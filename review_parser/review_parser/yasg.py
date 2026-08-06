from django.urls import path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


schema_view = get_schema_view(
   openapi.Info(
      title="Review Parser API",
      default_version='v1',
      description="""
API для парсинга и получения отзывов с различных платформ (Яндекс, 2GIS, VL.RU).

**Основные эндпоинты:**
- `GET /api/common/reviews` — отзывы по ID филиала
- `GET /api/common/reviews_by_ip` — отзывы по IP (требуется Branch IP Mapping)

**Провайдеры отзывов:** yandex, 2gis, vlru
""",
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
   path(r'swagger(?P<format>\.json|\.yaml)', schema_view.without_ui(cache_timeout=0), name='schema-json'),
   path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
   path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]