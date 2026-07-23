from django import forms
from django.contrib import admin
from .models import AutoDeskProject, AutodeskAccount, AutodeskUser, AutodeskSheets, AutodeskVersionSet, AutodeskProjectMembers, AutodeskProjectFiles, AutodeskFileVersions, AutodeskFolders, AutodeskFolderMembers, RequestedSheetVersionRequest, SyncFolderData, RequestedVersionLinkRequest, Subscriptions




class AutodeskUserAdmin(admin.ModelAdmin):
    model = AutodeskUser
    list_display = ['id', 'name', 'user', 'autodesk_user_id']
    list_display_links = ['id', 'name', 'user', 'autodesk_user_id']


class AutodeskSheetsAdmin(admin.ModelAdmin):
    model = AutodeskSheets
    list_display = ['id', 'sheetId', 'title', 'sheetNumber','version', 'versionSet', 'is_current', 'is_deleted']
    list_display_links = ['id', 'sheetId', 'title', 'sheetNumber', 'version', 'versionSet']
    # list_editable = ['file']


class AutodeskProjectMembersInline(admin.TabularInline):
    model = AutodeskProjectMembers
    fields = ['autodesk_user', 'status', 'company', 'added_on']
    extra = 0


class AutodeskProjectAdmin(admin.ModelAdmin):
    inlines = [AutodeskProjectMembersInline]
    model = AutoDeskProject
    list_display = ['name', 'hub_name', 'account']
    list_display_links = ['name', 'hub_name', 'account']


class AutodeskAccountAdmin(admin.ModelAdmin):
    model = AutodeskAccount
    list_display = [ 'hub_name', 'hub_region']
    list_display_links = ['hub_name', 'hub_region']


class AutodeskVersionSetAdmin(admin.ModelAdmin):
    model = AutodeskVersionSet
    list_display = ['version_id', 'name', 'issuanceDate']
    list_display_links = ['version_id', 'name', 'issuanceDate']


class AutodeskProjectMembersAdmin(admin.ModelAdmin):
    model = AutodeskProjectMembers
    list_display = ['project', 'autodesk_user', 'status', 'added_on']
    list_display_links = ['project', 'autodesk_user', 'status', 'added_on']


class AutodeskFileVersionsInline(admin.TabularInline):
    model = AutodeskFileVersions
    fields = ["name", "version", "created_at", "updated_at"]
    extra = 0


class AutodeskProjectFilesAdminForm(forms.ModelForm):
    class Meta:
        model = AutodeskProjectFiles
        fields = "__all__"
        widgets = {
            "item_id": forms.TextInput(attrs={
                "size": 100,
                "style": "width: 800px;"
            }),
            "current_file_id": forms.TextInput(attrs={
                "size": 100,
                "style": "width: 800px;"
            }),
        }


class AutodeskProjectFilesAdmin(admin.ModelAdmin):
    form = AutodeskProjectFilesAdminForm
    inlines = [AutodeskFileVersionsInline]
    model = AutodeskProjectFiles
    list_display = ["id", "name", "version", "version_number", "file", "is_deleted"]
    list_display_links = ["id", "name", "version", "version_number", "is_deleted"]


class AutodeskFileVersionsAdmin(admin.ModelAdmin):
    model = AutodeskFileVersions
    list_display =  ["id", "name", "version", "version_number", "file", "is_deleted"]
    list_display_links =  ["id", "name", "version", "version_number", "is_deleted"]
    list_filter = ["name", "is_deleted"]


class AutodeskFolderMembersInline(admin.TabularInline):
    model = AutodeskFolderMembers
    fields = ['autodesk_user', 'name', "subject_status"]
    extra = 0


class AutodeskFoldersAdmin(admin.ModelAdmin):
    inlines = [AutodeskFolderMembersInline]
    model = AutodeskFolders
    list_display = ["id", "is_root", "name", "parent", "object_count"]
    list_display_links = ["id", "is_root", "name", "parent", "object_count"]


class AutodeskFolderMembersAdmin(admin.ModelAdmin):
    model = AutodeskFolderMembers
    list_display = ["id", "folder", "autodesk_user", "name"]
    list_display_links = ["id", "folder", "autodesk_user", "name"]
    list_filter = ["autodesk_user", "name"]



class SyncFolderDataAdmin(admin.ModelAdmin):
    model = SyncFolderData
    list_display = ["id", "project", "name", "last_sync_time"]
    list_display_links = ["id", "project", "name", "last_sync_time"]


class RequestedVersionLinkRequestAdmin(admin.ModelAdmin):
    model = RequestedVersionLinkRequest
    list_display = ["id", "email", "token", "scanned_file_version", "requested_file_version", "request_status", "downloaded_at"]
    list_display_links = ["id", "email", "token", "scanned_file_version", "requested_file_version"]


class RequestedSheetVersionRequestAdmin(admin.ModelAdmin):
    model = RequestedSheetVersionRequest
    list_display = ["id", "email", "token", "scanned_sheet_version", "requested_sheet_version", "request_status", "downloaded_at"]
    list_display_links = ["id", "email", "token", "scanned_sheet_version", "requested_sheet_version"]


class SubscriptionAdmin(admin.ModelAdmin):
    model = Subscriptions
    list_display = ["id", "user", "subscription_type", "subscription_term", "total_scans", "used_scans", "start_date", "end_date"]
    list_display_links = ["id", "user", "subscription_type"]


admin.site.register(AutodeskUser, AutodeskUserAdmin)
admin.site.register(AutodeskAccount, AutodeskAccountAdmin)
admin.site.register(AutoDeskProject, AutodeskProjectAdmin)
admin.site.register(AutodeskSheets, AutodeskSheetsAdmin)
admin.site.register(AutodeskVersionSet, AutodeskVersionSetAdmin)
admin.site.register(AutodeskProjectMembers, AutodeskProjectMembersAdmin)
admin.site.register(AutodeskProjectFiles, AutodeskProjectFilesAdmin)
admin.site.register(AutodeskFileVersions, AutodeskFileVersionsAdmin)
admin.site.register(AutodeskFolders, AutodeskFoldersAdmin)
admin.site.register(AutodeskFolderMembers, AutodeskFolderMembersAdmin)
admin.site.register(SyncFolderData, SyncFolderDataAdmin)
admin.site.register(RequestedVersionLinkRequest, RequestedVersionLinkRequestAdmin)
admin.site.register(RequestedSheetVersionRequest, RequestedSheetVersionRequestAdmin)
admin.site.register(Subscriptions, SubscriptionAdmin)