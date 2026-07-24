import requests     #type:ignore
from django.conf import settings
from django.core.mail import send_mail
from Autodesk_Project.settings import DEFAULT_FROM_EMAIL
from .models import AutodeskAccount, AutoDeskProject, AutodeskFileVersions, AutodeskProjectFiles, AutodeskUser, AutodeskSheets, AutodeskVersionSet, AutodeskProjectMembers, AutodeskFolders, AutodeskFolderMembers, RequestedVersionLinkRequest, Subscriptions, SyncFolderData, RequestedSheetVersionRequest
from celery import shared_task
from django.core.files.base import ContentFile
import time
from collections import defaultdict
from django.utils.dateparse import parse_datetime
from django_accounts.models import CustomUser
from datetime import datetime
from django.utils import timezone
from copy import copy
from django.core.signing import TimestampSigner


import traceback
import io
import qrcode   #type:ignore
from pypdf import PdfReader, PdfWriter, Transformation      #type:ignore
from reportlab.pdfgen import canvas     #type:ignore
from reportlab.lib.utils import ImageReader     #type:ignore
from reportlab.lib.colors import black      #type:ignore
from datetime import datetime, timedelta


APS_TOKEN_URL = "https://developer.api.autodesk.com/authentication/v2/token"
APS_HUBS_URL = "https://developer.api.autodesk.com/project/v1/hubs"
APS_USERINFO_URL = "https://api.userprofile.autodesk.com/userinfo"



def get_projects(headers, hub_id):
    projects = requests.get(
        f"https://developer.api.autodesk.com/project/v1/hubs/{hub_id}/projects",
        headers=headers
    )
    projects.raise_for_status()
    return projects.json().get("data", [])


def get_hubs(headers):
    hubs = requests.get(APS_HUBS_URL, headers=headers)
    hubs.raise_for_status()
    return hubs.json().get("data", [])


def get_or_create_versionSet(version_sets_map, version_id):
    version_set = version_sets_map.get(version_id)

    if not version_set:
        return None
    
    version_set_obj, _ = AutodeskVersionSet.objects.get_or_create(
        version_id=version_id,
        defaults={
            "name":version_set.get("name", None),
            "issuanceDate":version_set.get("issuanceDate", None),
            "createdAt":version_set.get("createdAt", None),
            "createdBy":version_set.get("createdBy", None),
            "createdByName":version_set.get("createdByName", None),
            "updatedAt":version_set.get("updatedAt", None),
            "updatedBy":version_set.get("updatedBy", None),
            "updatedByName":version_set.get("updatedByName", None)
        }
    )
    return version_set_obj


def update_current_sheet_flags(project):
    sheet_numbers = (AutodeskSheets.objects.filter(project=project).values_list("sheetNumber", flat=True).distinct())
    for sheet_number in sheet_numbers:
        AutodeskSheets.objects.filter(project=project, sheetNumber=sheet_number).update(is_current=False)

        latest_sheet = (AutodeskSheets.objects.filter(project=project, sheetNumber=sheet_number, is_deleted=False).order_by('-version').first())
        if latest_sheet:
            latest_sheet.is_current = True
            latest_sheet.save()


def build_sheet_version_counts(headers, project_id):
    version_sets_response = requests.get(
        f"https://developer.api.autodesk.com/construction/sheets/v1/projects/{project_id}/version-sets",
        headers=headers,
    )

    if version_sets_response.status_code != 200:
        return {}

    version_sets = version_sets_response.json().get("results", [])

    sheet_versions = {}

    for version_set in version_sets:
        version_set_id = version_set.get("id")

        if not version_set_id:
            continue

        response = requests.get(
            f"https://developer.api.autodesk.com/construction/sheets/v1/projects/{project_id}/sheets"
            f"?filter[versionSetId]={version_set_id}",
            headers=headers,
        )

        if response.status_code != 200:
            continue

        for sheet in response.json().get("results", []):

            number = sheet.get("number")

            if not number:
                continue

            sheet_versions.setdefault(number, set()).add(version_set_id)

    return {
        sheet_number: len(version_ids)
        for sheet_number, version_ids in sheet_versions.items()
    }


def build_sheet_version_ranks(headers, project_id):

    version_sets_response = requests.get(
        f"https://developer.api.autodesk.com/construction/sheets/v1/projects/{project_id}/version-sets",
        headers=headers,
    )

    if version_sets_response.status_code != 200:
        return {}

    version_sets = version_sets_response.json().get("results", [])

    version_set_lookup = {
        version_set["id"]: {
            "issuance_date": version_set.get("issuanceDate"),
            "created_at": version_set.get("createdAt"),
        }
        for version_set in version_sets
    }

    sheet_versions = {}

    for version_set in version_sets:

        version_set_id = version_set.get("id")

        if not version_set_id:
            continue

        response = requests.get(
            f"https://developer.api.autodesk.com/construction/sheets/v1/projects/{project_id}/sheets"
            f"?filter[versionSetId]={version_set_id}",
            headers=headers,
        )

        if response.status_code != 200:
            continue

        vs_info = version_set_lookup[version_set_id]

        for sheet in response.json().get("results", []):

            number = sheet.get("number")

            if not number:
                continue

            sheet_versions.setdefault(number, []).append(
                {
                    "sheet_id": sheet.get("id"),
                    "version_set_id": version_set_id,
                    "version_set_name": version_set.get("name"),
                    "issuance_date": vs_info.get("issuance_date"),
                    "created_at": vs_info.get("created_at"),
                }
            )

    result = {}

    for number, versions in sheet_versions.items():

        versions.sort(
            key=lambda x: (
                datetime.strptime(
                    x["issuance_date"], "%Y-%m-%d"
                ) if x.get("issuance_date") else datetime.min,
                datetime.fromisoformat(
                    x["created_at"].replace("Z", "+00:00")
                ) if x.get("created_at") else datetime.min,
            )
        )

        for index, version in enumerate(versions, start=1):

            result[version["sheet_id"]] = {
                "rank": index,
                "version_set_id": version["version_set_id"],
            }

    return result


