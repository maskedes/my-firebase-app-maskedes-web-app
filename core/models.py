from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    Custom User model that integrates with Firebase Authentication.
    """
    # We will use the default username field from AbstractUser to store Firebase UID for simplicity of integration
    # with Django's ecosystem, but ensure it's populated with Firebase UID.
    # Email will be sourced from Firebase and should be unique.
    email = models.EmailField(unique=True, blank=False, null=False, verbose_name='email address')
    firebase_uid = models.CharField(max_length=128, unique=True, help_text="Firebase User ID", db_index=True, null=True, blank=True) # Null/Blank true initially until linked

    # Use email as the username field for Django's auth system if preferred,
    # but AbstractUser's `username` field is already unique and indexed.
    # Let's keep 'username' as the USERNAME_FIELD for now and populate it with Firebase UID.
    # Email can be used for login attempts via a custom auth backend if needed.
    # USERNAME_FIELD = 'email'
    # REQUIRED_FIELDS = ['username'] # username will be firebase_uid

    # If USERNAME_FIELD is 'email', then 'username' (Firebase UID) might not be required by REQUIRED_FIELDS
    # if it's populated programmatically.
    # For now, stick to default AbstractUser USERNAME_FIELD = 'username' and we'll ensure it's populated by Firebase UID.

    def __str__(self):
        return self.email or self.username

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    # Add other profile fields here later as needed
    # e.g., bio = models.TextField(blank=True)
    # e.g., avatar_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

class Video(models.Model):
    VIDEO_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('published', 'Published'),
        ('failed', 'Failed'),
        ('archived', 'Archived'),
    ]

    uploader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='videos')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    # URL from Firebase Storage (or other cloud storage)
    video_url = models.URLField(max_length=1024)
    # Optional: path in the storage bucket if needed for direct SDK operations
    storage_path = models.CharField(max_length=1024, blank=True, null=True, help_text="Path to the video file in cloud storage.")

    thumbnail_url = models.URLField(max_length=1024, blank=True, null=True)
    duration = models.PositiveIntegerField(blank=True, null=True, help_text="Duration in seconds")

    status = models.CharField(
        max_length=20,
        choices=VIDEO_STATUS_CHOICES,
        default='pending'
    )

    uploaded_at = models.DateTimeField(auto_now_add=True, help_text="When the metadata record was created.")
    # `updated_at` can be useful for tracking metadata changes
    updated_at = models.DateTimeField(auto_now=True)

    # Optional: views count, likes, etc. can be added later
    # view_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-uploaded_at']

# --- CMS Models ---
class ContentBase(models.Model):
    """
    Abstract base class for content types like MarketingPage and BlogPost.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('review', 'In Review'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, help_text="URL-friendly identifier. Auto-generated if left blank in admin.")
    # For rich text, consider using a specialized field later (e.g., from django-ckeditor)
    content = models.TextField(help_text="Main content body. Can use Markdown or HTML if supported by frontend rendering.")

    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="%(class)s_authored")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft', db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text="Date and time content was published.")

    # SEO fields (can be moved to a separate SEO mixin/model if they grow)
    meta_description = models.CharField(max_length=300, blank=True, help_text="Brief description for SEO (meta description tag).")
    meta_keywords = models.CharField(max_length=255, blank=True, help_text="Comma-separated keywords for SEO.")


    class Meta:
        abstract = True
        ordering = ['-published_at', '-updated_at']

    def __str__(self):
        return self.title

    # Consider adding a save method to auto-populate slug or set published_at when status changes.
    # from django.utils import timezone
    # from django.utils.text import slugify
    # def save(self, *args, **kwargs):
    #     if not self.slug:
    #         self.slug = slugify(self.title)
    #         # Ensure slug uniqueness if auto-generating
    #         original_slug = self.slug
    #         counter = 1
    #         while self.__class__.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
    #             self.slug = f"{original_slug}-{counter}"
    #             counter += 1
    #
    #     if self.status == 'published' and not self.published_at:
    #         self.published_at = timezone.now()
    #     elif self.status != 'published' and self.published_at: # If unpublished
    #         self.published_at = None # Clear published_at if moved out of published status
    #
    #     super().save(*args, **kwargs)


class MarketingPage(ContentBase):
    """
    For standalone pages like About Us, Landing Pages, etc.
    """
    # Add any specific fields for marketing pages if needed, e.g., template_name
    # template_name = models.CharField(max_length=100, blank=True, help_text="Optional template file to render this page.")

    class Meta:
        verbose_name = "Marketing Page"
        verbose_name_plural = "Marketing Pages"


