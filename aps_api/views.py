import requests  # type:ignore
from django.shortcuts import get_object_or_404, render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
# from .tasks import sync_autodesk_data, sync_selected_folders
from .tasks2 import sync_autodesk_data, sync_selected_folders, send_link_mail
from .models import AutoDeskProject, AutodeskFolders, AutodeskSheets, AutodeskUser, AutodeskAccount, AutodeskFileVersions, AutodeskProjectFiles, RequestedVersionLinkRequest, SyncFolderData, RequestedSheetVersionRequest
from django_accounts.models import CustomUser
from rest_framework.response import Response
from rest_framework import status 
from .serializers import AutodeskSheetsSerializer, AutodeskProjectSerializer, AutodeskFileVersionSerializer,RequestedVersionLinkRequestSerializer
from django.db.models.functions import Cast
from django.db.models import IntegerField
from django.core.mail import send_mail
from django.urls import reverse
from django.http import FileResponse
from django.utils import timezone
from datetime import timedelta
from Autodesk_Project.settings import DEFAULT_FROM_EMAIL



class FetchHubProjectsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        task = sync_autodesk_data.delay(request.user.id) 
        return Response(
            {
                "task_id":task.id,
                "status":"task started"
            },status=202
        )



class FetchSheets(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sheets = AutodeskSheets.objects.filter(
            is_deleted=False
        )
        serializer = AutodeskSheetsSerializer(sheets, many=True)
        return Response({"objects":len(serializer.data), "results":serializer.data}, status=status.HTTP_200_OK)
    
    

class DeletedSheets(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        deleted_sheets = AutodeskSheets.objects.filter(
            is_deleted=True
        )
        serializer = AutodeskSheetsSerializer(deleted_sheets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    


class FetchUsersByProject(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        project_users = AutoDeskProject.objects.filter(
            project_id=project_id
        )
        serializer = AutodeskProjectSerializer(project_users, many=True)
        return Response({"objects":len(serializer.data),"results":serializer.data}, status=status.HTTP_200_OK)
    


class GetSheets(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        region_filter = request.query_params.get("region")
        project_filter = request.query_params.get("project")
        account_filter = request.query_params.get("account")

        autodesk_user = AutodeskUser.objects.get(
            user=request.user
        )        
        projects = AutoDeskProject.objects.filter(
            members=autodesk_user
        )
        
        if region_filter:      
            hub = AutodeskAccount.objects.get(
                hub_region=region_filter.upper()
            )            
            projects = projects.filter(
                hub_id=hub.hub_id
            )

        if project_filter: 
            projects = projects.filter(
                project_id=project_filter
            )

        if account_filter:
            projects = projects.filter(
                hub_id=account_filter
            )                         

        sheets = AutodeskSheets.objects.filter(
            project__in=projects
        )        
        serializer = AutodeskSheetsSerializer(sheets, many=True)
        return Response({"objects" : len(serializer.data), "results": serializer.data}, status=status.HTTP_200_OK)
    


class GetFileVersions(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        file = AutodeskProjectFiles.objects.get(
            id=file_id
        )

        file_versions = AutodeskFileVersions.objects.filter(
            autodesk_project_file=file
        )
        serializer = AutodeskFileVersionSerializer(file_versions, many=True)
        return Response({"objects":len(serializer.data), "results":serializer.data}, status=status.HTTP_200_OK)
    



class FetchFileVersions(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, item_id):
        file = AutodeskProjectFiles.objects.get(
            item_id=item_id
        )

        file_versions = AutodeskFileVersions.objects.filter(
            autodesk_project_file=file
        )
        serializer = AutodeskFileVersionSerializer(file_versions, many=True)
        return Response({"objects":len(serializer.data), "results":serializer.data}, status=status.HTTP_200_OK)


# ********************************************* 

def fetch(request):
    return render(request, "fetchhhh.html") 


class FetchRegions(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = CustomUser.objects.get(email=request.user.email)

        headers = {
            "Authorization": f"Bearer {user.access_token}"
        }

        hubs_response = requests.get(
            f"https://developer.api.autodesk.com/project/v1/hubs",
            headers=headers
        )

        if hubs_response.status_code != 200:
            return Response(hubs_response.json(), hubs_response.status_code)

        hubs_data = hubs_response.json().get("data", [])

        regions = [hub_data["attributes"]["region"] for hub_data in hubs_data ]

        return Response({"Objects":len(regions), "results":regions}, hubs_response.status_code)



class FetchHubs(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, region):

        user = CustomUser.objects.get(email=request.user.email)
        headers = {
            "Authorization": f"Bearer {user.access_token}"
        }

        hubs_response = requests.get(
            f"https://developer.api.autodesk.com/project/v1/hubs",
            headers=headers
        )  

        if hubs_response.status_code != 200:
            return Response(hubs_response.json(), hubs_response.status_code) 

        hubs_data = hubs_response.json().get("data", [])

        hubs = []
        for hub_data in hubs_data:
            if hub_data["attributes"]["region"] == region.upper():
                hubs.append(hub_data)

        return Response({"Objects":len(hubs), "results":hubs}, status=hubs_response.status_code)


class FetchProjects(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, hub_id):
        user = CustomUser.objects.get(email=request.user.email)

        headers = {
            "Authorization": f"Bearer {user.access_token}"
        }

        projects_response = requests.get(
            f"https://developer.api.autodesk.com/project/v1/hubs/{hub_id}/projects",
            headers=headers
        )

        if projects_response.status_code != 200:
            return Response(projects_response.json(), projects_response.status_code)
        
        projects_data = projects_response.json().get("data", [])
        return Response({"objects":len(projects_data), "results":projects_data}, projects_response.status_code)
    

class FetchTopFolders(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, hub_id, project_id):
        user = CustomUser.objects.get(email=request.user.email)

        headers = {
            "Authorization": f"Bearer {user.access_token}"
        }

        top_folders_response = requests.get(
            f"https://developer.api.autodesk.com/project/v1/hubs/{hub_id}/projects/{project_id}/topFolders",
            headers=headers
        )

        if top_folders_response.status_code != 200:
            return Response(top_folders_response.json(), top_folders_response.status_code)

        top_folders_data = top_folders_response.json().get("data", [])

        return Response({"objects":len(top_folders_data), "results":top_folders_data}, top_folders_response.status_code)
    

class FetchSubFolders(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id, folder_id):
        user = CustomUser.objects.get(email=request.user.email)

        headers = {
            "Authorization": f"Bearer {user.access_token}"
        }

        url = (
            f"https://developer.api.autodesk.com/data/v1/projects/{project_id}/folders/{folder_id}/contents"
        )

        results = []

        while url:
            response = requests.get(url, headers=headers)

            if response.status_code != 200:
                return Response(response.json(), response.status_code)

            response_data = response.json()

            for item in response_data.get("data", []):

                # Keep all folders
                if item["type"] == "folders":
                    results.append(item)

                # Keep only PDF files
                elif item["type"] == "items":
                    name = (
                        item.get("attributes", {})
                        .get("displayName")
                        or item.get("attributes", {})
                        .get("name", "")
                    )

                    if name.lower().endswith(".pdf"):
                        results.append(item)

            url = response_data.get("links", {}).get("next", {}).get("href")

        results.sort(
            key=lambda x: (
                x.get("attributes", {}).get("displayName")
                or x.get("attributes", {}).get("name", "")
            ).lower()
        )

        return Response(
            {
                "objects": len(results),
                "results": results
            },
            status=status.HTTP_200_OK
        )
    

class SaveFoldersData(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        user = CustomUser.objects.get(email=request.user.email)

        headers = {
            "Authorization": f"Bearer {user.access_token}"
        }
        
        project = AutoDeskProject.objects.get(project_id=project_id)
        autodesk_user = AutodeskUser.objects.get(user=user)
        folders = request.data.get("folders", [])

        for folder in folders:
            folder_response = requests.get(
                f"https://developer.api.autodesk.com/data/v1/projects/{project_id}/folders/{folder['folder_id']}",
                headers=headers
            )

            if folder_response.status_code != 200:
                return Response(folder_response.json(), folder_response.status_code)
             
            folder_data = folder_response.json().get("data", [])

            SyncFolderData.objects.update_or_create(
                project=project,
                folder_id=folder["folder_id"],
                defaults={
                    "sync_user":autodesk_user,
                    "name":folder_data["attributes"]["name"],
                    "path":folder["path"]
                }
            )

        return Response({"status":"sucess", "message":"data saved successfully"})
    

class SyncFoldersData(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sync_selected_folders.delay()

        return Response({"status":"success", "message":"folder sync started."})


class FileData(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, model_type, file_id):
        if model_type == "project":
            file = get_object_or_404(AutodeskProjectFiles, id=file_id)
        elif model_type == "version":
            file = get_object_or_404(AutodeskFileVersions, id=file_id)
            latest_file = (AutodeskFileVersions.objects.filter(
                autodesk_project_file=file.autodesk_project_file,
                is_deleted=False
            ).annotate(
                version_no=Cast("version_number", IntegerField())
            ).order_by(
                "-version_no"
            ).first())
    

        data = {
            "id":file.pk,
            "file_id":file.file_id,
            "name": file.name,
            "version": file.version,
            "version_number": file.version_number,
            "created_by": file.created_by_name,
            "updated_by": file.updated_by_name,
            "updated_at": file.updated_at,
            "file_size": file.file_size_bytes,
            "is_deleted": file.is_deleted,
        }

        if model_type == "project":
            data = data
        elif model_type == "version":
            if file.file_id != latest_file.file_id:
                latest_active_version = {
                    "id":latest_file.pk,
                    "file_id":latest_file.file_id,
                    "name": latest_file.name,
                    "version": latest_file.version,
                    "version_number": latest_file.version_number,
                    "created_by": latest_file.created_by_name,
                    "updated_by": latest_file.updated_by_name,
                    "updated_at": latest_file.updated_at,
                    "file_size": latest_file.file_size_bytes,
                    "is_deleted": latest_file.is_deleted,
                }
                data = {
                    "scanned_version":data,
                    "latest_active_version":latest_active_version
                }
            else:
                data = data

        return Response(data)
    

class SendLatestVersionLinkRequest(APIView):    
    def post(self, request):
        email = request.data.get("email")
        scanned_version_id =request.data.get("scanned_version_id")

        scanned_version_obj = AutodeskFileVersions.objects.get(
            id=scanned_version_id
        )

        latest_version_obj = (AutodeskFileVersions.objects.filter(
            autodesk_project_file=scanned_version_obj.autodesk_project_file, 
            is_deleted=False
        ).annotate(
            version_no=Cast("version_number", IntegerField())
        ).order_by("-version_no").first())

        RequestedVersionLinkRequest.objects.create(
            scanned_file_version=scanned_version_obj,
            requested_file_version=latest_version_obj,
            email=email,
            requested_at=timezone.now()
        )

        return Response(
            {"message": "Request sent successfully."},
            status=status.HTTP_200_OK
        )


class FetchVersionRequests(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        requested_objs = RequestedVersionLinkRequest.objects.all()

        serializer = RequestedVersionLinkRequestSerializer(requested_objs, many=True)
        return Response({"count":len(serializer.data), "results":serializer.data}, status=status.HTTP_200_OK)
    

class UpdateRequests(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        status = request.data.get("status")

        requested_obj = get_object_or_404(RequestedVersionLinkRequest, id=id)
        requested_obj.request_status = status
        requested_obj.save(update_fields=["request_status"])

        return Response(
            {"status":"success", "message":"request status updated!"}
        )
    

class SendRequestedLinks(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        approved_ids = RequestedVersionLinkRequest.objects.filter(
            request_status="APPROVED"
        ).values_list("id", flat=True)

        for id in approved_ids:
            send_link_mail.delay(id)

        return Response({"status":"success", "message":"mail sent successfully"})


class DownloadLatestVersion(APIView):
    def get(self, request, token):

        token_obj = get_object_or_404(
            RequestedVersionLinkRequest,
            token=token
        )

        if timezone.now() > token_obj.created_at + timedelta(days=3):
            return Response(
                {"message": "Download link has expired."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if token_obj.is_downloaded == True:
            return Response(
                {"message": "This download link has already been used."},
                status=status.HTTP_400_BAD_REQUEST
            )

        latest_version = token_obj.requested_file_version

        if not latest_version.file:
            return Response(
                {"message": "File not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        token_obj.is_downloaded = True
        token_obj.downloaded_at = timezone.now()
        token_obj.save(update_fields=["is_downloaded", "downloaded_at"])

        response = FileResponse(
            latest_version.file.open("rb"),
            as_attachment=True,
            filename=latest_version.name
        )

        return response


class SheetData(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, sheet_id):
        try:
            scanned_sheet_obj = AutodeskSheets.objects.get(id=sheet_id)
            sheet_number =  scanned_sheet_obj.sheetNumber
            latest_sheet_obj = (AutodeskSheets.objects.filter(
                sheetNumber=sheet_number
            ).annotate(
                version_no=Cast("version", IntegerField())
            ).order_by(
                "-version_no"
            ).first())

        except AutodeskSheets.DoesNotExist:
            return Response({"status":"error", "message":"data does not exist!"})
        
        scanned_sheet_data = {
            "title":scanned_sheet_obj.title,
            "sheetId":scanned_sheet_obj.sheetId,
            "sheetNumber":scanned_sheet_obj.sheetNumber,
            "versionSet":scanned_sheet_obj.versionSet.name,
            "version":scanned_sheet_obj.version,
            "createdByName":scanned_sheet_obj.createdByName,
            "updatedByName":scanned_sheet_obj.updatedByName,
            "is_current":scanned_sheet_obj.is_current,
        }

        if scanned_sheet_obj.sheetId == latest_sheet_obj.sheetId:        
            data={
                "scanned_sheet_data":scanned_sheet_data
            }
        else:
            latest_sheet_data = {
                "title":latest_sheet_obj.title,
                "sheetId":latest_sheet_obj.sheetId,
                "sheetNumber":latest_sheet_obj.sheetNumber,
                "versionSet":latest_sheet_obj.versionSet.name,
                "version":latest_sheet_obj.version,
                "createdByName":latest_sheet_obj.createdByName,
                "updatedByName":latest_sheet_obj.updatedByName,
                "is_current":latest_sheet_obj.is_current,
            }

            data = {
                "scanned_sheet_data":scanned_sheet_data,
                "latest_sheet_data":latest_sheet_data,
            }

        return Response(data)


class SendLatestSheetVersionRequest(APIView):
    def post(self, request):
        email = request.data.get("email")
        scanned_sheet_version_id =request.data.get("scanned_version_id")

        scanned_sheet_version_obj = AutodeskSheets.objects.get(
            id=scanned_sheet_version_id
        )

        latest_sheet_version_obj = (AutodeskSheets.objects.filter(
            sheetNumber=scanned_sheet_version_obj.sheetNumber, 
            is_deleted=False
        ).annotate(
            version_no=Cast("version", IntegerField())
        ).order_by("-version_no").first())

        RequestedSheetVersionRequest.objects.create(
            scanned_sheet_version=scanned_sheet_version_obj,
            requested_sheet_version=latest_sheet_version_obj,
            email=email,
            requested_at=timezone.now()
        )

        return Response(
            {"message": "Request sent successfully."},
            status=status.HTTP_200_OK
        )
