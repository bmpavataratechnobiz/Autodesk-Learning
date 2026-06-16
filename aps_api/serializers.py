from rest_framework import serializers
from .models import AutodeskSheets, AutoDeskProject, AutodeskProjectMembers


class AutodeskSheetsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutodeskSheets
        fields = "__all__"


class AutodeskProjectMembersSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutodeskProjectMembers
        fields = "__all__"


class AutodeskProjectSerializer(serializers.ModelSerializer):
    members = AutodeskProjectMembersSerializer(source='project_members', read_only=True, many=True)

    class Meta:
        model = AutoDeskProject
        fields = ["id", "project_id", "name", "account", "hub_name", "hub_id", "members", "created_at"]