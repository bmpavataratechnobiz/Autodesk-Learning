import requests #type:ignore
from django.conf import settings
from .models import AutodeskAccount, AutoDeskProject, AutodeskUser, AutodeskSheets, AutodeskVersionSet
from celery import shared_task
from django.core.files.base import ContentFile
import time
from collections import defaultdict



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

          
@shared_task
def download_sheet_pdf(access_token, project_id, sheet_id, sheet_number, upload_file_name, sheet_db_id):

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

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

        sheet_obj.file.save(
            f"{sheet_number}.pdf",
            ContentFile(pdf_resp.content),
            save=True
        )

        print(f"PDF saved for {sheet_number}")

    except Exception as e:
        print(f"PDF task failed: {e}")


@shared_task
def get_hubs_projects_and_save(user_id):
    try:
        autodesk_user = AutodeskUser.objects.get(user__id=user_id)

        headers = {
            "Authorization": f"Bearer {autodesk_user.access_token}"
        }

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

                project_users_response = requests.get(
                    f"https://developer.api.autodesk.com/construction/admin/v1/projects/{project_id}/users",
                    headers=headers
                )

                project_users_data = project_users_response.json().get("results", [])

                autodesk_users = []
                for project_user_data in project_users_data:
                    autodesk_user_obj, _ = AutodeskUser.objects.get_or_create(
                        autodesk_user_id=project_user_data.get("autodeskId"),
                        defaults={
                            "email":project_user_data.get("email"),
                            "name":project_user_data.get("name")
                        }
                    )
                    autodesk_users.append(autodesk_user_obj)
                
                project.users.set(autodesk_users)
                project.save()
                project_name = project_data["attributes"]["name"]
                count = project.users.count()
                print("$" * 100)
                print(f"Project : {project_name}, Users : {autodesk_users}, Count : {count}")
                print("$" * 100)
                
                # ++++++++++++++++++++++++++++++++++++++++ version set map and version tracker +++++++++++++++++++++++++++++++++++++++
                version_sets_response = requests.get(
                    f"https://developer.api.autodesk.com/construction/sheets/v1/projects/{project_id}/version-sets",
                    headers=headers
                ) 
                if version_sets_response.status_code != 200:
                    continue

                version_sets_data = version_sets_response.json().get("results", [])

                version_sets_map = {
                    version_set["id"]:version_set for version_set in version_sets_data
                }

                # for current sheets
                active_sheet_version_tracker = defaultdict(list)

                # for deleted sheets
                deleted_sheet_version_tracker = defaultdict(list)
                
                for version_set in version_sets_data:
                    version_set_id = version_set["id"]

                    version_sheets_response = requests.get(
                        f"https://developer.api.autodesk.com/construction/sheets/v1/projects/{project_id}/sheets?filter[versionSetId]={version_set_id}",
                        headers=headers
                    )
                    if version_sheets_response.status_code != 200:
                        continue

                    version_sheets = version_sheets_response.json().get("results", [])

                    for version_sheet in version_sheets:
                        sheet_number = version_sheet["number"]

                        # for active sheets
                        if version_set_id not in active_sheet_version_tracker[sheet_number]:
                            active_sheet_version_tracker[sheet_number].append(version_set_id)

                        # for deleted sheets
                        if version_set_id not in deleted_sheet_version_tracker[sheet_number]:
                            deleted_sheet_version_tracker[sheet_number].append(version_set_id)

                deleted_sheets_response = requests.get(
                    f"https://developer.api.autodesk.com/construction/sheets/v1/projects/{project_id}/sheets?isDeleted=true",
                    headers=headers
                )
                deleted_sheets_data = []
                if deleted_sheets_response.status_code == 200:
                    deleted_sheets_data = deleted_sheets_response.json().get("results", [])

                    for deleted_sheet in deleted_sheets_data:
                        sheet_number = deleted_sheet["number"]
                        version_id = deleted_sheet["versionSet"]["id"]
                        if version_id not in version_sets_map:
                            version_sets_map[version_id] = deleted_sheet["versionSet"]

                        # store deleted version sheet
                        if version_id not in deleted_sheet_version_tracker[sheet_number]:
                            deleted_sheet_version_tracker[sheet_number].append(version_id)
                else:
                    print(f"Skipping project {project_id}. Deleted sheets API returned {deleted_sheets_response.status_code}")

                
                deleted_sheet_version_number = {}
                for sheet_number, versions in deleted_sheet_version_tracker.items():
                    order_versions = sorted(versions, key=lambda version_id:(version_sets_map.get(version_id, {}).get("issuanceDate") or "",
                            version_sets_map.get(version_id).get('createdAt') or "",
                            version_id
                        )
                    )

                    deleted_sheet_version_number[sheet_number] = {
                        version_id: index + 1 for index, version_id in enumerate(order_versions)
                    }                


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
                    version = len(active_sheet_version_tracker.get(sheet_number, {}))
                    version_set = get_or_create_versionSet(version_sets_map, version_id)

                    sheet_obj, _ = AutodeskSheets.objects.update_or_create(
                        sheetId=sheet_data["id"],
                        sheetNumber=sheet_number,
                        defaults={
                            "project":project,
                            "title":sheet_data["title"],
                            "versionSet":version_set,
                            "version":version,
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
                    download_sheet_pdf.delay(autodesk_user.access_token, project_id, sheet_id, sheet_data["number"], sheet_data["uploadFileName"], sheet_obj.id)

                              
                # +++++++++++++++++++++++++++++++++++++++++++++++++++ STORE DELETED SHEETS DATA ++++++++++++++++++++++++++++++++++++++++++++++++++++++
                deleted_sheets = requests.get(
                    f"https://developer.api.autodesk.com/construction/sheets/v1/projects/{project_id}/sheets?isDeleted=true",
                    headers=headers
                )

                if deleted_sheets.status_code != 200:
                    print(
                        f"Skipping project {project_id}. "
                        f"Sheets API returned {sheets.status_code}"
                    )   
                    continue

                deleted_sheets_data = deleted_sheets.json().get('results', [])               

                for deleted_sheet_data in deleted_sheets_data:
                    version_id = deleted_sheet_data["versionSet"]["id"]       
                    sheet_number = deleted_sheet_data["number"]             
                    version_set = get_or_create_versionSet(version_sets_map, version_id)
                    version = deleted_sheet_version_number.get(sheet_number, {}).get(version_id, 0)

                    sheet_obj, _ = AutodeskSheets.objects.update_or_create(
                        sheetId=deleted_sheet_data["id"],
                        defaults={
                            "project":project,
                            "title":deleted_sheet_data["title"],
                            "sheetNumber":deleted_sheet_data["number"],
                            "versionSet":version_set,
                            "version":version,
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

                print("\n" + "=" * 100)
                
                update_current_sheet_flags(project)

        return {"status": "success"}

    except AutodeskAccount.DoesNotExist:
        return {"status": "error", "message": "Autodesk account not found"}

    except Exception as e:
        return {"status": "error", "message": str(e)}