def update_create_autodesk_project_memebers(headers, project_id, project):
    project_users_response = requests.get(
        f"https://developer.api.autodesk.com/construction/admin/v1/projects/{project_id}/users",
        headers=headers
    )

    project_users_data = project_users_response.json().get("results", [])

    for project_user_data in project_users_data:
        autodesk_user_obj, _ = AutodeskUser.objects.update_or_create(
            autodesk_user_id=project_user_data.get("autodeskId"),
            defaults={
                "email":project_user_data.get("email"),
                "name":project_user_data.get("name")
            }
        )
        
        first_name = project_user_data.get("name").split()[0]
        last_name = project_user_data.get("name").split()[1]
        user, _ = CustomUser.objects.update_or_create(
            email=project_user_data.get("email"),
            defaults={
                "first_name":first_name,
                "last_name":last_name,
            }
        )

        autodesk_user_obj.user = user
        autodesk_user_obj.save()

        project_member_obj, _ = AutodeskProjectMembers.objects.update_or_create(
            project = project,
            autodesk_user = autodesk_user_obj,
            defaults={
                "email":project_user_data.get("email"),
                "name":project_user_data.get("name"),
                "phone":(project_user_data.get("phone", {}) or {}).get("number"),
                "status":project_user_data.get("status"),
                "company":project_user_data.get("companyName"),
                "roles":project_user_data.get("roles"),
                "access_levels":project_user_data.get("accessLevels"),
                "added_on":parse_datetime(project_user_data.get("addedOn")),
                "products":project_user_data.get("products")
            }
        )


def sync_folder_tree(headers, hub_id, project_id, project_obj, parent_folder=None):
    """
    parent_folder=None -> fetch top folders
    parent_folder=folder_obj -> fetch child folders
    """
    count = 0
    if parent_folder is None:
        response = requests.get(
            f"https://developer.api.autodesk.com/project/v1/"
            f"hubs/{hub_id}/projects/{project_id}/topFolders",
            headers=headers
        )

        if response.status_code != 200:
            print(f"Failed to fetch top folders for project {project_id}")
            return

        folders = response.json().get("data", [])

        for folder in folders:
            attrs = folder.get("attributes", {})

            folder_obj, _ = AutodeskFolders.objects.update_or_create(
                folder_id=folder["id"],
                project=project_obj,
                defaults={
                    "parent": None,
                    "name": attrs.get("name"),
                    "created_at": attrs.get("createTime", ""),
                    "created_by": attrs.get("createUserId", ""),
                    "created_by_name": attrs.get("createUserName", ""),
                    "updated_at": attrs.get("lastModifiedTime", ""),
                    "updated_by": attrs.get("lastModifiedUserId", ""),
                    "updated_by_name": attrs.get("lastModifiedUserName", ""),
                    "object_count":attrs.get("objectCount"),
                    "hidden":attrs.get("hidden"),
                    "is_root":attrs.get("extension", {}).get("data", {}).get("isRoot"),
                },
            )

            folder_member_response = requests.get(
                f"https://developer.api.autodesk.com/bim360/docs/v1/projects/{project_id}/folders/{folder_obj.folder_id}/permissions",
                headers=headers
            )
            
            if not folder_member_response.status_code == 200:
                continue
            folder_member_data = folder_member_response.json()

            for data in folder_member_data:
                autodesk_user_obj, _ = AutodeskUser.objects.get_or_create(
                    autodesk_user_id=data.get("autodeskId"),
                    defaults={
                        "email":data.get("email"),
                        "name":data.get("name")
                    }
                )

                folder_member_obj, _ = AutodeskFolderMembers.objects.update_or_create(
                    folder = folder_obj,
                    autodesk_user = autodesk_user_obj,
                    defaults={
                        "subject_id":data.get("subjectId"),
                        "name":data.get("name"),
                        "email":data.get("email"),
                        "user_type":data.get("userType"),
                        "subject_status":data.get("subjectStatus"),
                        "subject_type":data.get("subjectType"),
                        "actions":data.get("actions"),
                        "inherit_actions":data.get("inheritActions"),
                    }
                )


            sync_folder_tree(
                headers,
                hub_id,
                project_id,
                project_obj,
                parent_folder=folder_obj,
            )

        return

    # Child folders with pagination
    next_url = (
        f"https://developer.api.autodesk.com/data/v1/projects/"
        f"{project_id}/folders/{parent_folder.folder_id}"
        f"/contents?filter[type]=folders"
    )

    while next_url:
        response = requests.get(next_url, headers=headers)

        if response.status_code != 200:
            print(
                f"Folder fetch failed. "
                f"Project: {project_id}, "
                f"Parent: {parent_folder.folder_id}"
            )
            return

        payload = response.json()

        folders = payload.get("data", [])

        for folder in folders:
            count += 1
            attrs = folder.get("attributes", {})

            folder_obj, _ = AutodeskFolders.objects.update_or_create(
                folder_id=folder["id"],
                project=project_obj,
                defaults={
                    "parent": parent_folder,
                    "name": attrs.get("name"),
                    "created_at": attrs.get("createTime", ""),
                    "created_by": attrs.get("createUserId", ""),
                    "created_by_name": attrs.get("createUserName", ""),
                    "updated_at": attrs.get("lastModifiedTime", ""),
                    "updated_by": attrs.get("lastModifiedUserId", ""),
                    "updated_by_name": attrs.get("lastModifiedUserName", ""),
                    "object_count":attrs.get("objectCount"),
                    "hidden":attrs.get("hidden"),
                    "is_root":False,
                },
            )

            folder_member_response = requests.get(
                f"https://developer.api.autodesk.com/bim360/docs/v1/projects/{project_id}/folders/{folder_obj.folder_id}/permissions",
                headers=headers
            )

            print(f"folder : {folder_obj.name} | status : {folder_member_response.status_code}")

            if not folder_member_response.status_code == 200:
                continue
            folder_member_data = folder_member_response.json()

            for data in folder_member_data:
                autodesk_user_obj, _ = AutodeskUser.objects.get_or_create(
                    autodesk_user_id=data.get("autodeskId"),
                    defaults={
                        "email":data.get("email"),
                        "name":data.get("name")
                    }
                )

                folder_member_obj, _ = AutodeskFolderMembers.objects.update_or_create(
                    folder = folder_obj,
                    autodesk_user = autodesk_user_obj,
                    defaults={
                        "subject_id":data.get("subjectId"),
                        "name":data.get("name"),
                        "email":data.get("email"),
                        "user_type":data.get("userType"),
                        "subject_status":data.get("subjectStatus"),
                        "subject_type":data.get("subjectType"),
                        "actions":data.get("actions"),
                        "inherit_actions":data.get("inheritActions"),
                    }
                )
            
            print(
                f"Saved Folder: {folder_obj.name} | "
                f"Parent: {parent_folder.name if parent_folder else 'ROOT'} | ",
                f"Count : {count} | ",
                f"Members : {folder_member_data}" 
            )

            # Recursively fetch children
            sync_folder_tree(
                headers,
                hub_id,
                project_id,
                project_obj,
                parent_folder=folder_obj,
            )

        next_url = (
            payload.get("links", {})
            .get("next", {})
            .get("href")
        )


