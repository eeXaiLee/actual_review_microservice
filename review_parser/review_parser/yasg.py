from django.urls import path, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


schema_view = get_schema_view(
   openapi.Info(
      title="Review & Video Parser API",
      default_version='v1',
      description="""
API для парсинга и получения отзывов с различных платформ (Яндекс, 2GIS, VL.RU), а также видео из YouTube-плейлистов.

Доступ — по JWT-токену: `POST /api/common/token` (логин/пароль клиента) →
`access`/`refresh`. Токен передаётся в заголовке `Authorization: Bearer <access>`.

**Основные эндпоинты:**
- `GET /api/common/reviews` — отзывы по ID филиала (только если филиал принадлежит организации клиента)
- `GET /api/common/organization_reviews` — отзывы по всем филиалам организации клиента
- `GET /api/common/videos` — видео по ID плейлиста (только если плейлист принадлежит организации клиента)
- `GET /api/common/organization_videos` — видео по всем YouTube-плейлистам организации клиента

**Провайдеры отзывов:** yandex, 2gis, vlru
**Провайдеры видео:** youtube
""",
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
   re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
   path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
   path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]