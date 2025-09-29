"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static

from django.urls import path, include

from rest_framework import permissions
from dj_rest_auth.views import PasswordResetView, PasswordResetConfirmView
from django.http import JsonResponse
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from users.views import ReviewerCustomRegisterView, VendorCustomRegisterView, ReviewerProfileView, VendorProfileView, ProtectedVendorDocView, UserProfileView, check_username_email, CookieTokenRefreshView, CustomVerifyEmailView, CustomResendEmailView, custom_logout
from shops.views import AnnouncementView, ReplyView, CategoryView, RegionView, ReviewView, ShopSearchView, ShopDetailView, LikeDetailView, vendor_dashboard, vendor_reviews, reply_to_review, vendor_shops, create_vendor_shop, update_vendor_shop, add_shop_category, delete_vendor_shop, reviewer_dashboard, reviewer_reviews, FavouriteView, PublicAnnouncementView, AnnouncementDetailView
from ml.ml import ReviewSummaryView, ReviewFlagAIView
from users.views import CustomLoginView
from django.http import HttpResponseNotFound

schema_view = get_schema_view(
    openapi.Info(
        title="My API",
        default_version='v1',
        description="Test description",
        terms_of_service="https://www.google.com/policies/terms/",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)


def api_root(request):
    return JsonResponse({"message": "API is working!"})


def disabled_view(request, *args, **kwargs):
    return HttpResponseNotFound()


urlpatterns = [
    path('', api_root),

    # Putting the login path first to override the default login view
    path('auth/login/', CustomLoginView.as_view(), name='rest_login'),
    path('auth/logout/', custom_logout, name='rest_logout'),
    path('auth/token/refresh/',
         CookieTokenRefreshView.as_view(), name='token_refresh'),
    # Disable the default user details view
    path('auth/user/', disabled_view, name='rest_user_details'),

    path('auth/check-username/', check_username_email, name='check-username'),
    path('auth/', include('dj_rest_auth.urls')),
    path('auth/register/vendor/',
         VendorCustomRegisterView.as_view(), name='vendor_register'),
    path('auth/register/reviewer/',
         ReviewerCustomRegisterView.as_view(), name='reviewer_register'),
    path('auth/account-confirm-email/<str:key>/',
         CustomVerifyEmailView.as_view(), name='account_confirm_email'),
    path('auth/resend-email/',
         CustomResendEmailView.as_view(), name='resend_email'),
    path('auth/password/reset/', PasswordResetView.as_view(), name='password_reset'),
    path('auth/password/reset/confirm/<str:uidb64>/<str:token>/',
         PasswordResetConfirmView.as_view(), name='password_reset_confirm'),

    path('auth/profile/', UserProfileView.as_view(), name='rest_profile_details'),
    path('auth/profile/reviewer/',
         ReviewerProfileView.as_view(), name='reviewer_profile'),
    path('auth/profile/vendor/',
         VendorProfileView.as_view(), name='vendor_profile'),
    path('auth/uen_doc/', ProtectedVendorDocView.as_view(),
         name='protected_uen_doc'),

    path('shops/categories/',
         CategoryView.as_view({'get': 'list'}), name='category-list'),
    path('shops/regions/',
         RegionView.as_view({'get': 'list'}), name='region-list'),
    path('shops/search/', ShopSearchView.as_view(), name='shop-search'),
    path(
        'shops/<int:shop_id>/reviews/',
        ReviewView.as_view({'get': 'list', 'post': 'create'}),
        name='shop-reviews-list'
    ),
    path('shops/reviews/flag/<int:review_id>/',
         ReviewFlagAIView.as_view(), name='shop-reviews-flag'),
    path('shops/<int:shop_id>/reviews/summary/',
         ReviewSummaryView.as_view(), name='shop-reviews-summary'),
    path('shops/<int:shop_id>/reply/',
         ReplyView.as_view({'get': 'list'}),
         name='shop-reviews-replies'
         ),

    path(
        'shops/<int:shop_id>/reviews/<int:pk>/',
        ReviewView.as_view({
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        }),
        name='shop-review-detail'
    ),
    path('shops/<int:shop_id>/', ShopDetailView.as_view(), name='shop-detail'),
    path('shops/<int:shop_id>/likes/<int:review_id>/',
         LikeDetailView.as_view(), name='like-detail'),
    path('shops/<int:shop_id>/announcements/',
         PublicAnnouncementView.as_view({'get': 'list'}),
         name='announcement-list'),

    # Vendor API endpoints
    path('vendor/dashboard/', vendor_dashboard, name='vendor_dashboard'),
    path('vendor/reviews/', vendor_reviews, name='vendor_reviews'),
    path('vendor/reviews/<int:review_id>/reply/',
         reply_to_review, name='reply_to_review'),
    path('vendor/shops/', vendor_shops, name='vendor_shops'),
    path('vendor/shops/create/', create_vendor_shop, name='create_vendor_shop'),
    path('vendor/shops/<int:shop_id>/update/',
         update_vendor_shop, name='update_vendor_shop'),
    path('vendor/shops/<int:shop_id>/delete/',
         delete_vendor_shop, name='delete_vendor_shop'),
    path('vendor/shops/<int:shop_id>/categories/',
         add_shop_category, name='add_shop_category'),
    path('vendor/shops/<int:shop_id>/announcements/',
         AnnouncementView.as_view({'get': 'list', 'post': 'create'}),
         name='vendor-announcement-list'),
    path('vendor/shops/<int:shop_id>/announcements/<int:announcement_id>/',
         AnnouncementDetailView.as_view(),
         name='vendor-announcement-detail'),

    # Reviewer API endpoints
    path('reviewer/dashboard/', reviewer_dashboard, name='reviewer_dashboard'),
    path('reviewer/reviews/', reviewer_reviews, name='reviewer_reviews'),
    path('reviewer/favourite/',
         FavouriteView.as_view({'get': 'list'}),
         name='favourite-list'),
    path('reviewer/favourite/<int:shop_id>/',
         FavouriteView.as_view(
             {'post': 'create',
              'delete': 'destroy'}),
         name='favourite-detail'),


    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0),
         name='schema-swagger-ui'),
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0),
         name='schema-json'),
    path('redoc/', schema_view.with_ui('redoc',
                                       cache_timeout=0), name='schema-redoc'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
