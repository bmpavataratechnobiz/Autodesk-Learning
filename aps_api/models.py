from django.db import models
from django_accounts.models import CustomUser


class AutodeskUser(models.Model):
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, blank=True, null=True
    )
    autodesk_user_id = models.CharField(max_length=255, unique=True)
    email = models.EmailField(max_length=255)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.email}"


class AutodeskAccount(models.Model):
    autodesk_user = models.ForeignKey(
        AutodeskUser, on_delete=models.CASCADE, blank=True, null=True
    )
    hub_id = models.TextField(blank=True, null=True)
    hub_name = models.CharField(max_length=255, blank=True, null=True)
    hub_region = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.autodesk_user.name


class AutoDeskProject(models.Model):
    account = models.ForeignKey(
        AutodeskAccount,
        on_delete=models.CASCADE,
        related_name="aps_projects",
        blank=True,
        null=True,
    )
    project_id = models.TextField()
    hub_id = models.TextField()
    hub_name = models.CharField(max_length=255, blank=True, null=True)
    name = models.CharField(max_length=255)
    members = models.ManyToManyField(AutodeskUser, through="AutodeskProjectMembers", related_name='projects', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class AutodeskVersionSet(models.Model):
    version_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    issuanceDate = models.DateField(blank=True, null=True)
    createdAt = models.DateTimeField(blank=True, null=True)  
    createdBy = models.CharField(max_length=255, blank=True, null=True)
    createdByName = models.CharField(max_length=255, blank=True, null=True)
    updatedAt = models.DateTimeField(blank=True, null=True)
    updatedBy = models.CharField(max_length=255, blank=True, null=True)
    updatedByName = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name



class AutodeskSheets(models.Model):
    project = models.ForeignKey(AutoDeskProject, on_delete=models.CASCADE)

    title = models.CharField(max_length=255, blank=True, null=True)
    sheetId = models.CharField(max_length=255)
    sheetNumber = models.CharField(max_length=255)
    versionSet = models.ForeignKey(AutodeskVersionSet, on_delete=models.CASCADE, blank=True, null=True)
    version = models.IntegerField(blank=True, null=True)
    createdAt = models.DateTimeField(blank=True, null=True)
    createdBy = models.CharField(max_length=255, blank=True, null=True)
    createdByName = models.CharField(max_length=255, blank=True, null=True)
    updatedAt = models.DateTimeField(blank=True, null=True)
    updatedBy = models.CharField(max_length=255, blank=True, null=True)
    updatedByName =  models.CharField(max_length=255, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    is_current = models.BooleanField(default=False)
    deletedAt = models.DateTimeField(blank=True, null=True)
    deletedBy = models.CharField(max_length=255, blank=True, null=True)
    deletedByName = models.CharField(max_length=255, blank=True, null=True)
    file = models.FileField(upload_to="autodesk_sheets/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.project.name



class AutodeskProjectMembers(models.Model):
    project = models.ForeignKey(AutoDeskProject, on_delete=models.CASCADE, related_name="project_members")
    autodesk_user = models.ForeignKey(AutodeskUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    phone = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=30)
    company = models.CharField(max_length=255, blank=True, null=True)
    roles = models.JSONField(blank=True, null=True)
    access_levels = models.JSONField(blank=True, null=True)
    added_on = models.DateTimeField(blank=True, null=True)
    products = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f"{self.project} , {self.autodesk_user}, {self.status}"

