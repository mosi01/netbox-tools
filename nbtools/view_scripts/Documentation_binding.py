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

# Import plugin models
from ..models import DocumentationBinding, SharePointConfig

# Base URL for Microsoft Graph API
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

# Logger for this module
logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class DocumentationBindingView(View):
    """
    View for configuring SharePoint access and synchronizing documentation
    bindings with NetBox objects.

    UPDATED BEHAVIOUR (metadata-driven):

    The SharePoint document library now uses FOLDER NAME + METADATA fields
    to control how documents are bound to NetBox objects:

        Path example:
            Documents/Servers/SomeHLD.docx

        Metadata on the file:
            Document Version : 1.1.13      --> stored as DocumentationBinding.version
            Document Type    : HLD          --> stored as DocumentationBinding.category
            Object Name      : SE86DHCP0596 --> stored as DocumentationBinding.server_name

        Folder name determines Object Type:
            Servers      -> Virtual Machine
            Devices      -> Device
            Applications -> Application  (not yet visualized, but stored)

    On the NetBox side:

    * server_name  = Object Name (e.g. "SE86DHCP0596")
    * category     = Document Type (e.g. "HLD", "LLD")
    * version      = Document Version (e.g. "1.1.13")
    * application_name = Type label (e.g. "Virtual Machine", "Device")

    The VM panel still groups by DocumentationBinding.category and filters
    by DocumentationBinding.server_name, so the only requirement is that
    Object Name matches the NetBox object's name (e.g. VirtualMachine.name).
    """

    # Django template to render
    template_name = "nbtools/documentation_binding.html"

    # Optional base folder under the Documents library.
    # If left as "", files are expected directly under:
    #
    #   Documents/Servers/
    #   Documents/Devices/
    #   Documents/Applications/
    #
    # If you want an extra level (e.g. "Documentation/Servers/"), set:
    #   DOCUMENTATION_ROOT = "Documentation"
    DOCUMENTATION_ROOT = ""

    def get(self, request):
        """
        Display configuration form and the cached documents table.
        """
        config = SharePointConfig.objects.first()

        # Populate default file type mappings if not set
        if config and not config.file_type_mappings:
            config.file_type_mappings = {
                ".docx": "Word Document",
                ".vsdx": "Visio Drawing",
                ".xlsx": "Excel Spreadsheet",
            }

        # Fetch all cached bindings ordered by category and server name
        docs = DocumentationBinding.objects.all().order_by(
            "category", "server_name"
        )

        # Add an exists_flag for each doc (does the NetBox object exist?)
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
        """
        Handle POST requests for:

        - Saving configuration
        - Triggering sync from SharePoint
        """
        action = request.POST.get("action")

        try:
            if action == "save_config":
                # Basic SharePoint OAuth / site config
                site_url = request.POST.get("site_url")
                application_id = request.POST.get("application_id")
                client_id = request.POST.get("client_id")
                client_secret = request.POST.get("client_secret")

                # Folder mappings (kept for backward compatibility in the UI).
                # NOTE: These are no longer used for binding behavior, since
                #       Document Type is now taken from metadata instead of
                #       folder names.
                folder_keys = request.POST.getlist("folder_keys[]")
                folder_values = request.POST.getlist("folder_values[]")
                folder_mappings = {
                    k.strip(): v.strip().rstrip("/")
                    for k, v in zip(folder_keys, folder_values)
                    if k and v
                }

                # File type mappings: extension -> description
                file_type_keys = request.POST.getlist("file_type_keys[]")
                file_type_values = request.POST.getlist("file_type_values[]")
                file_type_mappings = {
                    k.strip(): v.strip()
                    for k, v in zip(file_type_keys, file_type_values)
                    if k and v
                }

                # Persist configuration (single row, id=1)
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
                        (
                            f"Sync complete. {result['count']} documents cached.\n"
                            f"Details:\n{details}"
                        ),
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

    # -------------------------------------------------------------------------
    # SharePoint sync logic
    # -------------------------------------------------------------------------
    def sync_sharepoint(self):
        """
        Synchronize documentation from SharePoint into DocumentationBinding.

        NEW BEHAVIOUR:

        * We no longer iterate over each NetBox object & category folder.
        * Instead, we iterate over top-level type folders inside the
          Documents library:

              <DOCUMENTATION_ROOT>/Servers
              <DOCUMENTATION_ROOT>/Devices
              <DOCUMENTATION_ROOT>/Applications

          (DOCUMENTATION_ROOT can be "", giving "Servers", "Devices", "Applications"
           directly under "Documents").

        * For each file in those folders, we read metadata fields:

              "Document Version" -> DocumentationBinding.version
              "Document Type"   -> DocumentationBinding.category
              "Object Name"     -> DocumentationBinding.server_name

        * Folder name ("Servers", "Devices", "Applications") determines the
          Type label stored in DocumentationBinding.application_name:

              Servers      -> "Virtual Machine"
              Devices      -> "Device"
              Applications -> "Application"

        * Filename (without extension) is used as file_name (e.g. "SomeHLD").
        * Extension is mapped via file_type_mappings to a friendly label
          (e.g. ".docx" -> "Word Document").
        """

        config = SharePointConfig.objects.first()
        if not config:
            return {"status": "error", "error": "No configuration found."}

        # Remove all existing bindings before resync
        DocumentationBinding.objects.all().delete()

        file_type_mappings = config.file_type_mappings or {}

        try:
            # -----------------------------------------------------------------
            # 1. Acquire OAuth token
            # -----------------------------------------------------------------
            token_url = (
                f"https://login.microsoftonline.com/{config.application_id}"
                f"/oauth2/v2.0/token"
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

            # -----------------------------------------------------------------
            # 2. Resolve site and document library (drive)
            # -----------------------------------------------------------------
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

            # -----------------------------------------------------------------
            # 3. Iterate over Object-Type folders and their files
            # -----------------------------------------------------------------
            total_files = 0
            path_results = []

            # Mapping of SharePoint folder name -> type label
            # You can adjust labels if you want other display text,
            # but the folder names "Servers", "Devices", "Applications"
            # must match your SharePoint structure.
            object_type_folders = {
                "Servers": "Virtual Machine",
                "Devices": "Device",
                "Applications": "Application",
            }

            for folder_name, type_label in object_type_folders.items():
                # Build path:
                #   <DOCUMENTATION_ROOT>/Servers   (or just "Servers" if root is "")
                if self.DOCUMENTATION_ROOT:
                    sp_path = f"{self.DOCUMENTATION_ROOT}/{folder_name}"
                else:
                    sp_path = folder_name

                folder_url = (
                    f"{GRAPH_BASE_URL}/drives/{drive_id}"
                    f"/root:/{sp_path}:/children"
                )

                folder_response = requests.get(folder_url, headers=headers)

                # Handle errors and missing folders gracefully
                if folder_response.status_code == 404:
                    path_results.append(
                        {
                            "path": sp_path,
                            "status": "warning",
                            "message": (
                                "Folder not found. This usually means "
                                "no documentation exists yet for this object type."
                            ),
                        }
                    )
                    continue

                if folder_response.status_code != 200:
                    error_msg = (
                        f"Failed to fetch folder '{sp_path}'. "
                        f"Status: {folder_response.status_code}. "
                        f"URL: {folder_url}"
                    )
                    path_results.append(
                        {
                            "path": sp_path,
                            "status": "error",
                            "message": error_msg,
                        }
                    )
                    continue

                items = folder_response.json().get("value", [])
                if not items:
                    path_results.append(
                        {
                            "path": sp_path,
                            "status": "warning",
                            "message": "No items found in folder.",
                        }
                    )
                    continue

                files_found = 0
                found_files = []

                for item in items:
                    # Only process files (skip subfolders etc.)
                    if "file" not in item:
                        continue

                    raw_name = item["name"]
                    found_files.append(raw_name)

                    # -----------------------------------------------------------------
                    # 3a. Fetch metadata (list item fields) for this file
                    # -----------------------------------------------------------------
                    fields_url = (
                        f"{GRAPH_BASE_URL}/drives/{drive_id}"
                        f"/items/{item['id']}/listItem/fields"
                    )
                    fields_response = requests.get(fields_url, headers=headers)

                    if fields_response.status_code == 200:
                        fields = fields_response.json()
                    else:
                        fields = {}
                        logger.warning(
                            "Failed to fetch metadata for item %s: %s",
                            item["id"],
                            fields_response.text,
                        )

                    # -----------------------------------------------------------------
                    # 3b. Map metadata fields to local variables
                    # -----------------------------------------------------------------
                    # NOTE ABOUT INTERNAL NAMES:
                    #
                    # SharePoint internal field names may differ from the display
                    # names ("Document Version", "Document Type", "Object Name").
                    #
                    # If your internal names are different, update the keys below.
                    #
                    # Example common patterns:
                    #   "Document Version" -> "DocumentVersion" or "Document_x0020_Version"
                    #   "Document Type"    -> "DocumentType"   or "Document_x0020_Type"
                    #   "Object Name"      -> "ObjectName"     or "Object_x0020_Name"
                    #
                    # Adjust these as needed to match your library.

                    # Version
                    version = (
                        fields.get("DocumentVersion")
                        or fields.get("Document_x0020_Version")
                        or None
                    )

                    # Document Type (category)
                    doc_type = (
                        fields.get("DocumentType")
                        or fields.get("Document_x0020_Type")
                        or None
                    )

                    # Object Name (NetBox object name to bind to)
                    object_name = (
                        fields.get("ObjectName")
                        or fields.get("Object_x0020_Name")
                        or None
                    )

                    # -----------------------------------------------------------------
                    # 3c. Fallbacks if metadata missing
                    # -----------------------------------------------------------------
                    # Use filename (without extension) as display name.
                    base_name = raw_name.rsplit(".", 1)[0]
                    file_display_name = base_name

                    # If version is not specified in metadata, try parsing from filename
                    if not version:
                        parsed = self.parse_filename(raw_name)
                        version = parsed.get("version", "Unknown")

                    # If no document type is set, use a generic label
                    if not doc_type:
                        doc_type = "Uncategorized"

                    # If no object name is provided, mark as Unassigned
                    if not object_name:
                        object_name = "Unassigned"

                    # Map extension to a friendly file type label
                    file_type = self.get_file_type(raw_name, file_type_mappings)

                    # -----------------------------------------------------------------
                    # 3d. Create or update DocumentationBinding record
                    # -----------------------------------------------------------------
                    DocumentationBinding.objects.update_or_create(
                        file_name=file_display_name,
                        server_name=object_name,
                        defaults={
                            "category": doc_type,
                            "version": version,
                            "file_type": file_type,
                            "sharepoint_url": item["webUrl"],
                            # Shown as "Type" in the UI (e.g. "Virtual Machine")
                            "application_name": type_label,
                        },
                    )

                    total_files += 1
                    files_found += 1

                # Summary per folder
                if files_found > 0:
                    path_results.append(
                        {
                            "path": sp_path,
                            "status": "success",
                            "message": (
                                f"Fetched {files_found} files. "
                                f"Found Files: {', '.join(found_files)}"
                            ),
                        }
                    )
                else:
                    path_results.append(
                        {
                            "path": sp_path,
                            "status": "warning",
                            "message": "No files found.",
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

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def parse_filename(self, filename):
        """
        Parse a filename into components.

        Preferred pattern (simple, user-friendly):
            "<Title>-v1.2.3.ext"
            "<Title>.ext"

        - Title can contain spaces/dashes/anything.
        - Version is optional; when present it starts with -v and can be
          one or more numeric components separated by dots.

        Legacy patterns are still supported as a fallback:
            "<APP>-<SERVER>-<Name>-V1.2.3.ext"
            "<SERVER>-<Name>-V1.2.3.ext"
        """
        # Strip extension for pattern matching
        base = filename.rsplit(".", 1)[0]

        # ---------------------------------------------------------------------
        # 1. New simple pattern: Title[-vX[.Y[.Z]]]
        # ---------------------------------------------------------------------
        simple_pattern = (
            r"^(?P<name>.+?)(?:-v(?P<version>[0-9]+(?:\.[0-9]+)*))?$"
        )
        match_simple = re.match(simple_pattern, base, flags=re.IGNORECASE)
        if match_simple:
            group_dict = match_simple.groupdict()
            # Version is already without the "v" prefix thanks to the regex
            return group_dict

        # ---------------------------------------------------------------------
        # 2. Legacy patterns (keep for backward compatibility)
        # ---------------------------------------------------------------------
        pattern_app = (
            r"^(?P<application>[A-Za-z0-9]+)-"
            r"(?P<server>[A-Za-z0-9]+)-"
            r"(?P<name>[A-Za-z_]+)-"
            r"V(?P<version>[0-9]+\.[0-9]+\.[0-9]+)$"
        )
        pattern_server = (
            r"^(?P<server>[A-Za-z0-9]+)-"
            r"(?P<name>[A-Za-z_]+)-"
            r"V(?P<version>[0-9]+\.[0-9]+\.[0-9]+)$"
        )

        match_app = re.match(pattern_app, base, flags=re.IGNORECASE)
        if match_app:
            return match_app.groupdict()

        match_server = re.match(pattern_server, base, flags=re.IGNORECASE)
        if match_server:
            return match_server.groupdict()

        # If nothing matches, return an empty dict; caller will fall back to
        # the raw filename.
        return {}

    def get_file_type(self, filename, file_type_mappings):
        """
        Return a friendly file type label based on the file extension.

        Uses the configured file_type_mappings, e.g.:
            ".docx" -> "Word Document"
        """
        filename = filename.lower()
        for ext, label in file_type_mappings.items():
            if filename.endswith(ext.lower()):
                return label
        return "Unknown"