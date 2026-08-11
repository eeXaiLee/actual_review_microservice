from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import get_reviews, get_organization_reviews, get_videos, get_organization_videos

urlpatterns = [
    path('token', TokenObtainPairView.as_view(), name='token-obtain'),
    path('token/refresh', TokenRefreshView.as_view(), name='token-refresh'),
    path('reviews', get_reviews, name='get-reviews'),
    path('organization_reviews', get_organization_reviews, name='get-organization-reviews'),
    path('videos', get_videos, name='get-videos'),
    path('organization_videos', get_organization_videos, name='get-organization-videos'),
]