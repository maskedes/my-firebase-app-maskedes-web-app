from django.contrib.auth import authenticate, login, logout, get_user_model
from rest_framework import status, views, permissions, viewsets
from rest_framework.response import Response
from .serializers import (
    FirebaseLoginSerializer, UserSerializer, UserProfileSerializer, VideoSerializer,
    MarketingPageSerializer, BlogPostSerializer, PromotionSerializer, CouponCodeSerializer,
    CouponValidationRequestSerializer, CouponValidationResponseSerializer,
    AffiliateProfileSerializer, ReferralSerializer, CreateReferralSerializer
)
from .models import (
    UserProfile, Video, MarketingPage, BlogPost, Promotion, CouponCode,
    AffiliateProfile, Referral
)
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction # For atomic operations


User = get_user_model()

class FirebaseLoginView(views.APIView):
    """
    API view to handle user login via Firebase ID token.
    Accepts a Firebase ID token, authenticates the user, and logs them in,
    creating a Django session.
    """
    permission_classes = [permissions.AllowAny] # Anyone can attempt to login

    def post(self, request, *args, **kwargs):
        serializer = FirebaseLoginSerializer(data=request.data)
        if serializer.is_valid():
            id_token = serializer.validated_data['id_token']

            # Authenticate using the custom Firebase backend
            user = authenticate(request, id_token=id_token)

            if user:
                login(request, user) # Creates a Django session

                # Ensure user profile exists
                UserProfile.objects.get_or_create(user=user)

                user_data = UserSerializer(user).data
                return Response(user_data, status=status.HTTP_200_OK)
            else:
                # If authenticate returns None, it means token was invalid or user couldn't be processed
                return Response(
                    {"error": "Invalid Firebase token or user authentication failed."},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserLogoutView(views.APIView):
    """
    API view for user logout.
    """
    permission_classes = [permissions.IsAuthenticated] # Only authenticated users can logout

    def post(self, request, *args, **kwargs):
        logout(request) # Clears the Django session
        return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)

