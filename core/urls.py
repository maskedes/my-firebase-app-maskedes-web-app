from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FirebaseLoginView, UserLogoutView, UserDetailView, UserProfileView,
    VideoViewSet, MarketingPageViewSet, BlogPostViewSet,
    PromotionViewSet, CouponCodeViewSet, ValidateCouponView,
    AffiliateProfileDetailView, RegisterReferralView,
    AffiliateProfileAdminViewSet, ReferralAdminViewSet
)

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'videos', VideoViewSet, basename='video')
router.register(r'pages', MarketingPageViewSet, basename='marketingpage')
router.register(r'posts', BlogPostViewSet, basename='blogpost')
router.register(r'promotions', PromotionViewSet, basename='promotion')
router.register(r'coupons', CouponCodeViewSet, basename='couponcode')
# Admin viewsets for affiliate system
router.register(r'admin/affiliate-profiles', AffiliateProfileAdminViewSet, basename='admin-affiliateprofile')
router.register(r'admin/referrals', ReferralAdminViewSet, basename='admin-referral')

# The API URLs are now determined automatically by the router.
urlpatterns = [
    # Auth specific paths
    path('auth/firebase-login/', FirebaseLoginView.as_view(), name='firebase-login'),
    path('auth/logout/', UserLogoutView.as_view(), name='user-logout'),
    path('auth/me/', UserDetailView.as_view(), name='user-detail'),
    path('auth/profile/', UserProfileView.as_view(), name='user-profile'),

    # Coupon validation specific path (not part of router)
    path('coupons/validate/', ValidateCouponView.as_view(), name='validate-coupon'),

    # Router paths for viewsets
    path('', include(router.urls)),
]
