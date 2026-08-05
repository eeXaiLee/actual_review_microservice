from django.urls import path
from .views import get_reviews, get_reviews_by_ip, get_videos_by_ip

urlpatterns = [
    path('reviews', get_reviews, name='get-reviews'),
    path('reviews_by_ip', get_reviews_by_ip, name='get-reviews-by-ip'),
    path('get_videos_by_ip', get_videos_by_ip, name='get-videos-by-ip'),
]