class UserDetailView(views.APIView):
    """
    API view to get current authenticated user's details.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        user_data = UserSerializer(user).data
        return Response(user_data, status=status.HTTP_200_OK)

class UserProfileView(views.APIView):
    """
    API view to get or update the current authenticated user's profile.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            serializer = UserProfileSerializer(profile)
            if created:
                 return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            # Catch any unexpected error during profile retrieval or creation
            return Response({"error": f"Could not retrieve or create profile: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Example of how an update might look (not fully implemented for brevity in this step)
    # def patch(self, request, *args, **kwargs):
    #     profile = UserProfile.objects.get(user=request.user)
    #     # Assuming you have a serializer that handles profile updates
    #     # serializer = UserProfileUpdateSerializer(profile, data=request.data, partial=True)
    #     # if serializer.is_valid():
    #     #     serializer.save()
    #     #     return Response(serializer.data, status=status.HTTP_200_OK)
    #     # return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        pass


# Permissions for VideoViewSet
class IsUploaderOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow uploaders of an object to edit or delete it.
    Read operations are allowed for any request (authenticated or not).
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the uploader of the video.
        return obj.uploader == request.user


class VideoViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows videos to be viewed or edited.
    """
    queryset = Video.objects.filter(status='published').order_by('-uploaded_at') # Default to published videos
    serializer_class = VideoSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsUploaderOrReadOnly] # Must be auth to create/edit/delete

    def get_queryset(self):
        """
        Optionally restricts the returned videos to a given user,
        by filtering against a `username` query parameter in the URL.
        Also, users should see their own non-published videos.
        """
        queryset = Video.objects.all().order_by('-uploaded_at') # Start with all for potential filtering

        # Allow users to see their own videos regardless of status
        if self.request.user.is_authenticated:
            user_videos = Video.objects.filter(uploader=self.request.user)
            published_videos = Video.objects.filter(status='published').exclude(uploader=self.request.user)
            queryset = user_videos | published_videos # Combine ensuring unique results
            queryset = queryset.order_by('-uploaded_at') # Re-apply ordering
        else:
            # Anonymous users only see published videos
            queryset = Video.objects.filter(status='published').order_by('-uploaded_at')

        # Example: Filter by uploader's username if a query param is present
        # username = self.request.query_params.get('username')
        # if username is not None:
        #     queryset = queryset.filter(uploader__username=username)

        return queryset.distinct()


    def perform_create(self, serializer):
        # Ensure the uploader is set to the current authenticated user
        if self.request.user.is_authenticated:
            serializer.save(uploader=self.request.user)
        else:
            # This should ideally be caught by permission_classes, but as a safeguard:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You must be logged in to upload a video.")

    # perform_update and perform_destroy are handled by IsUploaderOrReadOnly permission.

    # Placeholder for generating a signed URL for Firebase Storage
    # This would typically be a custom action if part of the ViewSet, or a separate APIView.
    # @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    # def generate_upload_url(self, request):
    #     """
    #     Generates a signed URL for uploading a video file directly to Firebase Storage.
    #     Requires firebase-admin SDK to be configured.
    #     """
    #     if not firebase_admin._apps:
    #         return Response({"error": "Firebase Admin SDK not initialized."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    #     file_name = request.data.get('file_name')
    #     content_type = request.data.get('content_type')

    #     if not file_name or not content_type:
    #         return Response({"error": "file_name and content_type are required."}, status=status.HTTP_400_BAD_REQUEST)

    #     try:
    #         bucket = storage.bucket() # Default bucket
    #         blob = bucket.blob(f"videos/{request.user.firebase_uid}/{file_name}") # Example path

    #         signed_url = blob.generate_signed_url(
    #             version="v4",
    #             expiration=timedelta(minutes=30), # URL expires in 30 minutes
    #             method="PUT",
    #             content_type=content_type,
    #         )
    #         return Response({"signed_url": signed_url, "file_path": blob.name}, status=status.HTTP_200_OK)
    #     except Exception as e:
    #         return Response({"error": f"Could not generate signed URL: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Need to import firebase_admin and storage for the above commented out code
# import firebase_admin
# from firebase_admin import storage
# from datetime import timedelta


# --- CMS Views ---

class IsAuthorOrAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission:
    - Read operations are allowed for any request (published content).
    - Write operations are allowed only if the user is the author or an admin/staff.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions for published content (or if user is author/staff)
        if request.method in permissions.SAFE_METHODS:
            if obj.status == 'published':
                return True
            # Allow viewing non-published if user is author or staff/admin
            return request.user.is_authenticated and (obj.author == request.user or request.user.is_staff)

        # Write permissions are only allowed to the author or staff/admin.
        if not request.user.is_authenticated:
            return False
        return obj.author == request.user or request.user.is_staff


class BaseContentViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet for content models like MarketingPage and BlogPost.
    Handles common logic for listing published content vs. user's own content.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrAdminOrReadOnly]
    lookup_field = 'slug' # Use slug for detail view lookup

    def get_queryset(self):
        # Get the base queryset from the specific model (e.g., MarketingPage.objects.all())
        model_class = self.serializer_class.Meta.model
        queryset = model_class.objects.all().select_related('author')

        # If user is authenticated and staff/admin, show all content
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return queryset.order_by('-status', '-updated_at')

        # If user is authenticated (but not staff), show their own drafts/reviews + all published
        if self.request.user.is_authenticated:
            user_content = queryset.filter(author=self.request.user)
            published_content = queryset.filter(status='published').exclude(author=self.request.user)
            # Combine ensuring unique results, ordered by status then date
            return (user_content | published_content).distinct().order_by('-status', '-updated_at')

        # For anonymous users, only show published content
        return queryset.filter(status='published').order_by('-published_at')

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            # If author is not provided in request data, set current user as author.
            # Admins might be able to set other authors.
            serializer.save(author=serializer.validated_data.get('author', self.request.user))
        else:
            # This case should be blocked by IsAuthenticatedOrReadOnly, but as a safeguard:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Authentication required to create content.")

    def perform_update(self, serializer):
        # Author can be changed by admin, otherwise it remains the same or is set on create.
        # The IsAuthorOrAdminOrReadOnly permission handles who can update.
        # If status is changed to 'published' and published_at is not set, set it.
        # (This logic can also live in the model's save method)
        from django.utils import timezone
        instance = serializer.instance
        new_status = serializer.validated_data.get('status', instance.status)

        if new_status == 'published' and not instance.published_at:
            serializer.save(published_at=timezone.now())
        elif new_status != 'published' and instance.published_at:
            serializer.save(published_at=None)
        else:
            serializer.save()


class MarketingPageViewSet(BaseContentViewSet):
    """
    API endpoint for Marketing Pages.
    """
    serializer_class = MarketingPageSerializer
    # queryset is dynamically set by get_queryset in BaseContentViewSet


class BlogPostViewSet(BaseContentViewSet):
    """
    API endpoint for Blog Posts.
    """
    serializer_class = BlogPostSerializer
    # queryset is dynamically set by get_queryset in BaseContentViewSet

# --- End CMS Views ---


# --- Promotions/Coupons Views ---

class PromotionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing Promotions.
    Typically, this would be admin/staff only.
    """
    queryset = Promotion.objects.all().order_by('-created_at')
    serializer_class = PromotionSerializer
    permission_classes = [permissions.IsAdminUser] # Only admins can manage promotions

class CouponCodeViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing Coupon Codes.
    Typically, this would be admin/staff only.
    """
    queryset = CouponCode.objects.all().select_related('promotion', 'user_specific').order_by('-created_at')
    serializer_class = CouponCodeSerializer
    permission_classes = [permissions.IsAdminUser] # Only admins can manage coupon codes

    def get_queryset(self):
        queryset = super().get_queryset()
        # Optional: filter by promotion_id if provided in query params
        promotion_id = self.request.query_params.get('promotion_id')
        if promotion_id:
            queryset = queryset.filter(promotion_id=promotion_id)
        return queryset

class ValidateCouponView(views.APIView):
    """
    API endpoint to validate a coupon code.
    Accessible by authenticated users.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        request_serializer = CouponValidationRequestSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(request_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        code_str = request_serializer.validated_data['code']

        try:
            coupon = CouponCode.objects.select_related('promotion').get(code__iexact=code_str) # case-insensitive match
        except CouponCode.DoesNotExist:
            response_data = {"valid": False, "message": "Invalid coupon code.", "discount_type": None, "discount_value": None, "coupon_id": None, "promotion_id": None}
            serializer = CouponValidationResponseSerializer(data=response_data)
            serializer.is_valid(raise_exception=True) # Should always be valid
            return Response(serializer.validated_data, status=status.HTTP_200_OK) # OK response but indicates invalid

        # Check if coupon and its promotion are valid for the current user
        # The user for validation is request.user
        if coupon.is_currently_valid(user=request.user):
            promo = coupon.promotion
            response_data = {
                "valid": True,
                "message": "Coupon is valid.",
                "discount_type": promo.discount_type,
                "discount_value": promo.discount_value,
                "coupon_id": coupon.id,
                "promotion_id": promo.id,
            }
        else:
            # Determine a more specific reason for invalidity if possible
            message = "Coupon code cannot be applied."
            if not coupon.is_active or not coupon.promotion.is_active:
                message = "Coupon code is not active."
            elif coupon.promotion.start_date > timezone.now():
                 message = "Promotion has not started yet."
            elif coupon.promotion.end_date and coupon.promotion.end_date < timezone.now():
                 message = "Promotion has expired."
            elif coupon.valid_from and coupon.valid_from > timezone.now():
                message = "Coupon is not yet valid."
            elif coupon.valid_to and coupon.valid_to < timezone.now():
                message = "Coupon has expired."
            elif coupon.max_uses is not None and coupon.uses_count >= coupon.max_uses:
                message = "Coupon has reached its usage limit."
            elif coupon.user_specific and coupon.user_specific != request.user:
                message = "Coupon is not valid for this user."
            # Add more specific messages as needed (e.g., per-user promo limits)

            response_data = {"valid": False, "message": message, "discount_type": None, "discount_value": None, "coupon_id": coupon.id, "promotion_id": coupon.promotion.id}

        serializer = CouponValidationResponseSerializer(data=response_data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

# --- End Promotions/Coupons Views ---


# --- Affiliate/Referral Views ---

class AffiliateProfileDetailView(views.APIView):
    """
    View to retrieve or create/update the current user's affiliate profile.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Get or create AffiliateProfile for the current user
        affiliate_profile, created = AffiliateProfile.objects.get_or_create(user=request.user)
        serializer = AffiliateProfileSerializer(affiliate_profile)
        if created:
            # Optionally, log an event or send a notification if a new profile was created.
            TrackedEvent.objects.create(
                event_type='affiliate_profile_created', # Define this event type
                user=request.user,
                data={'affiliate_profile_id': affiliate_profile.id, 'referral_code': affiliate_profile.referral_code}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        # Allow users to update certain parts of their affiliate profile, e.g., PayPal email
        affiliate_profile = get_object_or_404(AffiliateProfile, user=request.user)
        # Use a specific serializer for updates if fields are restricted
        serializer = AffiliateProfileSerializer(affiliate_profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            TrackedEvent.objects.create(
                event_type='affiliate_profile_updated', # Define this event type
                user=request.user,
                data={'affiliate_profile_id': affiliate_profile.id, 'updated_fields': list(request.data.keys())}
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegisterReferralView(views.APIView):
    """
    Endpoint to register a new user (current authenticated user) as being referred by a specific code.
    This should typically be called once, shortly after user signup if a referral code was provided.
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        # Check if this user has already been recorded as a referral
        if Referral.objects.filter(referred_user=request.user).exists():
            return Response(
                {"error": "This user has already been processed for a referral."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CreateReferralSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        referral_code_used = serializer.validated_data['referral_code']

        try:
            # Find the affiliate profile that owns the code
            affiliate_profile = AffiliateProfile.objects.get(referral_code__iexact=referral_code_used)
        except AffiliateProfile.DoesNotExist:
            # Optionally, still record the attempt with a null affiliate_profile if you want to track invalid code usage
            # For now, treat as an error.
            return Response({"error": "Invalid referral code."}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure the user is not referring themselves
        if affiliate_profile.user == request.user:
            return Response({"error": "Cannot refer yourself."}, status=status.HTTP_400_BAD_REQUEST)

        # Create the referral record
        referral = Referral.objects.create(
            referred_user=request.user,
            referral_code_used=referral_code_used.upper(), # Store consistently
            affiliate_profile=affiliate_profile,
            status='pending' # Initial status
            # commission_earned can be set here if there's an immediate signup bonus, or later.
        )

        # Basic commission for signup (example) - this logic might be more complex
        # For simplicity, let's assume a fixed $1 signup commission for the affiliate.
        # This should be configurable.
        signup_commission = getattr(settings, 'AFFILIATE_SIGNUP_COMMISSION', 1.00)
        if signup_commission > 0:
            referral.commission_earned = signup_commission
            affiliate_profile.balance += signup_commission
            affiliate_profile.total_earned += signup_commission
            referral.status = 'commission_awarded' # Or 'pending_confirmation' then 'commission_awarded'

            affiliate_profile.save(update_fields=['balance', 'total_earned'])
            referral.save(update_fields=['commission_earned', 'status'])

        TrackedEvent.objects.create(
            event_type='user_referred', # Define this event type
            user=request.user, # The user who was referred
            data={
                'referral_id': referral.id,
                'referral_code': referral_code_used,
                'affiliate_user_id': affiliate_profile.user.id,
                'commission_earned': float(referral.commission_earned or 0.0)
            }
        )

        return Response(ReferralSerializer(referral).data, status=status.HTTP_201_CREATED)


class AffiliateProfileAdminViewSet(viewsets.ModelViewSet):
    """
    Admin viewset for managing Affiliate Profiles.
    """
    queryset = AffiliateProfile.objects.all().select_related('user').order_by('-created_at')
    serializer_class = AffiliateProfileSerializer
    permission_classes = [permissions.IsAdminUser]

class ReferralAdminViewSet(viewsets.ModelViewSet):
    """
    Admin viewset for managing Referrals.
    """
    queryset = Referral.objects.all().select_related('referred_user', 'affiliate_profile__user').order_by('-timestamp')
    serializer_class = ReferralSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ['status', 'affiliate_profile__referral_code', 'referral_code_used']
    search_fields = ['referred_user__username', 'referred_user__email', 'affiliate_profile__user__username', 'referral_code_used']


# --- End Affiliate/Referral Views ---
