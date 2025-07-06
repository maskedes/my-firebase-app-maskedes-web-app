from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase # APITestCase provides a DRF client

from .models import BlogPost, Video, MarketingPage, UserProfile, Promotion, CouponCode, AffiliateProfile, Referral, TrackedEvent
from .serializers import BlogPostSerializer, VideoSerializer

User = get_user_model()

class UserModelTests(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(username='testuser_model', email='test_model@example.com', password='password123', firebase_uid='fbuid_model_test')
        self.assertEqual(user.username, 'testuser_model')
        self.assertEqual(user.email, 'test_model@example.com')
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.firebase_uid, 'fbuid_model_test')

        # Test UserProfile creation signal or direct creation
        UserProfile.objects.get_or_create(user=user)
        self.assertIsNotNone(user.profile)

class BlogPostModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser_blog', email='test_blog@example.com', password='password123')

    def test_create_blog_post(self):
        post = BlogPost.objects.create(
            title="My First Blog Post",
            slug="my-first-blog-post",
            content="This is the content of my first blog post.",
            author=self.user,
            status="published"
        )
        self.assertEqual(post.title, "My First Blog Post")
        self.assertEqual(str(post), "My First Blog Post")
        self.assertEqual(post.status, "published")
        self.assertIsNotNone(post.created_at)
        self.assertIsNotNone(post.updated_at)
        # published_at should be set by model's save method or view logic if status is 'published'
        # For this test, if not set by save, it might be None.
        # If model's save method is updated to auto-set published_at:
        # self.assertIsNotNone(post.published_at)


class VideoModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser_video', email='test_video@example.com', password='password123')

    def test_create_video(self):
        video = Video.objects.create(
            uploader=self.user,
            title="Test Video Title",
            video_url="http://example.com/video.mp4",
            status="published"
        )
        self.assertEqual(video.title, "Test Video Title")
        self.assertEqual(str(video), "Test Video Title")
        self.assertEqual(video.status, "published")
        self.assertEqual(video.uploader, self.user)


# --- Serializer Tests ---
class BlogPostSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser_serializer', email='test_serializer@example.com')
        self.blog_post_attributes = {
            'title': 'Serializer Test Post',
            'slug': 'serializer-test-post',
            'content': 'Some great content here.',
            'author': self.user, # Serializer will handle this via context or read_only
            'status': 'draft',
            'meta_description': 'A test description.',
            'meta_keywords': 'test, post, serializer'
        }
        self.blog_post = BlogPost.objects.create(**self.blog_post_attributes)
        # For serializer context if needed (e.g. for request object)
        # self.request = type('Request', (), {'user': self.user})()
        # self.serializer_context = {'request': self.request}

    def test_blog_post_serializer_valid_data(self):
        serializer = BlogPostSerializer(instance=self.blog_post) # context=self.serializer_context
        data = serializer.data
        self.assertEqual(data['title'], self.blog_post_attributes['title'])
        self.assertEqual(data['slug'], self.blog_post_attributes['slug'])
        self.assertEqual(data['status'], self.blog_post_attributes['status'])
        self.assertEqual(data['author']['id'], self.user.id) # Assuming UserSerializer nests author info

    def test_blog_post_serializer_create(self):
        data_to_create = {
            'title': 'New Post via Serializer',
            'slug': 'new-post-via-serializer', # Slug might be auto-generated or required
            'content': 'Content for new post.',
            'status': 'published',
            # Author should be set by view/context, not passed directly unless by admin
        }
        # Mock request for context
        mock_request = type('Request', (), {'user': self.user})()
        serializer = BlogPostSerializer(data=data_to_create, context={'request': mock_request})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        created_post = serializer.save() # perform_create in view sets author

        self.assertEqual(created_post.title, data_to_create['title'])
        self.assertEqual(created_post.author, self.user)
        self.assertEqual(BlogPost.objects.count(), 2) # self.blog_post + created_post


