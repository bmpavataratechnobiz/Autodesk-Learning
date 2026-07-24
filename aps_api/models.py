from django.utils import timezone
from datetime import timedelta
from django.db import models
from django_accounts.models import CustomUser
import uuid


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
        return f"{self.sheetNumber}  {self.version}"  



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
    

class AutodeskFolders(models.Model):
    project = models.ForeignKey(AutoDeskProject, on_delete=models.CASCADE, related_name="folders")
    folder_id = models.CharField(max_length=255)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children")
    name = models.CharField(max_length=255)
    is_root = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)
    object_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(null=True, blank=True)
    created_by = models.CharField(max_length=255, null=True, blank=True)
    created_by_name = models.CharField(max_length=255, null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.CharField(max_length=255, null=True, blank=True)
    updated_by_name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name




class AutodeskFolderMembers(models.Model):
    folder = models.ForeignKey(AutodeskFolders, on_delete=models.CASCADE, related_name="folder_members")
    autodesk_user = models.ForeignKey(AutodeskUser, on_delete=models.CASCADE, related_name="folder_users")
    subject_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    user_type = models.CharField(max_length=255)
    subject_status = models.CharField(max_length=255)
    subject_type = models.CharField(max_length=255)
    actions = models.JSONField(blank=True, null=True)
    inherit_actions = models.JSONField(blank=True, null=True)

    def __str__(self):
        return self.name


class AutodeskProjectFiles(models.Model):
    folder = models.ForeignKey(AutodeskFolders, on_delete=models.CASCADE, related_name="folder_files", blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    version_number = models.CharField(max_length=10, blank=True, null=True)
    version = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    created_by = models.CharField(max_length=255, blank=True, null=True)
    created_by_name = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    updated_by = models.CharField(max_length=255, blank=True, null=True)
    updated_by_name = models.CharField(max_length=255, blank=True, null=True)

    item_id = models.CharField(max_length=255, blank=True, null=True)
    current_file_id = models.CharField(max_length=255, blank=True, null=True)
    file = models.FileField(upload_to="autodesk_pdf_files/", blank=True, null=True)
    file_size_bytes = models.BigIntegerField(blank=True, null=True)
    is_deleted = models.BooleanField(blank=True, null=True)

    createdat = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updatedat = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return self.name
    

class AutodeskFileVersions(models.Model):
    autodesk_project_file = models.ForeignKey(AutodeskProjectFiles, on_delete=models.CASCADE, related_name="file_versions", blank=True, null=True)

    name = models.CharField(max_length=255, blank=True, null=True)
    version_number = models.CharField(max_length=10, blank=True, null=True)
    version = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    created_by = models.CharField(max_length=255, blank=True, null=True)
    created_by_name = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    updated_by = models.CharField(max_length=255, blank=True, null=True)
    updated_by_name = models.CharField(max_length=255, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)

    file_id = models.CharField(max_length=255, blank=True, null=True)
    file = models.FileField(upload_to="autodesk_pdf_files/", blank=True, null=True)
    file_size_bytes = models.BigIntegerField(blank=True, null=True)

    createdat = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updatedat = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return self.name
    

class SyncFolderData(models.Model):
    project = models.ForeignKey(AutoDeskProject, on_delete=models.CASCADE)
    sync_user = models.ForeignKey(AutodeskUser, on_delete=models.CASCADE, blank=True, null=True)

    folder_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    path = models.CharField(max_length=255, blank=True, null=True)
    last_sync_time = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return self.name
    

class RequestedVersionLinkRequest(models.Model):
    REQUEST_STATUS_CHOICES = [
        ("PENDING", "PENDING"),
        ("APPROVED", "APPROVED"),
        ("REJECTED", "REJECTED"),
        ("SEND", "SEND"),
    ]

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    scanned_file_version = models.ForeignKey(AutodeskFileVersions, on_delete=models.CASCADE, related_name="scanned_file_version_request")
    requested_file_version = models.ForeignKey(AutodeskFileVersions, on_delete=models.CASCADE, related_name="requested_file_version_request")
    email = models.EmailField()
    request_status = models.CharField(choices=REQUEST_STATUS_CHOICES, max_length=255, default="PENDING")
    requested_at = models.DateTimeField(blank=True, null=True)
    is_downloaded = models.BooleanField(default=False)
    downloaded_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.email
    

class RequestedSheetVersionRequest(models.Model):
    REQUEST_STATUS_CHOICES = [
        ("PENDING", "PENDING"),
        ("APPROVED", "APPROVED"),
        ("REJECTED", "REJECTED"),
        ("SEND", "SEND"),
    ]

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    scanned_sheet_version = models.ForeignKey(AutodeskSheets, on_delete=models.CASCADE, related_name="scanned_sheet_version_request")
    requested_sheet_version = models.ForeignKey(AutodeskSheets, on_delete=models.CASCADE, related_name="requested_sheet_version_request")
    email = models.EmailField()
    request_status = models.CharField(choices=REQUEST_STATUS_CHOICES, max_length=255, default="PENDING")
    requested_at = models.DateTimeField(blank=True, null=True)
    is_downloaded = models.BooleanField(default=False)
    downloaded_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.email
    

class Subscriptions(models.Model):
    SUBSCRIPTION_TYPE_CHOICES = (
        ("Free Trial", "Free Trial"),
        ("Basic", "Basic"),
        ("Standard", "Standard"),
        ("Premium", "Premium")
    )
    SUBSCRIPTION_TERM_CHOICES = (
        ("Free Trial", "Free Trial"),
        ("1 Month", "1 Month"),
        ("6 Month", "6 Month"),
        ("Yearly", "Yearly")
    )
    SCANS_CHOICES = (
        (10, 10),
        (30, 30),
        (50, 50),
        (100, 100)
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="sub_users")
    is_active = models.BooleanField(default=False)
    subscription_type = models.CharField(choices=SUBSCRIPTION_TYPE_CHOICES, max_length=50)
    subscription_term = models.CharField(choices=SUBSCRIPTION_TERM_CHOICES, max_length=50)
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    total_scans = models.IntegerField(choices=SCANS_CHOICES, blank=True, null=True)
    used_scans = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def remaining_scans(self):
        return max(self.total_scans - self.used_scans, 0)
    
    def save(self, *args, **kwargs):
        if not self.start_date:
            self.start_date = timezone.now()

        if not self.end_date:
            if self.subscription_term == "Free Trial":
                self.end_date = self.start_date + timedelta(days=14)
                self.total_scans = 10

            elif self.subscription_term == "1 Month":
                self.end_date = self.start_date + timedelta(days=30)
                self.total_scans = 30

            elif self.subscription_term == "6 Month":
                self.end_date = self.start_date + timedelta(days=180)
                self.total_scans = 50

            elif self.subscription_term == "Yearly":
                self.end_date = self.start_date + timedelta(days=365)
                self.total_scans = 100

        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.subscription_type





