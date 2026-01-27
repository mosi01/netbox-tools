import logging
import re
import requests

from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from dcim.models import Device
from virtualization.models import VirtualMachine

from ..models import DocumentationBinding, SharePointConfig

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class DocumentationBindingView(View):
    template_name = "nbtools/documentation_binding.html"

    def get(self, request):
        config = SharePointConfig.objects.first()
        if config and not config.file_type_mappings:
            config.file_type_mappings = {
                ".docx": "Word Document",
                ".vsdx": "Visio Drawing",
                ".xlsx": "Excel Spreadsheet",
            }

        docs = DocumentationBinding.objects.all().order_by("category", "server_name")
        for doc in docs:
            exists = (
                Device.objects.filter(name=doc.server_name).exists()
                or VirtualMachine.objects.filter(name=doc.server_name).exists()
            )
            doc.exists_flag = exists

        return render(
            request,
            self.template_name,
            {
                "config": config,
                "docs": docs,
            },
        )

    def post(self, request):
        action = request.POST.get("action")
        try:
            if action == "save_config":
                site_url = request.POST.get("site_url")
                application_id = request.POST.get("application_id")
                client_id = request.POST.get("client_id")
                client_secret = request.POST.get("client_secret")

                # Folder mappings
                folder_keys = request.POST.getlist("folder_keys[]")
                folder_values = request.POST.getlist("folder_values[]")
                folder_mappings = {
                    k.strip(): v.strip().rstrip("/")
                    for k, v in zip(folder_keys, folder_values)
                    if k and v
                }

                # File type mappings handled like folder mappings
                file_type_keys = request.POST.getlist("file_type_keys[]")
                file_type_values = request.POST.getlist("file_type_values[]")
                file_type_mappings = {
                    k.strip(): v.strip()
                    for k, v in zip(file_type_keys, file_type_values)
                    if k and v
                }

                SharePointConfig.objects.update_or_create(
                    id=1,
                    defaults={
                        "site_url": site_url,
                        "application_id": application_id,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "folder_mappings": folder_mappings,
                        "file_type_mappings": file_type_mappings,
                    },
                )
                messages.success(request, "Configuration saved successfully.")

            elif action == "sync":
                messages.info(request, "Syncing with SharePoint...")
                result = self.sync_sharepoint()
                if result["status"] == "success":
                    details = "\n".join(
                        [
                            f"{r['status'].upper()}: {r['path']} - {r['message']}"
                            for r in result["details"]
                        ]
                    )
                    messages.success(
                        request,
                        f"Sync complete. {result['count']} documents cached.\nDetails:\n{details}",
                    )
                else:
                    details = "\n".join(
                        [
                            f"{r['status'].upper()}: {r['path']} - {r['message']}"
                            for r in result.get("details", [])
                        ]
                    )
                    messages.error(
                        request,
                        f"Sync failed: {result['error']}\nDetails:\n{details}",
                    )

        except Exception as e:
            logger.exception(f"Error in DocumentationBindingView POST: {e}")
            messages.error(request, f"An error occurred: {e}")

        return redirect("plugins:nbtools:documentation_binding")

    def sync_sharepoint(self):
        config = SharePointConfig.objects.first()
        if not config:
            return {"status": "error", "error": "No configuration found."}

        DocumentationBinding.objects.all().delete()
        folder_mappings = config.folder_mappings
        file_type_mappings = config.file_type_mappings

        try:
            token_url = (
                f"https://login.microsoftonline.com/{config.application_id}/oauth2/v2.0/token"
            )
            token_data = {
                "grant_type": "client_credentials",
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "scope": "https://graph.microsoft.com/.default",
            }
            token_response = requests.post(token_url, data=token_data)
            if token_response.status_code != 200:
                return {
                    "status": "error",
                    "error": f"Token request failed: {token_response.text}",
                }

            access_token = token_response.json().get("access_token")
            headers = {"Authorization": f"Bearer {access_token}"}

            hostname = config.site_url.replace("https://", "").split("/")[0]
            path = "/" + "/".join(
                config.site_url.replace("https://", "").split("/")[1:]
            )
            site_lookup_url = f"{GRAPH_BASE_URL}/sites/{hostname}:{path}"
            site_response = requests.get(site_lookup_url, headers=headers)
            if site_response.status_code != 200:
                return {
                    "status": "error",
                    "error": f"Site lookup failed: {site_response.text}",
                }

            site_id = site_response.json().get("id")
            drives_url = f"{GRAPH_BASE_URL}/sites/{site_id}/drives"
            drives_response = requests.get(drives_url, headers=headers)
            if drives_response.status_code != 200:
                return {
                    "status": "error",
                    "error": f"Drive lookup failed: {drives_response.text}",
                }

            drives = drives_response.json().get("value", [])
            documents_drive = next(
                (
                    d
                    for d in drives
                    if d["name"].lower() in ["documents", "shared documents"]
                ),
                None,
            )
            if not documents_drive:
                return {
                    "status": "error",
                    "error": "Documents library not found.",
                }

            drive_id = documents_drive["id"]
            total_files = 0
            path_results = []

            for category_key, path in folder_mappings.items():
                folder_url = (
                    f"{GRAPH_BASE_URL}/drives/{drive_id}/root:/{path}:/children"
                )
                folder_response = requests.get(folder_url, headers=headers)
                found_folders = []
                found_files = []

                if folder_response.status_code != 200:
                    error_msg = (
                        f"Failed to fetch folder '{path}'. "
                        f"Status: {folder_response.status_code}. URL: {folder_url}"
                    )
                    path_results.append(
                        {"path": path, "status": "error", "message": error_msg}
                    )
                    continue

                items = folder_response.json().get("value", [])
                if not items:
                    warning_msg = (
                        f"No items found in folder '{path}'. URL: {folder_url}. "
                        "Possible reasons: empty folder or incorrect path."
                    )
                    path_results.append(
                        {"path": path, "status": "warning", "message": warning_msg}
                    )
                    continue

                files_found = 0
                for item in items:
                    if "folder" in item and item["name"].lower() in [
                        "application",
                        "server",
                    ]:
                        found_folders.append(item["name"])
                        subfolder_id = item["id"]
                        subfolder_url = (
                            f"{GRAPH_BASE_URL}/drives/{drive_id}/items/{subfolder_id}/children"
                        )
                        subfolder_response = requests.get(
                            subfolder_url, headers=headers
                        )
                        if subfolder_response.status_code != 200:
                            error_msg = (
                                f"Failed to fetch subfolder '{item['name']}' under '{path}'. "
                                f"Status: {subfolder_response.status_code}. URL: {subfolder_url}"
                            )
                            path_results.append(
                                {
                                    "path": path,
                                    "status": "error",
                                    "message": error_msg,
                                }
                            )
                            continue

                        sub_items = subfolder_response.json().get("value", [])
                        if not sub_items:
                            continue

                        for sub_item in sub_items:
                            if "file" in sub_item:
                                found_files.append(sub_item["name"])
                                parsed = self.parse_filename(sub_item["name"])
                                file_type = self.get_file_type(
                                    sub_item["name"], file_type_mappings
                                )
                                DocumentationBinding.objects.update_or_create(
                                    file_name=parsed.get("name", sub_item["name"]),
                                    server_name=parsed.get("server", ""),
                                    defaults={
                                        "category": category_key,
                                        "version": parsed.get(
                                            "version", "Unknown"
                                        ),
                                        "file_type": file_type,
                                        "sharepoint_url": sub_item["webUrl"],
                                        "application_name": parsed.get(
                                            "application", None
                                        )
                                        or item["name"].capitalize(),
                                    },
                                )
                                total_files += 1
                                files_found += 1

                if files_found > 0:
                    path_results.append(
                        {
                            "path": path,
                            "status": "success",
                            "message": (
                                f"Fetched {files_found} files. "
                                f"Found Folders: {', '.join(found_folders)}. "
                                f"Found Files: {', '.join(found_files)}"
                            ),
                        }
                    )
                else:
                    path_results.append(
                        {
                            "path": path,
                            "status": "warning",
                            "message": (
                                "No files found. "
                                f"Found Folders: {', '.join(found_folders) if found_folders else 'None'}"
                            ),
                        }
                    )

            if total_files == 0:
                return {
                    "status": "error",
                    "error": "No documents found.",
                    "details": path_results,
                }

            return {
                "status": "success",
                "count": total_files,
                "details": path_results,
            }

        except Exception as e:
            logger.exception(f"Error during Graph API sync: {e}")
            return {"status": "error", "error": str(e)}

    def parse_filename(self, filename):
        pattern_app = (
            r"^(?P<application>[A-Za-z0-9]+)-"
            r"(?P<server>[A-Za-z0-9]+)-"
            r"(?P<name>[A-Za-z_]+)-"
            r"V(?P<version>[0-9]+\.[0-9]+\.[0-9]+)"
        )
        pattern_server = (
            r"^(?P<server>[A-Za-z0-9]+)-"
            r"(?P<name>[A-Za-z_]+)-"
            r"V(?P<version>[0-9]+\.[0-9]+\.[0-9]+)"
        )
        match_app = re.match(pattern_app, filename)
        match_server = re.match(pattern_server, filename)
        if match_app:
            return match_app.groupdict()
        if match_server:
            return match_server.groupdict()
        return {}

    def get_file_type(self, filename, file_type_mappings):
        filename = filename.lower()
        for ext, label in file_type_mappings.items():
            if filename.endswith(ext.lower()):
                return label
        return "Unknown"