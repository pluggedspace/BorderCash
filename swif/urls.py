from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
import app.urls
import kyc.urls
import iban.urls
import utils.urls
import invest.urls

# Create the schema view using get_schema_view from drf-yasg
schema_view = get_schema_view(
    openapi.Info(
        title="My API",
        default_version='v1',
        description="API documentation for my Django app",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@myapi.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(app.urls)),
    path('kyc/', include(kyc.urls)),
    path('iban/', include(iban.urls)),
    path('util/', include(utils.urls)),
    path('invest/', include(invest.urls)),

    # Swagger documentation
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    re_path(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),

    # ReDoc documentation
    re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

