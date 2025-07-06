from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class FirebaseLoginSerializer(serializers.Serializer):
    """
    Serializer for Firebase ID token.
    """
    id_token = serializers.CharField()

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model.
    """
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'firebase_uid') # Add other fields as needed
        read_only_fields = ('id', 'username', 'email', 'firebase_uid') # firebase_uid and email are managed by backend/Firebase

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for the UserProfile model.
    """
    user = UserSerializer(read_only=True) # Nested user details

    class Meta:
        model = User # This should be UserProfile
        # Correcting the model to UserProfile
        # fields = ('user', 'bio', 'avatar_url', 'created_at', 'updated_at') # Example fields
        # For now, just the basics:
        fields = ('user', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

# Correcting UserProfileSerializer
from .models import UserProfile as UserProfileModel

class UserProfileSerializer(serializers.ModelSerializer): # Re-declaration to correct
    """
    Serializer for the UserProfile model.
    """
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserProfileModel
        # Add fields from UserProfile model here, e.g. 'bio', 'avatar_url'
        fields = ('id', 'user', 'created_at', 'updated_at')
        read_only_fields = ('id', 'user', 'created_at', 'updated_at')

from .models import Video

class VideoSerializer(serializers.ModelSerializer):
    uploader = UserSerializer(read_only=True)
    # If you want to accept uploader_id on write operations and have it validated:
    # uploader_id = serializers.PrimaryKeyRelatedField(
    #     queryset=User.objects.all(), source='uploader', write_only=True, required=False
    # )
    # ^ uploader will be set from request.user in the view for POST.

    class Meta:
        model = Video
        fields = (
            'id',
            'uploader',
            'title',
            'description',
            'video_url',
            'storage_path',
            'thumbnail_url',
            'duration',
            'status',
            'uploaded_at',
            'updated_at',
        )
        read_only_fields = ('id', 'uploader', 'uploaded_at', 'updated_at')
        # `status` might also be read-only for users and only updatable by admin or system processes
        # For now, let's make it writable by uploader for simplicity, can be restricted later.

    def create(self, validated_data):
        # Set uploader from context if not directly provided (recommended way)
        if 'uploader' not in validated_data and 'request' in self.context:
            validated_data['uploader'] = self.context['request'].user
        return super().create(validated_data)

from .models import MarketingPage, BlogPost

class BaseContentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    # author_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='author', write_only=True, required=False, allow_null=True)
    # ^ Author will be set from request.user for create, or can be specified by admin

    class Meta:
        abstract = True # This itself won't be used directly
        fields = (
            'id', 'title', 'slug', 'content', 'author', 'status',
            'created_at', 'updated_at', 'published_at',
            'meta_description', 'meta_keywords'
        )
        read_only_fields = ('id', 'author', 'created_at', 'updated_at', 'published_at')
        # Slug can be made read-only if auto-generated, or writable with validation
        # For now, let's allow writing slug, but it should be unique.
        # The model's save method (if uncommented) or admin prepopulated_fields can handle slug generation.

    def create(self, validated_data):
        # Set author from context if not directly provided and user is authenticated
        if 'author' not in validated_data and 'request' in self.context and self.context['request'].user.is_authenticated:
            validated_data['author'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Potentially set author if it's being changed by an admin and provided in data
        # if 'author_id' in validated_data:
        #    instance.author = validated_data.pop('author_id')
        # For now, author is mostly set on create or managed by admin.
        return super().update(instance, validated_data)

class MarketingPageSerializer(BaseContentSerializer):
    class Meta(BaseContentSerializer.Meta):
        model = MarketingPage
        # Add any MarketingPage specific fields here if they exist in the model
        # e.g. fields = BaseContentSerializer.Meta.fields + ('template_name',)


class BlogPostSerializer(BaseContentSerializer):
    class Meta(BaseContentSerializer.Meta):
        model = BlogPost
        # Add any BlogPost specific fields here
        # e.g. fields = BaseContentSerializer.Meta.fields + ('header_image', 'category', 'tags')

from .models import Promotion, CouponCode

class PromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promotion
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'total_uses_count')

class CouponCodeSerializer(serializers.ModelSerializer):
    # promotion = PromotionSerializer(read_only=True) # Can be nested if needed for GET
    promotion_id = serializers.PrimaryKeyRelatedField(
        queryset=Promotion.objects.all(), source='promotion', write_only=True
    )
    user_specific_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='user_specific', write_only=True, required=False, allow_null=True
    )
    user_specific = UserSerializer(read_only=True)


    class Meta:
        model = CouponCode
        fields = (
            'id', 'promotion', 'promotion_id', 'code', 'is_active',
            'uses_count', 'max_uses', 'valid_from', 'valid_to',
            'user_specific', 'user_specific_id', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'promotion', 'uses_count', 'created_at', 'updated_at', 'user_specific')
        # 'promotion' is read_only here because 'promotion_id' is used for writing.

    def to_representation(self, instance):
        """Add nested promotion data for GET requests."""
        representation = super().to_representation(instance)
        representation['promotion'] = PromotionSerializer(instance.promotion).data
        return representation


class CouponValidationRequestSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)
    # Optionally, pass context like cart_value, items, user_id (if not from request.user)
    # cart_value = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

class CouponValidationResponseSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    message = serializers.CharField()
    discount_type = serializers.CharField(allow_null=True)
    discount_value = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    coupon_id = serializers.IntegerField(allow_null=True)
    promotion_id = serializers.IntegerField(allow_null=True)
    # Potentially, the final discounted price if cart_value was provided.
    # discounted_amount = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)

from .models import TrackedEvent

class TrackedEventSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True) # Display user details, not just ID

    class Meta:
        model = TrackedEvent
        fields = (
            'id', 'event_type', 'user', 'timestamp',
            'session_id', 'ip_address', 'user_agent', 'data'
        )
        read_only_fields = fields # All fields are typically read-only as events are logged by the system

from .models import AffiliateProfile, Referral

class AffiliateProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True) # User details are read-only

    class Meta:
        model = AffiliateProfile
        fields = (
            'id', 'user', 'referral_code', 'balance', 'total_earned',
            'is_active', 'paypal_email', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'user', 'referral_code', 'balance', 'total_earned', 'created_at', 'updated_at')
        # is_active and paypal_email can be made writable by user or admin as needed.

class ReferralSerializer(serializers.ModelSerializer):
    referred_user = UserSerializer(read_only=True)
    affiliate_profile = AffiliateProfileSerializer(read_only=True) # Can show affiliate details

    class Meta:
        model = Referral
        fields = (
            'id', 'referred_user', 'referral_code_used', 'affiliate_profile',
            'timestamp', 'commission_earned', 'status', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'referred_user', 'affiliate_profile', 'timestamp', 'created_at', 'updated_at')
        # referral_code_used is set at creation.
        # commission_earned and status might be updated by system/admin.

class CreateReferralSerializer(serializers.Serializer):
    # Used when a new user signs up, potentially with a referral code.
    # The referred_user will be request.user (the new user).
    referral_code = serializers.CharField(max_length=20, required=True)
