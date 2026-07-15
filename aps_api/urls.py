from django.urls import path
from .import views


urlpatterns = [
    path("fetch_data/", views.FetchHubProjectsView.as_view(), name="fetch_data"),
    path("fetch_sheets/", views.FetchSheets.as_view(), name="fetch_sheets"),
    path("deleted_sheets/", views.DeletedSheets.as_view(), name="deleted_sheets"),
    path("users_by_project/<str:project_id>/", views.FetchUsersByProject.as_view(), name="users_by_project"),
    path("get_sheets/", views.GetSheets.as_view(), name="get_sheets"),
    path("get_file_versions/<str:file_id>/", views.GetFileVersions.as_view(), name="get_file_versions"),
    path("fetch_file_versions/<str:item_id>/", views.FetchFileVersions.as_view(),name="fetch_file_versions"),


    # fetchhhhh
    path("fetch/", views.fetch, name="fetch"),

    path("fetch_regions/", views.FetchRegions.as_view(), name="fetch_regions"),
    path("fetch_hubs/<str:region>/", views.FetchHubs.as_view(), name="fetch_hubs"),
    path("fetch_projects/<str:hub_id>/", views.FetchProjects.as_view(), name="fetch_projects"),
    path("hub/<str:hub_id>/fetch_top_folders/<str:project_id>/", views.FetchTopFolders.as_view(), name="fetch_top_folders"),
    path("project/<str:project_id>/folder/<str:folder_id>/", views.FetchSubFolders.as_view(), name="fetch_sub_folders"),

    path("sync/project/<str:project_id>/", views.SyncFoldersData.as_view(), name="sync_folder_data"),

]
