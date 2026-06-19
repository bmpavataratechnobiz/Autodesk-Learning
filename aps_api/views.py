from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .tasks import sync_autodesk_data
# from .tasks2 import sync_autodesk_data
from .models import AutoDeskProject, AutodeskSheets, AutodeskUser, AutodeskAccount, AutodeskFileVersions, AutodeskProjectFiles
from rest_framework.response import Response
from rest_framework import status 
from .serializers import AutodeskSheetsSerializer, AutodeskProjectSerializer, AutodeskFileVersionSerializer



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
