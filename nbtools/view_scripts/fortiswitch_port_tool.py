"""
fortiswitch_port_tool.py

Single-page FortiSwitch port tool for the nbtools NetBox plugin.

Purpose
-------
- Select Site / Device
- Automatically load all switch ports from FortiGate
- Allow bulk selection of multiple ports
- Validate intended switch port settings in bulk
- Preview deploy payloads in bulk
- Deploy changes via FortiGate API in bulk
- Perform manual readback/sync in bulk
- Return structured, human-readable results rather than raw Forti JSON

Notes
-----
- This file is intentionally modular and designed to be imported by views.py
- It uses FortiSiteBinding + FortiAPIClient
- It remains safe by:
  - warning if a selected interface looks connected in NetBox
  - blocking obvious uplink candidates
- Endpoint paths/payload keys used by the Forti client are proposed and
  must be validated against your FortiOS version
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from dcim.models import Device, Interface, Site

from nbtools.models import FortiSiteBinding
from nbtools.services.forti_api import FortiAPIClient

logger = logging.getLogger("nbtools")


class FortiSwitchPortToolView(LoginRequiredMixin, View):
    """
    Single-page FortiSwitch bulk-capable port operations tool.

    Supported actions
    -----------------
    - validate
    - deploy
    - sync

    Behaviour
    ---------
    - GET:
        If a site/device is selected, load all Forti ports for the device
        and pass them to the template as `port_rows`.
    - POST:
        Accept multiple selected ports and perform the chosen action on all
        of them, returning a structured bulk result.
    """

    template_name = "nbtools/fortiswitch_port_tool.html"

    # ------------------------------------------------------------------
    # HTTP GET
    # ------------------------------------------------------------------
    def get(self, request):
        """
        Render the starting page and, if possible, load current Forti port
        state for the selected device.
        """
        site_id = request.GET.get("site_id", "").strip()
        device_id = request.GET.get("device_id", "").strip()

        site = self._get_site(site_id)
        device = self._get_device(device_id)

        warnings_list: List[str] = []
        errors_list: List[str] = []

        port_rows = self._load_port_rows(
            site=site,
            device=device,
            warnings_list=warnings_list,
            errors_list=errors_list,
        )

        context = self._build_context(
            site_id=site_id,
            device_id=device_id,
            submitted_data={},
            port_rows=port_rows,
            result=None,
            warnings_list=warnings_list,
            errors_list=errors_list,
        )
        return render(request, self.template_name, context)

    # ------------------------------------------------------------------
    # HTTP POST
    # ------------------------------------------------------------------
    def post(self, request):
        """
        Handle all form actions from the single-page bulk tool.
        """
        submitted_data = {
            "site_id": request.POST.get("site_id", "").strip(),
            "device_id": request.POST.get("device_id", "").strip(),
            "action": request.POST.get("action", "").strip(),
            "dry_run": bool(request.POST.get("dry_run")),
        }

        selected_ports = [p.strip() for p in request.POST.getlist("selected_ports") if p.strip()]

        errors_list: List[str] = []
        warnings_list: List[str] = []
        result = None

        # --------------------------------------------------------------
        # Resolve selected objects
        # --------------------------------------------------------------
        site = self._get_site(submitted_data["site_id"])
        device = self._get_device(submitted_data["device_id"])

        if not site:
            errors_list.append("A valid site must be selected.")

        if not device:
            errors_list.append("A valid device must be selected.")

        if site and device and device.site_id != site.id:
            errors_list.append("The selected device does not belong to the selected site.")

        if not selected_ports:
            errors_list.append("At least one switch port must be selected.")

        # --------------------------------------------------------------
        # Resolve Forti site binding
        # --------------------------------------------------------------
        binding = None
        if site:
            binding = FortiSiteBinding.objects.filter(site=site, enabled=True).first()
            if not binding:
                errors_list.append("No enabled Forti site binding exists for the selected site.")

        # Always reload current rows so the page remains populated
        port_rows = self._load_port_rows(
            site=site,
            device=device,
            warnings_list=warnings_list,
            errors_list=[],
        )

        if errors_list:
            context = self._build_context(
                site_id=submitted_data["site_id"],
                device_id=submitted_data["device_id"],
                submitted_data=submitted_data,
                port_rows=port_rows,
                result=result,
                warnings_list=warnings_list,
                errors_list=errors_list,
            )
            return render(request, self.template_name, context)

        # --------------------------------------------------------------
        # Execute Forti action per selected port
        # --------------------------------------------------------------
        try:
            client = FortiAPIClient(binding)
            switch_identifier = client.get_switch_identifier(device)

            bulk_results = []

            for port_name in selected_ports:
                # Build port-specific desired state from posted row fields
                desired_state = self._extract_desired_state_for_port(
                    request=request,
                    port_name=port_name,
                )

                port_result = self._handle_port_action(
                    action=submitted_data["action"],
                    client=client,
                    switch_identifier=switch_identifier,
                    device=device,
                    port_name=port_name,
                    desired_state=desired_state,
                    dry_run=submitted_data["dry_run"],
                    warnings_list=warnings_list,
                )
                bulk_results.append(port_result)

            result = self._summarise_bulk_results(
                action=submitted_data["action"],
                device_name=device.name,
                bulk_results=bulk_results,
            )

            if submitted_data["action"] == "validate":
                messages.success(request, "Validation completed successfully.")
            elif submitted_data["action"] == "deploy":
                if submitted_data["dry_run"]:
                    messages.success(request, "Deploy preview completed successfully.")
                else:
                    messages.success(request, "Deploy completed successfully.")
            elif submitted_data["action"] == "sync":
                messages.success(request, "Sync completed successfully.")

            # Reload rows after action so the page reflects current state
            port_rows = self._load_port_rows(
                site=site,
                device=device,
                warnings_list=warnings_list,
                errors_list=[],
            )

        except Exception as exc:
            logger.exception("FortiSwitch port bulk action failed")
            errors_list.append(f"Unexpected error: {exc}")

        context = self._build_context(
            site_id=submitted_data["site_id"],
            device_id=submitted_data["device_id"],
            submitted_data=submitted_data,
            port_rows=port_rows,
            result=result,
            warnings_list=warnings_list,
            errors_list=errors_list,
        )
        return render(request, self.template_name, context)

    # ------------------------------------------------------------------
    # Bulk page context helper
    # ------------------------------------------------------------------
    def _build_context(
        self,
        site_id: str,
        device_id: str,
        submitted_data: dict,
        port_rows: List[dict],
        result: Optional[dict],
        warnings_list: List[str],
        errors_list: List[str],
    ) -> dict:
        """
        Build page context for both GET and POST.

        Note:
        - `port_rows` is a normalised list of live Forti ports for the
          selected device.
        - The template can render this as an editable table with:
            checkbox + mode + native_vlan + allowed_vlans + description
        """
        sites = Site.objects.all().order_by("name")

        if site_id and site_id.isdigit():
            devices = Device.objects.filter(site_id=site_id).order_by("name")
        else:
            devices = Device.objects.none()

        return {
            "sites": sites,
            "devices": devices,
            "selected_site": self._get_site(site_id),
            "selected_device": self._get_device(device_id),
            "submitted_data": submitted_data,
            "port_rows": port_rows,
            "result": result,
            "warnings_list": warnings_list,
            "errors_list": errors_list,
            "action_help": {
                "validate": "Compare desired values against live FortiSwitch state.",
                "deploy": "Push desired values to FortiSwitch. If dry_run is checked, only preview payloads.",
                "sync": "Read current FortiSwitch state and refresh the page.",
            },
        }

    # ------------------------------------------------------------------
    # Object resolvers
    # ------------------------------------------------------------------
    @staticmethod
    def _get_site(site_id: str):
        """
        Resolve a Site safely by primary key.
        """
        return Site.objects.filter(pk=site_id).first() if site_id and site_id.isdigit() else None

    @staticmethod
    def _get_device(device_id: str):
        """
        Resolve a Device safely by primary key.
        """
        return (
            Device.objects.select_related("site").filter(pk=device_id).first()
            if device_id and device_id.isdigit()
            else None
        )

    @staticmethod
    def _get_interface_by_name(device: Device, port_name: str):
        """
        Attempt to map a Forti port name back to a NetBox interface.
        """
        return Interface.objects.filter(device=device, name=port_name).first()

    # ------------------------------------------------------------------
    # Port loading helpers
    # ------------------------------------------------------------------
    def _load_port_rows(
        self,
        site: Optional[Site],
        device: Optional[Device],
        warnings_list: List[str],
        errors_list: List[str],
    ) -> List[dict]:
        """
        Load and normalise all FortiSwitch ports for the selected device.

        This is what enables the table to be pre-populated automatically.
        """
        if not site or not device:
            return []

        binding = FortiSiteBinding.objects.filter(site=site, enabled=True).first()
        if not binding:
            return []

        try:
            client = FortiAPIClient(binding)
            switch_identifier = client.get_switch_identifier(device)
            raw_ports = client.get_switch_ports(switch_identifier)
            port_rows = client.normalise_ports_response(raw_ports)

            # Add NetBox safety metadata per row
            enriched_rows = []
            for row in port_rows:
                interface = self._get_interface_by_name(device, row["port_name"])
                row["netbox_interface_exists"] = bool(interface)
                row["netbox_connected"] = self._is_connected(interface) if interface else False
                row["uplink_candidate"] = self._is_uplink_candidate(interface) if interface else False
                enriched_rows.append(row)

            return enriched_rows

        except Exception as exc:
            logger.exception("Failed to load FortiSwitch ports")
            errors_list.append(f"Could not load ports from Forti: {exc}")
            return []

    # ------------------------------------------------------------------
    # Per-port desired state extraction
    # ------------------------------------------------------------------
    def _extract_desired_state_for_port(self, request, port_name: str) -> dict:
        """
        Extract row-specific desired values from the POST.

        Expected field names in the template:
        - mode__<port_name>
        - native_vlan__<port_name>
        - allowed_vlans__<port_name>
        - description__<port_name>
        """
        mode = request.POST.get(f"mode__{port_name}", "").strip()
        native_vlan_raw = request.POST.get(f"native_vlan__{port_name}", "").strip()
        allowed_vlans_raw = request.POST.get(f"allowed_vlans__{port_name}", "").strip()
        description = request.POST.get(f"description__{port_name}", "").strip()

        parsed_native_vlan = self._parse_vlan_id(native_vlan_raw)
        parsed_allowed_vlans = self._parse_vlan_list(allowed_vlans_raw)

        return {
            "mode": mode or None,
            "native_vlan": parsed_native_vlan,
            "allowed_vlans": parsed_allowed_vlans or [],
            "description": description or None,
        }

    # ------------------------------------------------------------------
    # Safety helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_connected(interface: Optional[Interface]) -> bool:
        """
        Determine whether the port appears connected in NetBox.
        """
        if not interface:
            return False

        return bool(
            getattr(interface, "cable_id", None)
            or getattr(interface, "mark_connected", False)
        )

    @staticmethod
    def _is_uplink_candidate(interface: Optional[Interface]) -> bool:
        """
        Conservative temporary uplink block.

        This should later be replaced by a dedicated plugin-side uplink flag
        or explicit policy rule.
        """
        if not interface:
            return False

        combined_text = f"{interface.name or ''} {interface.description or ''}".lower()
        markers = ["uplink", "up-link", "wan", "core", "stack", "trunk-uplink"]
        return any(marker in combined_text for marker in markers)

    # ------------------------------------------------------------------
    # VLAN parsing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_vlan_id(value: str):
        """
        Parse a single VLAN ID.
        """
        if not value:
            return None

        try:
            vlan_id = int(value)
        except ValueError:
            return None

        return vlan_id if 1 <= vlan_id <= 4094 else None

    @staticmethod
    def _parse_vlan_list(value: str):
        """
        Parse a VLAN list in the form:
            10,20,30-35
        """
        if not value:
            return []

        parsed = set()

        try:
            for part in value.split(","):
                item = part.strip()
                if not item:
                    continue

                if "-" in item:
                    start_str, end_str = item.split("-", 1)
                    start_vlan = int(start_str.strip())
                    end_vlan = int(end_str.strip())

                    if start_vlan > end_vlan:
                        return None

                    for vlan_id in range(start_vlan, end_vlan + 1):
                        if vlan_id < 1 or vlan_id > 4094:
                            return None
                        parsed.add(vlan_id)
                else:
                    vlan_id = int(item)
                    if vlan_id < 1 or vlan_id > 4094:
                        return None
                    parsed.add(vlan_id)

        except Exception:
            return None

        return sorted(parsed)

    # ------------------------------------------------------------------
    # Payload + diff helpers
    # ------------------------------------------------------------------
    def _build_forti_payload(self, desired_state: dict) -> dict:
        """
        Build a payload for the FortiSwitch update call.

        IMPORTANT:
        Validate the exact payload schema against your FortiOS version.
        """
        payload = {}

        # Proposed mode mapping
        if desired_state.get("mode") == "access":
            payload["mode"] = "access"
        elif desired_state.get("mode") == "trunk":
            payload["mode"] = "trunk"

        # Proposed VLAN keys
        if desired_state.get("native_vlan") is not None:
            payload["native-vlan"] = desired_state["native_vlan"]

        if desired_state.get("allowed_vlans"):
            payload["allowed-vlans"] = " ".join(map(str, desired_state["allowed_vlans"]))

        if desired_state.get("description") is not None:
            payload["description"] = desired_state["description"]

        return payload

    @staticmethod
    def _compare_states(desired_state: dict, actual_state: dict) -> List[dict]:
        """
        Compare desired vs actual state and return only meaningful differences.
        """
        diffs = []

        comparable_fields = [
            ("mode", "Mode"),
            ("native_vlan", "Native VLAN"),
            ("allowed_vlans", "Allowed VLANs"),
            ("description", "Description"),
        ]

        for field_key, label in comparable_fields:
            desired_value = desired_state.get(field_key)
            actual_value = actual_state.get(field_key)

            # Normalise blanks for stable comparisons
            desired_value = [] if desired_value is None and field_key == "allowed_vlans" else desired_value
            actual_value = [] if actual_value is None and field_key == "allowed_vlans" else actual_value

            if desired_value != actual_value:
                diffs.append(
                    {
                        "field": label,
                        "desired": desired_value,
                        "actual": actual_value,
                    }
                )

        return diffs

    @staticmethod
    def _humanise_actual_state(normalised_port: Optional[dict]) -> dict:
        """
        Extract the operator-relevant Forti state from a normalised port row.
        """
        if not normalised_port:
            return {
                "mode": None,
                "native_vlan": None,
                "allowed_vlans": [],
                "description": None,
            }

        return {
            "mode": normalised_port.get("mode"),
            "native_vlan": normalised_port.get("native_vlan"),
            "allowed_vlans": normalised_port.get("allowed_vlans", []),
            "description": normalised_port.get("description"),
        }

    # ------------------------------------------------------------------
    # Bulk port action helpers
    # ------------------------------------------------------------------
    def _handle_port_action(
        self,
        action: str,
        client: FortiAPIClient,
        switch_identifier: str,
        device: Device,
        port_name: str,
        desired_state: dict,
        dry_run: bool,
        warnings_list: List[str],
    ) -> dict:
        """
        Execute one action for one selected port and return a structured result.
        """
        interface = self._get_interface_by_name(device, port_name)

        # Safety warnings/errors at row level
        row_warnings = list(warnings_list)
        row_errors = []

        if self._is_uplink_candidate(interface):
            row_errors.append("Port appears to be an uplink candidate in NetBox.")
        if self._is_connected(interface):
            row_warnings.append("NetBox indicates this port is connected.")

        # Always read current live state first
        live_raw = client.get_port(switch_identifier, port_name)
        live_normalised = client.normalise_port_response(live_raw)
        actual_state = self._humanise_actual_state(live_normalised.get("port"))

        if action == "validate":
            diffs = self._compare_states(desired_state, actual_state)
            return {
                "port_name": port_name,
                "action": "validate",
                "status": "validated" if not row_errors else "blocked",
                "warnings": row_warnings,
                "errors": row_errors,
                "desired_state": desired_state,
                "actual_state": actual_state,
                "diffs": diffs,
            }

        if action == "deploy":
            payload = self._build_forti_payload(desired_state)

            if row_errors:
                return {
                    "port_name": port_name,
                    "action": "deploy",
                    "status": "blocked",
                    "warnings": row_warnings,
                    "errors": row_errors,
                    "desired_state": desired_state,
                    "actual_state": actual_state,
                    "payload": payload,
                    "diffs": self._compare_states(desired_state, actual_state),
                }

            if dry_run:
                return {
                    "port_name": port_name,
                    "action": "deploy",
                    "status": "preview_only",
                    "warnings": row_warnings,
                    "errors": row_errors,
                    "desired_state": desired_state,
                    "actual_state": actual_state,
                    "payload": payload,
                    "diffs": self._compare_states(desired_state, actual_state),
                }

            update_result = client.update_port(
                switch_identifier=switch_identifier,
                port_name=port_name,
                payload=payload,
            )

            live_after_raw = client.get_port(switch_identifier, port_name)
            live_after_normalised = client.normalise_port_response(live_after_raw)
            after_state = self._humanise_actual_state(live_after_normalised.get("port"))

            return {
                "port_name": port_name,
                "action": "deploy",
                "status": "completed",
                "warnings": row_warnings,
                "errors": row_errors,
                "desired_state": desired_state,
                "actual_state": after_state,
                "payload": payload,
                "update_result": {
                    "http_status": update_result.get("http_status"),
                    "status": update_result.get("status"),
                },
                "diffs": self._compare_states(desired_state, after_state),
            }

        if action == "sync":
            return {
                "port_name": port_name,
                "action": "sync",
                "status": "completed",
                "warnings": row_warnings,
                "errors": row_errors,
                "desired_state": None,
                "actual_state": actual_state,
                "diffs": [],
            }

        return {
            "port_name": port_name,
            "action": action,
            "status": "error",
            "warnings": row_warnings,
            "errors": ["Unknown action requested."],
            "desired_state": desired_state,
            "actual_state": actual_state,
            "diffs": [],
        }

    def _summarise_bulk_results(
        self,
        action: str,
        device_name: str,
        bulk_results: List[dict],
    ) -> dict:
        """
        Build a clean, human-readable bulk summary for the template.

        This is deliberately much more readable than dumping raw Forti JSON.
        """
        total = len(bulk_results)
        completed = len([r for r in bulk_results if r["status"] in {"completed", "validated", "preview_only"}])
        blocked = len([r for r in bulk_results if r["status"] == "blocked"])
        changed = len([r for r in bulk_results if r.get("diffs")])

        return {
            "action": action,
            "device_name": device_name,
            "summary": {
                "total_ports": total,
                "completed_ports": completed,
                "blocked_ports": blocked,
                "ports_with_differences": changed,
            },
            "port_results": bulk_results,
        }