@shared_task
def sync_project_folders(headers, hub_id, project_id):
    project_obj = AutoDeskProject.objects.get(project_id=project_id)

    sync_folder_tree(headers, hub_id, project_id, project_obj, parent_folder=None)

    return f"Folders synced for {project_obj.name}"


def stamp_pdf_with_qr(pdf_bytes, qr_url):
    # ---------------- Generate QR ----------------
    qr = qrcode.make(qr_url)

    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    qr_image = ImageReader(qr_buffer)

    # ---------------- Read PDF ----------------
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()

    for page in reader.pages:

        original_page = copy(page)

        # Normalize rotation
        if original_page.rotation:
            original_page.transfer_rotation_to_content()

        # Remove tiny original bottom border
        original_page.mediabox.lower_left = (
            original_page.mediabox.left,
            original_page.mediabox.bottom + 2
        )

        width = float(original_page.mediabox.width)
        height = float(original_page.mediabox.height)

        # ==========================================================
        # Dynamic scaling based on page size
        # ==========================================================

        shortest_side = min(width, height)

        qr_size = int(shortest_side * 0.075)
        qr_size = max(80, min(qr_size, 180))

        # Distance between drawing and QR (smaller = closer)
        top_gap = -10

        # Distance between QR and bottom edge (larger = more space)
        bottom_gap = 10

        # Left/right margin
        margin = int(qr_size * 0.20)

        # Total footer height
        footer_height = qr_size + top_gap + bottom_gap

        # QR position
        qr_y = bottom_gap

        font_size = max(10, int(qr_size * 0.14))

        # ==========================================================

        new_page = writer.add_blank_page(
            width,
            height + footer_height
        )

        new_page.merge_transformed_page(
            original_page,
            Transformation().translate(
                tx=0,
                ty=footer_height
            )
        )

        # ----------------------------------------------------------
        # Hide original bottom border
        # ----------------------------------------------------------

        white_overlay = io.BytesIO()

        c = canvas.Canvas(
            white_overlay,
            pagesize=(width, height + footer_height)
        )

        c.setFillColorRGB(1, 1, 1)

        c.rect(
            0,
            footer_height - top_gap - 1,
            width,
            2,
            stroke=0,
            fill=1
        )

        c.save()

        white_overlay.seek(0)

        new_page.merge_page(
            PdfReader(white_overlay).pages[0]
        )

        # ----------------------------------------------------------
        # Draw footer
        # ----------------------------------------------------------

        overlay = io.BytesIO()

        c = canvas.Canvas(
            overlay,
            pagesize=(width, height + footer_height)
        )

        # Left QR
        c.drawImage(
            qr_image,
            margin,
            qr_y,
            qr_size,
            qr_size
        )

        # Right QR
        c.drawImage(
            qr_image,
            width - qr_size - margin,
            qr_y,
            qr_size,
            qr_size
        )

        stamp_text = (
            f"Stamped by QR Verifier on "
            f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )

        c.setFont("Helvetica", font_size)

        text_width = c.stringWidth(
            stamp_text,
            "Helvetica",
            font_size
        )

        text_y = qr_y + (qr_size - font_size) / 2

        c.drawString(
            (width - text_width) / 2,
            text_y,
            stamp_text
        )

        c.save()

        overlay.seek(0)

        new_page.merge_page(
            PdfReader(overlay).pages[0]
        )

    output = io.BytesIO()

    writer.write(output)

    return output.getvalue()


