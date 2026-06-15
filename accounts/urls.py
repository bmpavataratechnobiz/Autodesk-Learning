from django.urls import path
from . import views


urlpatterns = [
    path('login/', views.AutodeskLoginView.as_view(), name='autodesk_login'),
    path('callback/', views.AutodeskCallbackView.as_view(), name="autodesk_callback"),
]