class BlogPost(ContentBase):
    """
    For blog articles.
    """
    # Example: Add categories or tags if needed later
    # category = models.ForeignKey('BlogCategory', on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    # tags = TaggableManager(blank=True) # Requires django-taggit

    # For simplicity, these are commented out. Can be added in a future step.
    # header_image = models.ImageField(upload_to='blog_headers/', null=True, blank=True)

    class Meta:
        verbose_name = "Blog Post"
        verbose_name_plural = "Blog Posts"


# --- End CMS Models ---


# --- Promotions/Coupons Models ---
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid # For potentially generating unique codes if not manually entered

class Promotion(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
    ]

    name = models.CharField(max_length=255, help_text="Internal name for the promotion.")
    description = models.TextField(blank=True, help_text="Customer-facing description if applicable.")

    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    # For percentage, value is like 10 for 10%. For fixed_amount, it's the actual amount.
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True, help_text="Optional: when the promotion automatically deactivates.")

    is_active = models.BooleanField(default=True, db_index=True, help_text="Master switch for the promotion.")

    # Optional global limits for the promotion itself
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Max total uses for this entire promotion across all codes.")
    total_uses_count = models.PositiveIntegerField(default=0, editable=False, help_text="How many times this promotion has been used in total.")

    # Optional per-user limit for the promotion
    max_uses_per_user = models.PositiveIntegerField(null=True, blank=True, help_text="Max times a single user can use this promotion.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_discount_type_display()}: {self.discount_value})"

    def is_currently_active(self):
        if not self.is_active:
            return False
        now = timezone.now()
        if self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        if self.max_uses is not None and self.total_uses_count >= self.max_uses:
            return False
        return True

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Promotion"
        verbose_name_plural = "Promotions"


class CouponCode(models.Model):
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='coupons')
    code = models.CharField(max_length=50, unique=True, db_index=True, help_text="The actual coupon code string (e.g., SUMMER20).")

    is_active = models.BooleanField(default=True, help_text="Switch for this specific code.")

    uses_count = models.PositiveIntegerField(default=0, help_text="How many times this specific code has been used.")
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Max uses for this specific code (can override promotion's global limit for this code).")

    valid_from = models.DateTimeField(null=True, blank=True, help_text="Code-specific start date (must be within promotion's dates).")
    valid_to = models.DateTimeField(null=True, blank=True, help_text="Code-specific end date (must be within promotion's dates).")

    # If a coupon is tied to a specific user
    user_specific = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='coupons', help_text="If set, only this user can use the coupon.")

    # Potentially store which order/transaction used this coupon
    # order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='applied_coupon')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code

    def is_currently_valid(self, user=None):
        if not self.is_active or not self.promotion.is_currently_active():
            return False

        now = timezone.now()
        if self.valid_from and self.valid_from > now:
            return False
        if self.valid_to and self.valid_to < now:
            return False

        if self.max_uses is not None and self.uses_count >= self.max_uses:
            return False

        if self.user_specific and self.user_specific != user:
            return False

        # Check promotion-level per-user limits if applicable
        if user and self.promotion.max_uses_per_user is not None:
            # This check requires tracking how many times a user has used *any* code for this promotion.
            # This might involve a separate model like `UserPromotionUsage`.
            # For now, this specific check is simplified / deferred.
            # Example:
            # user_promo_uses = UserPromotionUsage.objects.filter(user=user, promotion=self.promotion).count()
            # if user_promo_uses >= self.promotion.max_uses_per_user:
            #     return False
            pass

        return True

    def increment_usage(self):
        self.uses_count += 1
        self.promotion.total_uses_count +=1 # Assuming direct update, might need F() expressions for concurrency
        self.save(update_fields=['uses_count'])
        self.promotion.save(update_fields=['total_uses_count'])

    class Meta:
        ordering = ['promotion', 'code']
        verbose_name = "Coupon Code"
        verbose_name_plural = "Coupon Codes"

# --- End Promotions/Coupons Models ---


