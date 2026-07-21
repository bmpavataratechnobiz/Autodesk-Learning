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

    path("save_data/project/<str:project_id>/", views.SaveFoldersData.as_view(), name="save_folders_data"),
    path("sync_folders_data/", views.SyncFoldersData.as_view(), name="sync_folders_data"), 

    path("file_data/<str:model_type>/<int:file_id>/", views.FileData.as_view(), name="file_Data"),
    path("send_latest_version_request/", views.SendLatestVersionLinkRequest.as_view(), name="send_latest_version_request"),
    path("fetch_version_requests/", views.FetchVersionRequests.as_view(), name="fetch_version_requests"),
    path("approve_request/<str:id>/", views.ApproveRequests.as_view(), name="approve_request"),
    path("reject_request/<str:id>/", views.RejectRequests.as_view(), name="reject_request"),
    # path("send_link_mail/", views.SendRequestedLinks.as_view(), name="send_link_mail"),
    path("download/<uuid:token>/", views.DownloadLatestVersion.as_view(), name="download_latest_version"),

]
