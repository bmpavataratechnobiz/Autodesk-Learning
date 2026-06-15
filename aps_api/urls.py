from django.urls import path
from .import views


urlpatterns = [
    path("fetch_data/", views.FetchHubProjectsView.as_view(), name="fetch_data"),
    path("fetch_sheets/", views.FetchSheets.as_view(), name="fetch_sheets"),
    path("deleted_sheets/", views.DeletedSheets.as_view(), name="deleted_sheets"),
    path("users_by_project/<str:project_id>/", views.FetchUsersByProject.as_view(), name="users_by_project"),
    path("get_sheets/", views.GetSheets.as_view(), name="get_sheets"),
]
