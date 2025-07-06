from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.conf import settings
import firebase_admin
from firebase_admin import auth, credentials

# App-specific imports
from .email_utils import send_templated_email
from .models import TrackedEvent # Assuming TrackedEvent is in core.models

User = get_user_model()

# Initialize Firebase Admin SDK if not already initialized
# This is a fallback if not initialized in settings.py, but settings.py is preferred.
# Ensure FIREBASE_SERVICE_ACCOUNT_KEY_PATH is set in your environment or Django settings.

# IMPORTANT: The primary initialization should be in settings.py.
# This check is to ensure Firebase is available for the backend.
# If using the settings.py initialization, this might be redundant but harmless if `firebase_admin._apps` check is correct.

if not firebase_admin._apps:
    FIREBASE_SERVICE_ACCOUNT_KEY_PATH = getattr(settings, 'FIREBASE_SERVICE_ACCOUNT_KEY_PATH', None)
    if FIREBASE_SERVICE_ACCOUNT_KEY_PATH:
        try:
            cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_KEY_PATH)
            firebase_admin.initialize_app(cred)
            print("Firebase Admin SDK initialized in authentication.py (fallback).")
        except Exception as e:
            print(f"Fallback Firebase Admin SDK initialization error in authentication.py: {e}")
            # Depending on how critical Firebase is at this point, you might raise an error.
    else:
        print("Firebase Admin SDK not configured for authentication.py (FIREBASE_SERVICE_ACCOUNT_KEY_PATH not found).")
        # Raise an error or handle as appropriate if Firebase is essential.
        # from django.core.exceptions import ImproperlyConfigured
        # raise ImproperlyConfigured("FIREBASE_SERVICE_ACCOUNT_KEY_PATH not set and Firebase app not initialized.")


class FirebaseAuthenticationBackend(BaseBackend):
    """
    Custom authentication backend for Firebase.
    Authenticates users using a Firebase ID token.
    """

    def authenticate(self, request, id_token=None):
        if id_token is None:
            return None

        if not firebase_admin._apps:
            print("Firebase Admin SDK is not initialized. Cannot authenticate.")
            # Optionally, you could try to initialize it here if it's strictly necessary
            # and not done elsewhere, but it's better to ensure it's done at startup.
            return None

        try:
            decoded_token = auth.verify_id_token(id_token)
            firebase_uid = decoded_token['uid']
            email = decoded_token.get('email')
            # Other claims like name, picture can be extracted if needed:
            # name = decoded_token.get('name')
            # picture = decoded_token.get('picture')

            if not email:
                # Firebase users might not always have an email (e.g., phone auth)
                # Decide how to handle this. For this app, email is mandatory.
                # If email is not in token, but user exists with this firebase_uid,
                # it might be acceptable. Or, enforce email verification in Firebase.
                print(f"Firebase token for UID {firebase_uid} does not contain an email.")
                # For now, we require email.
                return None


            # Try to get the user by Firebase UID first.
            user, created = User.objects.get_or_create(
                firebase_uid=firebase_uid,
                defaults={'email': email, 'username': firebase_uid} # Use UID as username
            )

            if created:
                user.is_active = True # Firebase users are active by default
                # You might want to set other fields from the token if available
                # e.g., user.first_name, user.last_name
                # For example, if 'name' is in decoded_token:
                # if 'name' in decoded_token:
                #     parts = decoded_token['name'].split(' ', 1)
                #     user.first_name = parts[0]
                #     if len(parts) > 1:
                #         user.last_name = parts[1]
                user.save()

                # Send welcome email and track event for new user
                try:
                    # Construct login URL (replace with actual frontend URL structure)
                    # This might come from settings or be a fixed path.
                    login_url = f"{getattr(settings, 'APP_FRONTEND_URL', 'http://localhost:3000')}/login" # Example

                    send_templated_email(
                        subject="Welcome to Our Platform!",
                        template_name_html="emails/welcome_email.html",
                        template_name_txt="emails/welcome_email.txt",
                        context={"user_name": user.first_name or user.username, "login_url": login_url},
                        recipient_list=[user.email]
                    )

                    # Track user signup event
                    # Extract IP and User-Agent if available from request (passed to authenticate)
                    ip_address = None
                    user_agent = None
                    session_id = None
                    if request:
                        ip_address = request.META.get('REMOTE_ADDR')
                        user_agent = request.META.get('HTTP_USER_AGENT')
                        if request.session and request.session.session_key:
                             session_id = request.session.session_key

                    TrackedEvent.objects.create(
                        event_type='user_signup',
                        user=user,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        session_id=session_id,
                        data={"firebase_uid": firebase_uid, "email": user.email}
                    )
                except Exception as e:
                    # Log error in sending email or tracking event, but don't fail authentication
                    print(f"Error in post-creation actions for user {user.email}: {e}")

            else:
                # If user exists, update email if it has changed in Firebase
                # (and it's different from current email to avoid unnecessary saves)
                if user.email != email:
                    # Check if the new email is already taken by another user (excluding current)
                    if User.objects.filter(email=email).exclude(firebase_uid=firebase_uid).exists():
                        print(f"Attempt to update email to {email} for user {firebase_uid}, but it's taken by another user.")
                        # Handle this conflict: maybe log it, or don't update the email.
                        # For now, we won't update if it causes a conflict.
                    else:
                        user.email = email
                        user.save(update_fields=['email'])

            # Ensure username is also set to firebase_uid for consistency, especially for existing users
            if user.username != firebase_uid:
                user.username = firebase_uid
                user.save(update_fields=['username'])

            return user

        except auth.InvalidIdTokenError as e: # More specific error for token verification
            print(f"Firebase ID token invalid: {e}")
            return None
        except firebase_admin.auth.UserNotFoundError as e: # If trying to get user by UID and not found
            print(f"Firebase user not found: {e}")
            return None
        except firebase_admin.FirebaseError as e: # Catch other Firebase errors
            print(f"Firebase authentication error: {e}")
            return None
        except User.MultipleObjectsReturned:
            # This shouldn't happen if firebase_uid is unique
            print(f"Multiple users found for Firebase UID: {firebase_uid}. Data integrity issue.")
            return None
        except Exception as e:
            # Catch any other unexpected errors during the process
            print(f"An unexpected error occurred during Firebase authentication: {e}")
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