@shared_task
def download_sheet_pdf(headers, project_id, sheet_id, sheet_number, upload_file_name, sheet_db_id):
    payload = {
        "sheets": [sheet_id],
        "options": {
            "outputFileName": upload_file_name
        }
    }

    try:
        export_response = requests.post(
            f"https://developer.api.autodesk.com/construction/sheets/v1/projects/{project_id}/exports",
            headers=headers,
            json=payload
        )

        if export_response.status_code != 202:
            print(f"Export failed for {sheet_id}")
            return

        export_job_id = export_response.json()["id"]

        download_url = None

        for _ in range(12):
            status_response = requests.get(
                f"https://developer.api.autodesk.com/construction/sheets/v1/projects/{project_id}/exports/{export_job_id}",
                headers=headers
            )

            status_data = status_response.json()

            if status_data.get("status") == "successful":
                download_url = status_data["result"]["output"]["signedUrl"]
                break

            time.sleep(5)

        if not download_url:
            print(f"Export timeout for {sheet_id}")
            return

        pdf_resp = requests.get(download_url)

        if pdf_resp.status_code != 200:
            print(f"Download failed for {sheet_id}")
            return

        sheet_obj = AutodeskSheets.objects.get(id=sheet_db_id)

        qr_url = (
            f"http://192.168.1.7:8000/api/aps/sheet_data/{sheet_obj.id}/"
        )

        stamped_pdf = stamp_pdf_with_qr(
            pdf_resp.content,
            qr_url
        )

        sheet_obj.file.save(
            f"{sheet_number}.pdf",
            ContentFile(stamped_pdf),
            save=True
        )

        print(f"SHEET saved for {sheet_number}")

    except Exception as e:
        print(f"PDF task failed: {e}")


@shared_task
def download_project_file(headers, project_id, file_version_urn, file_db_id, file_name, model_type):
    print(f"\n==================== {file_name} ====================")
    payload = {
        "options": {
            "outputFileName": file_name
        },
        "fileVersions": [
            file_version_urn
        ]
    }

    try:
        print("Creating Autodesk export...")

        export_response = requests.post(
            f"https://developer.api.autodesk.com/construction/files/v1/projects/{project_id}/exports",
            headers=headers,
            json=payload
        )

        print(f"Export API Status: {export_response.status_code}")

        if export_response.status_code != 202:
            print(export_response.text)
            return {
                "status": "failed",
                "file": file_name,
                "reason": "export_failed"
            }

        export_id = export_response.json()["id"]

        print(f"Export ID: {export_id}")

        download_url = None

        for i in range(12):

            status_response = requests.get(
                f"https://developer.api.autodesk.com/construction/files/v1/projects/{project_id}/exports/{export_id}",
                headers=headers
            )

            status_data = status_response.json()

            print(f"Poll {i + 1}: {status_data.get('status')}")

            if status_data.get("status") == "successful":
                download_url = (
                    status_data
                    .get("result", {})
                    .get("output", {})
                    .get("signedUrl")
                )
                break

            time.sleep(5)

        if not download_url:
            print("Export timed out.")
            return {
                "status": "failed",
                "file": file_name,
                "reason": "timeout"
            }

        print("Downloading PDF...")

        file_response = requests.get(download_url)

        print(
            f"Download Status: {file_response.status_code}, "
            f"Content-Type: {file_response.headers.get('Content-Type')}, "
            f"Size: {len(file_response.content)} bytes"
        )

        if file_response.status_code != 200:
            return {
                "status": "failed",
                "file": file_name,
                "reason": "download_failed"
            }

        print("Fetching database object...")

        if model_type == "project_file":
            file_obj = AutodeskProjectFiles.objects.get(id=file_db_id)
            qr_url = f"http://192.168.1.9:8000/api/aps/file_data/project/{file_obj.id}/"
        else:
            file_obj = AutodeskFileVersions.objects.get(id=file_db_id)
            qr_url = f"http://192.168.1.9:8000/api/aps/file_data/version/{file_obj.id}/"

        print(f"QR URL: {qr_url}")

        print("Stamping PDF...")

        stamped_pdf = stamp_pdf_with_qr(
            file_response.content,
            qr_url
        )

        print(f"Stamped PDF Size: {len(stamped_pdf)} bytes")

        print("Saving PDF...")

        file_obj.file.save(
            file_name,
            ContentFile(stamped_pdf),
            save=True
        )

        print(f"SUCCESS: {file_name}")

        return {
            "status": "success",
            "file": file_name
        }

    except Exception:
        print(f"\nERROR while processing: {file_name}")
        traceback.print_exc()

        return {
            "status": "failed",
            "file": file_name,
            "reason": "exception"
        }


