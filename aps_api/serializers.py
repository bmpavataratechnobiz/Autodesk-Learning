from rest_framework import serializers
from .models import AutodeskSheets, AutoDeskProject, AutodeskUser


class AutodeskSheetsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutodeskSheets
        fields = "__all__"


class AutodeskUsersSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutodeskUser
        fields = "__all__"


class AutodeskProjectSerializer(serializers.ModelSerializer):
    users = AutodeskUsersSerializer(many=True)

    class Meta:
        model = AutoDeskProject
        fields = ["id", "project_id", "name", "account", "hub_name", "hub_id", "users", "created_at"]