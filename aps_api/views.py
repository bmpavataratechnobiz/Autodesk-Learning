from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .tasks import get_hubs_projects_and_save
# from .tasks2 import get_hubs_projects_and_save
from .models import AutoDeskProject, AutodeskSheets, AutodeskUser
from rest_framework.response import Response
from rest_framework import status 
from .serializers import AutodeskSheetsSerializer, AutodeskProjectSerializer



class FetchHubProjectsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        task = get_hubs_projects_and_save.delay(request.user.id) 
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
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    

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
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class GetSheets(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        autodesk_user = AutodeskUser.objects.get(
            user=request.user
        )        
        projects = AutoDeskProject.objects.filter(
            users=autodesk_user
        )
        sheets = AutodeskSheets.objects.filter(
            project__in=projects
        )        
        serializer = AutodeskSheetsSerializer(sheets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