def update_create_project_files(headers, project_id, project):
    top_folders_response = requests.get(
        f"https://developer.api.autodesk.com/project/v1/hubs/b.3a470ff8-7c50-4178-832a-121d8316a07e/projects/{project_id}/topFolders",
        headers=headers
    )
    top_folders_data = top_folders_response.json().get("data", [])
    if not top_folders_data:
        print(f"No top folders found for project: {project.name}")
        return
    top_folders_id = top_folders_data[0].get("id")
    print("Project : ", project.name)
    print("top_folders_id : ", top_folders_id)

    drawings_response = requests.get(
        f"https://developer.api.autodesk.com/data/v1/projects/{project_id}/folders/{top_folders_id}/contents",
        headers=headers
    )
    drawings_id = None
    for folder in drawings_response.json().get("data", []):
        if "Drawings" == folder.get("attributes", {}).get("name", ""):
            drawings_id = folder.get("id")
            break    
    print("drawings_id : ", drawings_id)

    consumed_response = requests.get(
        f"https://developer.api.autodesk.com/data/v1/projects/{project_id}/folders/{drawings_id}/contents",
        headers=headers
    )
    consumed_id = None
    for folder in consumed_response.json().get("data", []):
        if folder.get("attributes", {}).get("name") == "Consumed":
            consumed_id = folder.get("id")
            break
    print("consumed_id : ", consumed_id)

    sub_consumed_response = requests.get(
        f"https://developer.api.autodesk.com/data/v1/projects/{project_id}/folders/{consumed_id}/contents",
        headers=headers
    )
    sub_consumed_id = None
    for folder in sub_consumed_response.json().get("data", []):
        if folder.get("attributes", {}).get("name") == "Consumed":
            sub_consumed_id = folder.get("id")
            break
    print("sub_consumed_id : ", sub_consumed_id)

    files_response = requests.get(
        f"https://developer.api.autodesk.com/data/v1/projects/{project_id}/folders/{sub_consumed_id}/contents?filter[type]=items&includeHidden=true",
        headers=headers
    )
    files_data = files_response.json().get("data", [])  
    pdfs_data = []
    for data in files_data:
        filename = data.get("attributes", {}).get("extension", {}).get("data", {}).get("sourceFileName", "")
        if filename.lower().endswith(".pdf"):
            pdfs_data.append(data)

    for data in pdfs_data:
        item_id = data.get("id")

        # create-store current file data      
        current_file_reponse = requests.get(
            f"https://developer.api.autodesk.com/data/v1/projects/{project_id}/items/{item_id}/tip",
            headers=headers
        )
        current_file_data = current_file_reponse.json().get("data", [])

        current_attributes = current_file_data.get("attributes", {})
        is_deleted = False
        name = ""
        if current_attributes.get("extension", {}).get("type") == "versions:autodesk.core:Deleted":
            name = current_attributes.get("extension", {}).get("data", {}).get("originalName")
            is_deleted = True
            print("name : ", name)
            print("deleted : ", is_deleted)
        else:
            name = current_attributes.get("name")

        autodesk_project_file, _ = AutodeskProjectFiles.objects.update_or_create(            
            item_id=item_id, 
            project=project,
            defaults={
                "current_file_id":current_file_data.get("id"),
                "name":name,
                "version_number":current_attributes.get("versionNumber"),
                "created_at":current_attributes.get("createTime"),
                "created_by":current_attributes.get("createUserId"),
                "created_by_name":current_attributes.get("createUserName"),
                "updated_at":current_attributes.get("lastModifiedTime"),
                "updated_by":current_attributes.get("lastModifiedUserId"),
                "updated_by_name":current_attributes.get("lastModifiedUserName"),
                "file_size_bytes":current_attributes.get("storageSize"),
                "version":current_attributes.get("extension", {}).get("data", {}).get("revisionDisplayLabel", ""),
                "is_deleted":is_deleted
            }
        )
        print("Current File Name : ", autodesk_project_file.name)
    
        file_version_urn = current_file_data.get("id")
        file_db_id = autodesk_project_file.pk
        file_name = autodesk_project_file.name
        model_type = "project_file"
        download_project_file.delay(headers, project_id, file_version_urn, file_db_id, file_name, model_type)


        # create-store file versions data
        file_versions_response = requests.get(
            f"https://developer.api.autodesk.com/data/v1/projects/{project_id}/items/{item_id}/versions",
            headers=headers
        )
        file_versions_data = file_versions_response.json().get("data", [])
        
        for file_version_data in file_versions_data: 
            versions_attribute = file_version_data.get("attributes", {})

            name = ""
            is_deleted = False
            if versions_attribute.get("extension", {}).get("type") == "versions:autodesk.core:Deleted":
                name = versions_attribute.get("extension", {}).get("data", {}).get("originalName")
                is_deleted = True
            else:
                name = versions_attribute.get("name")

            file_version, _ = AutodeskFileVersions.objects.update_or_create(
                file_id=file_version_data.get("id"),
                autodesk_project_file=autodesk_project_file,
                defaults={
                    "name":name,
                    "version_number":versions_attribute.get("versionNumber"),
                    "created_at":versions_attribute.get("createTime"),
                    "created_by":versions_attribute.get("createUserId"),
                    "created_by_name":versions_attribute.get("createUserName"),
                    "updated_at":versions_attribute.get("lastModifiedTime"),
                    "updated_by":versions_attribute.get("lastModifiedUserId"),
                    "updated_by_name":versions_attribute.get("lastModifiedUserName"),
                    "file_size_bytes":versions_attribute.get("storageSize"),
                    "version":versions_attribute.get("extension", {}).get("data", {}).get("revisionDisplayLabel", ""),
                    "is_deleted":is_deleted
                }
            )  

            print("For File Versions : ", autodesk_project_file.name)
            
            file_version_urn = file_version_data.get("id")
            file_db_id = file_version.pk
            file_name = file_version.name
            model_type = "file_version"
            download_project_file.delay(headers, project_id, file_version_urn, file_db_id, file_name, model_type)




