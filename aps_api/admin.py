from django.contrib import admin
from .models import AutoDeskProject, AutodeskAccount, AutodeskUser, AutodeskSheets, AutodeskVersionSet




class AutodeskUserAdmin(admin.ModelAdmin):
    model = AutodeskUser
    list_display = ['id', 'name']


class AutodeskSheetsAdmin(admin.ModelAdmin):
    model = AutodeskSheets
    list_display = ['id', 'sheetId', 'sheetNumber','version', 'versionSet', 'is_current', 'is_deleted']
    list_display_links = ['id', 'sheetId', 'sheetNumber', 'version', 'versionSet']
    # list_editable = ['file']


class AutodeskProjectAdmin(admin.ModelAdmin):
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

admin.site.register(AutodeskUser, AutodeskUserAdmin)
admin.site.register(AutodeskAccount, AutodeskAccountAdmin)
admin.site.register(AutoDeskProject, AutodeskProjectAdmin)
admin.site.register(AutodeskSheets, AutodeskSheetsAdmin)
admin.site.register(AutodeskVersionSet, AutodeskVersionSetAdmin)