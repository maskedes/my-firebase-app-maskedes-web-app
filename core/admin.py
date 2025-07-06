from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserProfile

# Define an inline admin descriptor for UserProfile model
# which acts a bit like a singleton
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'

# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'firebase_uid', 'first_name', 'last_name', 'is_staff')
    search_fields = ('username', 'email', 'firebase_uid')

    # If you added custom fields to User model and want them in add/change forms:
    # fieldsets = BaseUserAdmin.fieldsets + (
    #     (None, {'fields': ('firebase_uid',)}),
    # )
    # add_fieldsets = BaseUserAdmin.add_fieldsets + (
    #     (None, {'fields': ('firebase_uid', 'email')}), # Ensure email is here if it's required
    # )


# Register the new UserAdmin
admin.site.register(User, UserAdmin)

# Optionally, if you want to manage UserProfiles directly (though typically done via User)
# admin.site.register(UserProfile)

from .models import Video

@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploader', 'status', 'uploaded_at', 'duration')
    list_filter = ('status', 'uploader')
    search_fields = ('title', 'description', 'uploader__username', 'uploader__email')
    readonly_fields = ('uploaded_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'video_url', 'storage_path', 'thumbnail_url')
        }),
        ('Details', {
            'fields': ('uploader', 'status', 'duration')
        }),
        ('Timestamps', {
            'fields': ('uploaded_at', 'updated_at'),
            'classes': ('collapse',) # Keep it collapsed by default
        }),
    )

    def get_queryset(self, request):
        # Optimize query by prefetching related uploader
        return super().get_queryset(request).select_related('uploader')

from .models import MarketingPage, BlogPost, User # User already imported