# *********************************************************** MAIN FUNCTION ***********************************************************
@shared_task
def sync_autodesk_data(user_id):
    try:
        user = CustomUser.objects.get(id=user_id)

        headers = {
            "Authorization": f"Bearer {user.access_token}"
        }

        autodesk_user = AutodeskUser.objects.get(
            user=user
        )

        # +++++++++++++++++++++++++++++++++++++++++++++ storing hub +++++++++++++++++++++++++++++++++++++++++++++
        hubs_data = get_hubs(headers)
        for hub_data in hubs_data:        
            account, _ = AutodeskAccount.objects.update_or_create(
                autodesk_user=autodesk_user,
                hub_id=hub_data.get("id"),
                defaults={
                    "hub_name": hub_data.get("attributes", []).get("name"),
                    "hub_region": hub_data.get("attributes", []).get("region")
                }
            )
            hub_id = hub_data.get("id")

            # +++++++++++++++++++++++++++++++++++++++++++++ storing projects +++++++++++++++++++++++++++++++++++++++++++++
            version_sets_map = None

            projects_data = get_projects(headers, hub_id)
            for project_data in projects_data:
                project_id = project_data.get("id")

                project, _ = AutoDeskProject.objects.update_or_create(
                    account=account,
                    project_id=project_id,
                    defaults={
                        "hub_id": hub_id,
                        "hub_name": hub_data.get("attributes", []).get("name"),
                        "name": project_data.get("attributes", []).get("name"),
                    }
                )

                # +++++++++++++++++++++++++++++++++++++++++++++ storing projects folders +++++++++++++++++++++++++++++++++++++++++++++
                # sync_project_folders(headers, hub_id, project_id)

                # +++++++++++++++++++++++++++++++++++++++++++++ storing projects members +++++++++++++++++++++++++++++++++++++++++++++
                # update_create_autodesk_project_memebers(headers, project_id, project) 

                # +++++++++++++++++++++++++++++++++++++++++++++ storing projects files and data +++++++++++++++++++++++++++++++++++++++++++++
                # update_create_project_files(headers, project_id, project)               
                
                # ++++++++++++++++++++++++++++++++++++++++ version set map and version tracker +++++++++++++++++++++++++++++++++++++++
                version_sets_response = requests.get(
                    f"https://developer.api.autodesk.com/construction/sheets/v1/projects/{project_id}/version-sets",
                    headers=headers
                )

                if version_sets_response.status_code != 200:
                    continue

                version_sets_data = version_sets_response.json().get("results", [])

                version_sets_map = {
                    version_set["id"]: version_set
                    for version_set in version_sets_data
                }

                version_counts = build_sheet_version_counts(headers, project_id)
                version_ranks = build_sheet_version_ranks(headers, project_id)

                deleted_sheets_response = requests.get(
                    f"https://developer.api.autodesk.com/construction/sheets/v1/projects/{project_id}/sheets?isDeleted=true",
                    headers=headers
                )

                deleted_sheets_data = []

                if deleted_sheets_response.status_code == 200:
                    deleted_sheets_data = deleted_sheets_response.json().get("results", [])

                    for sheet in deleted_sheets_data:
                        version_id = sheet["versionSet"]["id"]

                        if version_id not in version_sets_map:
                            version_sets_map[version_id] = sheet["versionSet"]

                # +++++++++++++++++++++++++++++++++++++++++++++ storing sheets +++++++++++++++++++++++++++++++++++++++++++++
                sheets = requests.get(
                    f"https://developer.api.autodesk.com/construction/sheets/v1/projects/{project_id}/sheets",
                    headers=headers
                )

                if sheets.status_code != 200:
                    print(
                        f"Skipping project {project_id}. "
                        f"Sheets API returned {sheets.status_code}"
                    )
                    continue

                sheets_data = sheets.json().get('results', [])                         
                for sheet_data in sheets_data:
                    sheet_id = sheet_data["id"]
                    version_id = sheet_data["versionSet"]["id"]
                    sheet_number = sheet_data["number"]    
                    version_set = get_or_create_versionSet(version_sets_map, version_id)

                    sheet_obj, _ = AutodeskSheets.objects.update_or_create(
                        sheetId=sheet_data["id"],
                        sheetNumber=sheet_number,
                        defaults={
                            "project":project,
                            "title":sheet_data["title"],
                            "versionSet":version_set,
                            "version":0,
                            "createdAt":sheet_data["createdAt"],
                            "createdBy":sheet_data["createdBy"],
                            "createdByName":sheet_data["createdByName"],
                            "updatedAt":sheet_data["updatedAt"],
                            "updatedBy":sheet_data["updatedBy"],
                            "updatedByName":sheet_data["updatedByName"],
                            "is_deleted":False,
                            "is_current":sheet_data.get("isCurrent"),                           
                        }
                    )
                    # +++++++++++++++++++++++++++++++++++++++++++++ storing sheet file +++++++++++++++++++++++++++++++++++++++++++++                   
                    download_sheet_pdf.delay(headers, project_id, sheet_id, sheet_data["number"], sheet_data["uploadFileName"], sheet_obj.id)

                              
                # +++++++++++++++++++++++++++++++++++++++++++++++++++ STORE DELETED SHEETS DATA ++++++++++++++++++++++++++++++++++++++++++++++++++++++
                for deleted_sheet_data in deleted_sheets_data:
                    sheet_id = deleted_sheet_data["id"]
                    version_id = deleted_sheet_data["versionSet"]["id"]
                    version_set = get_or_create_versionSet(version_sets_map, version_id)

                    sheet_obj, _ = AutodeskSheets.objects.update_or_create(
                        sheetId=deleted_sheet_data["id"],
                        defaults={
                            "project":project,
                            "title":deleted_sheet_data["title"],
                            "sheetNumber":deleted_sheet_data["number"],
                            "versionSet":version_set,
                            "version":0,
                            "createdAt":deleted_sheet_data.get("createdAt", None),
                            "createdBy":deleted_sheet_data.get("createdBy", None),
                            "createdByName":deleted_sheet_data.get("createdByName", None),
                            "updatedAt":deleted_sheet_data.get("updatedAt", None),
                            "updatedBy":deleted_sheet_data.get("updatedBy", None),
                            "updatedByName":deleted_sheet_data.get("updatedByName", None),
                            "is_deleted":deleted_sheet_data.get("deleted", None),
                            "is_current":False,
                            "deletedAt":deleted_sheet_data["deletedAt"],
                            "deletedBy":deleted_sheet_data["deletedBy"],
                            "deletedByName":deleted_sheet_data["deletedByName"],                            
                        }
                    )

                # +++++++++++++++++++++++++++++++++++++++++++++ UPDATE VERSION COUNTS +++++++++++++++++++++++++++++++++++++++++++++
                for sheet_number, count in version_counts.items():

                    AutodeskSheets.objects.filter(
                        project=project,
                        sheetNumber=sheet_number,
                        is_current=True,
                    ).update(
                        version=count
                    )


                # +++++++++++++++++++++++++++++++++++++++++++++ UPDATE VERSION RANKS +++++++++++++++++++++++++++++++++++++++++++++
                for sheet_id, data in version_ranks.items():

                    sheet = AutodeskSheets.objects.filter(
                        project=project,
                        sheetId=sheet_id,
                    ).first()

                    if not sheet:
                        continue

                    sheet.version = data["rank"]

                    sheet.versionSet = get_or_create_versionSet(
                        version_sets_map,
                        data["version_set_id"],
                    )

                    sheet.save(
                        update_fields=[
                            "version",
                            "versionSet",
                        ]
                    )

                # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ updates -> latest updated sheet is current if multiple ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                update_current_sheet_flags(project)
        
        return {"status": "success"}

    except AutodeskAccount.DoesNotExist:
        return {"status": "error", "message": "Autodesk account not found"}

    except Exception as e:
        return {"status": "error", "message": str(e)}
    



