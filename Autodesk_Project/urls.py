
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView 
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/token/refresh/',  TokenRefreshView.as_view(), name="token_refresh"),

    # ACCOUNTS APP URL
    path('api/autodesk/', include('accounts.urls')),

    # APS_API APP URL
    path('api/aps/', include('aps_api.urls')),

    # DJANGO USER 
    path('api/auth/', include('django_accounts.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