# Common Admin for ContentBase derived models
class ContentAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'status', 'author', 'published_at', 'updated_at')
    list_filter = ('status', 'author')
    search_fields = ('title', 'slug', 'content', 'author__username', 'author__email')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at', 'published_at')
    actions = ['publish_selected', 'unpublish_selected']

    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'content')
        }),
        ('Publication', {
            'fields': ('status', 'author', 'published_at')
        }),
        ('SEO', {
            'fields': ('meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.author_id: # Set author to current user if not already set
            obj.author = request.user

        # Handle published_at based on status (also consider model's save method)
        from django.utils import timezone
        if obj.status == 'published' and not obj.published_at:
            obj.published_at = timezone.now()
        elif obj.status != 'published' and obj.published_at:
            obj.published_at = None

        super().save_model(request, obj, form, change)

    def publish_selected(self, request, queryset):
        from django.utils import timezone
        updated_count = queryset.update(status='published', published_at=timezone.now())
        self.message_user(request, f"{updated_count} items were successfully published.")
    publish_selected.short_description = "Publish selected items"

    def unpublish_selected(self, request, queryset):
        updated_count = queryset.update(status='draft', published_at=None) # Or 'archived'
        self.message_user(request, f"{updated_count} items were successfully unpublished (set to draft).")
    unpublish_selected.short_description = "Unpublish selected items (set to draft)"


@admin.register(MarketingPage)
class MarketingPageAdmin(ContentAdmin):
    # Inherits all from ContentAdmin, can add specific overrides if needed
    pass

@admin.register(BlogPost)
class BlogPostAdmin(ContentAdmin):
    # Inherits all from ContentAdmin, can add specific overrides if needed
    # e.g., if BlogPost had categories or tags, add them to list_display, list_filter, etc.
    pass

from .models import Promotion, CouponCode

class CouponCodeInline(admin.TabularInline):
    model = CouponCode
    fk_name = "promotion"
    extra = 1 # Number of empty forms to display
    fields = ('code', 'is_active', 'max_uses', 'uses_count', 'user_specific', 'valid_from', 'valid_to')
    readonly_fields = ('uses_count',)
    # autocomplete_fields = ['user_specific'] # If you have a lot of users

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('name', 'discount_type', 'discount_value', 'start_date', 'end_date', 'is_active', 'total_uses_count')
    list_filter = ('discount_type', 'is_active', 'start_date', 'end_date')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'total_uses_count')
    inlines = [CouponCodeInline]
    fieldsets = (
        (None, {'fields': ('name', 'description')}),
        ('Discount', {'fields': ('discount_type', 'discount_value')}),
        ('Activity Window', {'fields': ('start_date', 'end_date', 'is_active')}),
        ('Usage Limits', {'fields': ('max_uses', 'total_uses_count', 'max_uses_per_user')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

@admin.register(CouponCode)
class CouponCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'promotion_name', 'is_active', 'uses_count', 'max_uses', 'user_specific_email', 'valid_to')
    list_filter = ('is_active', 'promotion', 'user_specific')
    search_fields = ('code', 'promotion__name', 'user_specific__email', 'user_specific__username')
    readonly_fields = ('created_at', 'updated_at', 'uses_count')
    autocomplete_fields = ['promotion', 'user_specific'] # Makes selecting easier
    fieldsets = (
        (None, {'fields': ('promotion', 'code', 'is_active')}),
        ('Usage', {'fields': ('uses_count', 'max_uses')}),
        ('Validity', {'fields': ('valid_from', 'valid_to')}),
        ('User Restriction', {'fields': ('user_specific',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def promotion_name(self, obj):
        return obj.promotion.name
    promotion_name.short_description = 'Promotion'
    promotion_name.admin_order_field = 'promotion__name'

    def user_specific_email(self, obj):
        if obj.user_specific:
            return obj.user_specific.email
        return None
    user_specific_email.short_description = 'User Specific (Email)'
    user_specific_email.admin_order_field = 'user_specific__email'

from .models import TrackedEvent

@admin.register(TrackedEvent)
class TrackedEventAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'event_type', 'user_email', 'session_id', 'ip_address')
    list_filter = ('event_type', 'timestamp', 'user')
    search_fields = ('event_type', 'user__username', 'user__email', 'session_id', 'ip_address', 'data')
    readonly_fields = ('timestamp', 'event_type', 'user', 'session_id', 'ip_address', 'user_agent', 'data') # All fields essentially
    date_hierarchy = 'timestamp'

    fieldsets = (
        ('Event Details', {'fields': ('event_type', 'timestamp', 'user')}),
        ('Context', {'fields': ('session_id', 'ip_address', 'user_agent')}),
        ('Data Payload', {'fields': ('data',)}),
    )

    def user_email(self, obj):
        if obj.user:
            return obj.user.email
        return '-'
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'

    def has_add_permission(self, request):
        return False # Events should be logged by the system, not added manually in admin

    def has_change_permission(self, request, obj=None):
        return False # Events are immutable once logged

    # Optional: Allow deletion for cleanup, but generally events are kept.
    # def has_delete_permission(self, request, obj=None):
    #     return request.user.is_superuser # Only superusers can delete

from .models import AffiliateProfile, Referral

@admin.register(AffiliateProfile)
class AffiliateProfileAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'referral_code', 'balance', 'total_earned', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__username', 'user__email', 'referral_code', 'paypal_email')
    readonly_fields = ('referral_code', 'balance', 'total_earned', 'created_at', 'updated_at')
    autocomplete_fields = ['user']
    fieldsets = (
        (None, {'fields': ('user', 'referral_code', 'is_active')}),
        ('Earnings', {'fields': ('balance', 'total_earned')}),
        ('Payout Info', {'fields': ('paypal_email',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referred_user_email', 'affiliate_username', 'referral_code_used', 'status', 'commission_earned', 'timestamp')
    list_filter = ('status', 'timestamp', 'affiliate_profile__user__username')
    search_fields = (
        'referred_user__username', 'referred_user__email',
        'affiliate_profile__user__username', 'affiliate_profile__referral_code',
        'referral_code_used'
    )
    readonly_fields = ('created_at', 'updated_at', 'timestamp')
    autocomplete_fields = ['referred_user', 'affiliate_profile']
    actions = ['mark_confirmed', 'mark_commission_awarded', 'mark_paid_out', 'mark_cancelled']

    fieldsets = (
        ('Referral Details', {'fields': ('referred_user', 'referral_code_used', 'affiliate_profile', 'timestamp')}),
        ('Commission & Status', {'fields': ('commission_earned', 'status')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def referred_user_email(self, obj):
        return obj.referred_user.email
    referred_user_email.short_description = 'Referred User'
    referred_user_email.admin_order_field = 'referred_user__email'

    def affiliate_username(self, obj):
        if obj.affiliate_profile:
            return obj.affiliate_profile.user.username
        return '-'
    affiliate_username.short_description = 'Affiliate'
    affiliate_username.admin_order_field = 'affiliate_profile__user__username'

    def mark_confirmed(self, request, queryset):
        updated_count = queryset.update(status='confirmed')
        self.message_user(request, f"{updated_count} referrals marked as confirmed.")
    mark_confirmed.short_description = "Mark selected referrals as Confirmed"

    def mark_commission_awarded(self, request, queryset):
        # Note: This action only changes status. Actual commission calculation and balance update
        # should happen in a more robust way (e.g., a service function or signal handler)
        # if not already handled at referral creation or via a separate process.
        updated_count = queryset.update(status='commission_awarded')
        self.message_user(request, f"{updated_count} referrals marked as Commission Awarded.")
    mark_commission_awarded.short_description = "Mark selected as Commission Awarded"

    def mark_paid_out(self, request, queryset):
        updated_count = queryset.update(status='paid_out')
        self.message_user(request, f"{updated_count} referrals marked as Paid Out.")
    mark_paid_out.short_description = "Mark selected referrals as Paid Out"

    def mark_cancelled(self, request, queryset):
        updated_count = queryset.update(status='cancelled')
        # Consider if cancelling a referral should revert any earned commission.
        self.message_user(request, f"{updated_count} referrals marked as Cancelled.")
    mark_cancelled.short_description = "Mark selected referrals as Cancelled"