# ***************************************************************** sync *****************************************************************
from celery import chord

def sync_folder_recursive(headers, project, parent, folder_id, download_tasks):

    url = f"https://developer.api.autodesk.com/data/v1/projects/{project.project_id}/folders/{folder_id}/contents?includeHidden=true"

    while url:

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(response.text)
            return

        data = response.json()

        for obj in data.get("data", []):

            # ---------------- Folder ----------------

            if obj["type"] == "folders":

                folder, _ = AutodeskFolders.objects.update_or_create(
                    project=project,
                    folder_id=obj["id"],
                    defaults={
                        "parent": parent,
                        "is_root": False,
                        "name": obj["attributes"]["displayName"],
                        "hidden": obj["attributes"]["hidden"],
                        "object_count": obj["attributes"]["objectCount"],
                        "created_at": obj["attributes"]["createTime"],
                        "created_by": obj["attributes"]["createUserId"],
                        "created_by_name": obj["attributes"]["createUserName"],
                        "updated_at": obj["attributes"]["lastModifiedTime"],
                        "updated_by": obj["attributes"]["lastModifiedUserId"],
                        "updated_by_name": obj["attributes"]["lastModifiedUserName"],
                    }
                )

                sync_folder_recursive(
                    headers=headers,
                    project=project,
                    parent=folder,
                    folder_id=obj["id"],
                    download_tasks=download_tasks
                )

            # ---------------- PDF ----------------

            elif obj["type"] == "items":

                file_name = obj["attributes"]["displayName"]

                if not file_name.lower().endswith(".pdf"):
                    continue

                item_id = obj["id"]

                file_response = requests.get(
                    f"https://developer.api.autodesk.com/data/v1/projects/{project.project_id}/items/{item_id}/tip",
                    headers=headers
                )

                if file_response.status_code != 200:
                    continue

                file_data = file_response.json().get("data")

                if not file_data:
                    continue

                file_attributes = file_data.get("attributes", {})

                is_deleted = False
                name = ""
                if file_attributes.get("extension", {}).get("type") == "versions:autodesk.core:Deleted":
                    name = file_attributes.get("extension", {}).get("data", {}).get("originalName")
                    is_deleted = True
                else:
                    name = file_attributes.get("name")

                if not file_data:
                    continue

                file_obj, _ = AutodeskProjectFiles.objects.update_or_create(
                    folder=parent,
                    item_id=item_id,
                    defaults={
                        "name": name,
                        "version_number": file_attributes["versionNumber"],
                        "version": file_attributes.get("extension", {}).get("data", {}).get("revisionDisplayLabel", ""),
                        "created_at": file_attributes["createTime"],
                        "created_by": file_attributes["createUserId"],
                        "created_by_name": file_attributes["createUserName"],
                        "updated_at": file_attributes["lastModifiedTime"],
                        "updated_by": file_attributes["lastModifiedUserId"],
                        "updated_by_name": file_attributes["lastModifiedUserName"],
                        "current_file_id": file_data["id"],
                        "file_size_bytes": file_attributes.get("storageSize", 0),
                        "is_deleted": is_deleted,
                    }
                )

                download_tasks.append(
                    download_project_file.s(
                        headers,
                        project.project_id,
                        file_data["id"],
                        file_obj.pk,
                        file_name,
                        "project_file"
                    )
                )

                # create-store file versions data
                file_versions_response = requests.get(
                    f"https://developer.api.autodesk.com/data/v1/projects/{project.project_id}/items/{item_id}/versions",
                    headers=headers
                )

                if file_versions_response.status_code != 200:
                    continue

                file_versions_data = file_versions_response.json().get("data", [])                

                for file_version_data in file_versions_data:
                    versions_attribute = file_version_data.get("attributes", {})

                    name = ""
                    is_deleted = False
                    if versions_attribute.get("extension", {}).get("type") == "versions:autodesk.core:Deleted": 
                        name = versions_attribute.get("extension", {}).get("data", {}).get("originalName")
                        is_deleted = True
                    else:
                        name = versions_attribute.get("name")

                    file_versions, _ = AutodeskFileVersions.objects.update_or_create(
                        file_id=file_version_data.get("id"),
                        autodesk_project_file=file_obj,
                        defaults={
                            "name":name,
                            "version_number":versions_attribute.get("versionNumber"),
                            "created_at":versions_attribute.get("createTime"),
                            "created_by":versions_attribute.get("createUserId"),
                            "created_by_name":versions_attribute.get("createUserName"),
                            "updated_at":versions_attribute.get("lastModifiedTime"),
                            "updated_by":versions_attribute.get("lastModifiedUserId"),
                            "updated_by_name":versions_attribute.get("lastModifiedUserName"),
                            "file_size_bytes":versions_attribute.get("storageSize"),
                            "version":versions_attribute.get("extension", {}).get("data", {}).get("revisionDisplayLabel", ""),
                            "is_deleted":is_deleted
                        }
                    )

                    project_id = project.project_id
                    file_version_urn = file_version_data.get("id")
                    file_db_id = file_versions.pk
                    file_name = file_versions.name
                    model_type = "file_version"

                    download_tasks.append(
                        download_project_file.s(headers, project_id, file_version_urn, file_db_id, file_name, model_type)
                    )

        url = data.get("links", {}).get("next", {}).get("href")
                   