# --- Analytics Foundation ---
class TrackedEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        # User related
        ('user_signup', 'User Signup'),
        ('user_login', 'User Login'),
        ('user_logout', 'User Logout'),
        ('profile_update', 'Profile Update'),
        # Content related
        ('page_view', 'Page View'), # Generic page view
        ('blog_post_view', 'Blog Post View'),
        ('marketing_page_view', 'Marketing Page View'),
        ('video_view', 'Video View'),
        # Action related
        ('video_upload_initiated', 'Video Upload Initiated'), # Metadata created
        ('video_published', 'Video Published'),
        ('coupon_validated', 'Coupon Validated'),
        ('coupon_applied', 'Coupon Applied'), # This would be after successful order/action
        # System related
        ('error_occurred', 'Error Occurred'),
        # Add more specific event types as needed
    ]

    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES, db_index=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tracked_events')
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    # Contextual information
    session_id = models.CharField(max_length=100, null=True, blank=True, db_index=True) # Could be Django session key or a custom one
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    # Flexible data payload for event-specific details
    # E.g., for 'page_view', data could be {'url': '/some/page', 'referrer': '...'}
    # E.g., for 'video_view', data could be {'video_id': 123, 'duration_watched': 60}
    data = models.JSONField(null=True, blank=True, help_text="Event-specific data payload.")

    def __str__(self):
        user_str = f"User: {self.user.username}" if self.user else "Anonymous"
        return f"{self.get_event_type_display()} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} ({user_str})"

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Tracked Event"
        verbose_name_plural = "Tracked Events"
        indexes = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]
# --- End Analytics Foundation ---


# --- Affiliate/Referral System ---
import secrets

def generate_unique_referral_code():
    # Generate a sufficiently random and unique enough code.
    # Loop to ensure uniqueness, though collision is highly unlikely with enough length.
    # For production, might want a more robust system or check against existing codes more rigorously.
    return secrets.token_urlsafe(8).upper().replace('-', '').replace('_', '')[:10] # Example: 10 char alphanumeric

class AffiliateProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='affiliate_profile')
    referral_code = models.CharField(max_length=20, unique=True, default=generate_unique_referral_code, db_index=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Current available commission balance.")
    total_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Total commission earned over time.")

    is_active = models.BooleanField(default=True, help_text="Whether the affiliate account is active.")
    # Payout information (simplified)
    paypal_email = models.EmailField(null=True, blank=True, help_text="PayPal email for payouts.")
    # Add other payout methods/details as needed: bank_account_info = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Affiliate Profile ({self.referral_code})"

    class Meta:
        verbose_name = "Affiliate Profile"
        verbose_name_plural = "Affiliate Profiles"

class Referral(models.Model):
    REFERRAL_STATUS_CHOICES = [
        ('pending', 'Pending'),       # User signed up, awaiting confirmation/action
        ('confirmed', 'Confirmed'),   # Referral action completed (e.g., first purchase, subscription)
        ('commission_awarded', 'Commission Awarded'), # Commission calculated and added to affiliate balance
        ('paid_out', 'Paid Out'),     # Commission included in a payout
        ('cancelled', 'Cancelled'),   # Referral invalidated
    ]

    referred_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_received', help_text="The user who was referred.")
    # It's good to also store the original referral code used, in case the affiliate changes their code later.
    referral_code_used = models.CharField(max_length=20, db_index=True, help_text="The referral code used at signup.")

    # Link to the affiliate profile that owns the referral_code_used at the time of referral
    # This might be null if the affiliate profile was deleted, or if code was invalid but still tracked.
    affiliate_profile = models.ForeignKey(AffiliateProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals_made')

    timestamp = models.DateTimeField(default=timezone.now, help_text="When the referral occurred (e.g., signup time).")

    # Store commission details directly or link to a Commission model
    commission_earned = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Commission amount earned from this specific referral, if applicable immediately.")

    status = models.CharField(max_length=20, choices=REFERRAL_STATUS_CHOICES, default='pending', db_index=True)

    # Optional: details about the action that confirmed the referral
    # confirming_action_details = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        affiliate_name = self.affiliate_profile.user.username if self.affiliate_profile else "N/A"
        return f"User {self.referred_user.username} referred by {affiliate_name} via {self.referral_code_used}"

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Referral"
        verbose_name_plural = "Referrals"
        unique_together = ('referred_user', 'affiliate_profile') # A user can only be referred by one affiliate directly.
                                                                # Or (referred_user, referral_code_used) if affiliate_profile can be null initially.

# Consider a UserAction model if commissions are tied to specific actions post-referral (e.g. first purchase)
# class Commission (as detailed in plan) could be added for more granular tracking of earnings.

# --- End Affiliate/Referral System ---