# --- API View Tests (using APITestCase for DRF client and features) ---
class BlogPostAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='api_user', email='api@example.com', password='password123')
        self.staff_user = User.objects.create_user(username='staff_user', email='staff@example.com', password='password123', is_staff=True)

        self.published_post = BlogPost.objects.create(
            title="Published API Post", slug="published-api-post", content="Content", author=self.user, status="published"
        )
        self.draft_post_by_user = BlogPost.objects.create(
            title="Draft API Post by User", slug="draft-api-post-user", content="Content", author=self.user, status="draft"
        )
        self.draft_post_by_staff = BlogPost.objects.create(
            title="Draft API Post by Staff", slug="draft-api-post-staff", content="Content", author=self.staff_user, status="draft"
        )
        self.client = APIClient()

    def test_list_blog_posts_anonymous(self):
        url = reverse('blogpost-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Assuming no pagination, response.data is a list
        self.assertEqual(len(response.data), 1) # Only published_post
        self.assertEqual(response.data[0]['slug'], self.published_post.slug)

    def test_list_blog_posts_authenticated_user(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('blogpost-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Assuming no pagination, response.data is a list
        # Should see own draft + published posts
        slugs_in_response = {item['slug'] for item in response.data}
        self.assertIn(self.published_post.slug, slugs_in_response)
        self.assertIn(self.draft_post_by_user.slug, slugs_in_response)
        self.assertEqual(len(response.data), 2)

    def test_list_blog_posts_staff_user(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('blogpost-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Assuming no pagination, response.data is a list
        # Staff should see all posts (own drafts, other drafts, published)
        self.assertEqual(len(response.data), 3)

    def test_retrieve_published_blog_post_anonymous(self):
        url = reverse('blogpost-detail', kwargs={'slug': self.published_post.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], self.published_post.title)

    def test_retrieve_draft_blog_post_anonymous_forbidden(self):
        url = reverse('blogpost-detail', kwargs={'slug': self.draft_post_by_user.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND) # Or 403 if permission explicitly denies

    def test_retrieve_own_draft_blog_post_authenticated(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('blogpost-detail', kwargs={'slug': self.draft_post_by_user.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], self.draft_post_by_user.title)

    def test_create_blog_post_authenticated(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('blogpost-list')
        data = {
            'title': 'User Created Post',
            'slug': 'user-created-post-api', # Slug is often auto-generated or required
            'content': 'A post created via API by authenticated user.',
            'status': 'draft'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(BlogPost.objects.count(), 4) # 3 from setup + 1 new
        new_post = BlogPost.objects.get(slug=data['slug'])
        self.assertEqual(new_post.author, self.user)

    def test_create_blog_post_unauthenticated(self):
        url = reverse('blogpost-list')
        data = {'title': 'Anon Post', 'slug': 'anon-post', 'content': 'Content', 'status': 'draft'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_own_blog_post(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('blogpost-detail', kwargs={'slug': self.draft_post_by_user.slug})
        updated_data = {'title': 'Updated Title by Owner', 'content': 'Updated content.'}
        response = self.client.patch(url, updated_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.draft_post_by_user.refresh_from_db()
        self.assertEqual(self.draft_post_by_user.title, updated_data['title'])

    def test_update_other_user_blog_post_forbidden(self):
        # Non-staff user trying to update another user's (staff_user's) post
        self.client.force_authenticate(user=self.user)
        url = reverse('blogpost-detail', kwargs={'slug': self.draft_post_by_staff.slug})
        updated_data = {'title': 'Attempted Update'}
        response = self.client.patch(url, updated_data, format='json')
        # Based on IsAuthorOrAdminOrReadOnly and queryset filtering, this should be 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_own_blog_post(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('blogpost-detail', kwargs={'slug': self.draft_post_by_user.slug})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(BlogPost.objects.filter(slug=self.draft_post_by_user.slug).exists())

# --- Firebase Authentication Backend Tests (Placeholder) ---
from unittest.mock import patch, MagicMock

class FirebaseAuthenticationBackendTests(TestCase):
    def setUp(self):
        from .authentication import FirebaseAuthenticationBackend
        self.backend = FirebaseAuthenticationBackend()
        self.user_data = {
            'uid': 'test_firebase_uid',
            'email': 'firebase_auth_test@example.com',
            'name': 'Firebase TestUser'
        }

    @patch('firebase_admin.auth.verify_id_token')
    @patch('firebase_admin._apps', True) # Mock that Firebase app is initialized
    def test_authenticate_new_user(self, mock_verify_id_token):
        mock_verify_id_token.return_value = self.user_data

        # Mock request object if your auth backend or subsequent logic (like email sending) uses it
        mock_request = MagicMock()
        mock_request.META = {'REMOTE_ADDR': '127.0.0.1', 'HTTP_USER_AGENT': 'TestAgent'}
        mock_request.session = MagicMock()
        mock_request.session.session_key = 'testsessionkey'

        # Patch send_templated_email and TrackedEvent.objects.create to avoid side effects in this unit test
        with patch('core.authentication.send_templated_email') as mock_send_email, \
             patch('core.models.TrackedEvent.objects.create') as mock_track_event:

            user = self.backend.authenticate(request=mock_request, id_token='fake_token')

            self.assertIsNotNone(user)
            self.assertEqual(user.firebase_uid, self.user_data['uid'])
            self.assertEqual(user.email, self.user_data['email'])
            self.assertEqual(user.username, self.user_data['uid']) # As per current logic

            # Check if email and event tracking were called for new user
            mock_send_email.assert_called_once()
            mock_track_event.assert_called_once()
            args, kwargs = mock_track_event.call_args
            self.assertEqual(kwargs['event_type'], 'user_signup')
            self.assertEqual(kwargs['user'], user)


    @patch('firebase_admin.auth.verify_id_token')
    @patch('firebase_admin._apps', True)
    def test_authenticate_existing_user(self, mock_verify_id_token):
        mock_verify_id_token.return_value = self.user_data
        # Pre-create the user
        existing_user = User.objects.create_user(
            username=self.user_data['uid'], # Ensure username matches UID if that's the logic
            email='old_email@example.com', # Different email to test update
            firebase_uid=self.user_data['uid']
        )

        with patch('core.authentication.send_templated_email') as mock_send_email, \
             patch('core.models.TrackedEvent.objects.create') as mock_track_event:

            user = self.backend.authenticate(request=None, id_token='fake_token')

            self.assertIsNotNone(user)
            self.assertEqual(user.id, existing_user.id)
            self.assertEqual(user.email, self.user_data['email']) # Email should be updated

            # Email and signup event should NOT be called for existing user
            mock_send_email.assert_not_called()
            mock_track_event.assert_not_called()


    @patch('firebase_admin.auth.verify_id_token')
    @patch('firebase_admin._apps', True)
    def test_authenticate_invalid_token(self, mock_verify_id_token):
        from firebase_admin import auth
        mock_verify_id_token.side_effect = auth.InvalidIdTokenError("Token is invalid.")
        user = self.backend.authenticate(request=None, id_token='invalid_token')
        self.assertIsNone(user)

    # Add more tests for other scenarios: token without email, Firebase init failure (if not globally patched), etc.

# TODO: Add tests for Video API, MarketingPage API, Promotions/Coupons, Affiliate System, etc.
# For example:
# class VideoAPITests(APITestCase): ...
# class CouponValidationAPITests(APITestCase): ...
# class AffiliateProfileAPITests(APITestCase): ...
# class RegisterReferralAPITests(APITestCase): ...
# class SitemapAccessibilityTests(TestCase): ...
#     def test_sitemap_xml_accessible(self):
#         url = reverse('django.contrib.sitemaps.views.sitemap')
#         response = self.client.get(url)
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response['content-type'], 'application/xml')
#         # Further checks on content can be done if needed.
#         # self.assertContains(response, "<loc>") # Basic check for sitemap structure
#         # self.assertContains(response, self.published_post.slug) # Check if a known published item is there
#         # Note: The above content check depends on having a Site object and actual content.

# To run these tests: python manage.py test core
# Remember to configure Firebase Admin SDK (e.g., with a mock service account key or by mocking firebase_admin.initialize_app)
# for tests that depend on it if not already handled by patching firebase_admin._apps.
# For tests that need Site framework (like sitemap), ensure SITE_ID is set and a Site object exists.
# You might need to create a Site object in setUpTestData for sitemap tests.
# from django.contrib.sites.models import Site
# @classmethod
# def setUpTestData(cls):
#     Site.objects.get_or_create(domain='example.com', name='example.com')