@shared_task
def update_folder_sync_time(sync_folder_id):

    SyncFolderData.objects.filter(
        id=sync_folder_id
    ).update(
        last_sync_time=timezone.now()
    )

    print(f"Folder {sync_folder_id} sync completed.")


@shared_task
def sync_single_folder(sync_folder_id):
    sync_folder = SyncFolderData.objects.select_related(
        "project",
        "sync_user__user"
    ).get(id=sync_folder_id)

    project = sync_folder.project
    user = sync_folder.sync_user.user

    headers = {
        "Authorization": f"Bearer {user.access_token}"
    }

    root_response = requests.get(
        f"https://developer.api.autodesk.com/data/v1/projects/{project.project_id}/folders/{sync_folder.folder_id}",
        headers=headers
    )

    if root_response.status_code != 200:
        return

    root_data = root_response.json().get("data")

    if not root_data:
        return

    root_folder, _ = AutodeskFolders.objects.update_or_create(
        project=project,
        folder_id=root_data["id"],
        defaults={
            "parent": None,
            "is_root": True,
            "name": root_data["attributes"]["displayName"],
            "hidden": root_data["attributes"]["hidden"],
            "object_count": root_data["attributes"]["objectCount"],
            "created_at": root_data["attributes"]["createTime"],
            "created_by": root_data["attributes"]["createUserId"],
            "created_by_name": root_data["attributes"]["createUserName"],
            "updated_at": root_data["attributes"]["lastModifiedTime"],
            "updated_by": root_data["attributes"]["lastModifiedUserId"],
            "updated_by_name": root_data["attributes"]["lastModifiedUserName"],
        }
    )

    download_tasks = []

    sync_folder_recursive(
        headers=headers,
        project=project,
        parent=root_folder,
        folder_id=sync_folder.folder_id,
        download_tasks=download_tasks
    )

    if download_tasks:
        print(f"{sync_folder.name} has {len(download_tasks)} downloads")
        chord(download_tasks)(
            update_folder_sync_time.si(sync_folder.id)
        )
    else:
        update_folder_sync_time.delay(sync_folder.id)


@shared_task
def sync_selected_folders():
    
    folder_ids = SyncFolderData.objects.values_list(
        "id",
        flat=True
    )

    for folder_id in folder_ids:
        sync_single_folder.delay(folder_id)


@shared_task
def send_link_mail(id, type):
    try:
        if type == "File":
            obj = RequestedVersionLinkRequest.objects.get(
                id=id     
            )
        elif type == "Sheet":
            obj = RequestedSheetVersionRequest.objects.get(
                id=id
            )
    except RequestedVersionLinkRequest.DoesNotExist:
        return
    except RequestedSheetVersionRequest.DoesNotExist:
        return
    
    signer = TimestampSigner()

    signed_token = signer.sign(str(obj.token))

    download_link = (
        f"http://192.168.1.7:8000/api/aps/download/{type}/{signed_token}/"
    )

    send_mail(
        subject=f"Latest {type} Version", 
        message=( 
            f"You scanned an older version of the drawing.\n\n" 
            f"Click the link below to download the latest version:\n\n" 
            f"{download_link}\n\n" 
            f"This link will expire in 3 days and can only be used once." 
        ), 
        from_email=DEFAULT_FROM_EMAIL, 
        recipient_list=[obj.email], 
    )

    obj.request_status = "SEND"
    obj.save(update_fields=["request_status"])
    


@shared_task
def deactivate_expired_subscriptions():
    print("Running deactivate_expired_subscriptions...")

    expired_date = timezone.now().date() - timedelta(days=1)

    active_subscriptions = Subscriptions.objects.filter(
        end_date__date=expired_date,
        is_active=True
    )
    print(active_subscriptions.count())
    for active_subscription in active_subscriptions:
        active_subscription.is_active = False
        active_subscription.save(update_fields=["is_active"])
