"""
fortiswitch_port_tool.py

Single-page FortiSwitch port tool for the nbtools NetBox plugin.

Purpose
-------
- Select Site / Device
- Automatically load all switch ports from FortiGate
- Auto-select the first device after a site is selected
- Allow bulk selection of multiple ports
- Validate intended switch port settings in bulk
- Preview deploy payloads in bulk
- Deploy changes via FortiGate API in bulk
- Perform manual readback/sync in bulk
- Return structured, human-readable results rather than raw Forti JSON

Design notes
------------
- This file is intentionally modular and designed to be imported by views.py
- It uses FortiSiteBinding + FortiAPIClient
- It remains safe by:
  - warning if a selected interface looks connected in NetBox
  - blocking obvious uplink candidates
- The "mode" field has been removed because this environment does not use
  a per-port FortiSwitch mode setting for this workflow
- Native VLAN is presented as a selectable list
- Allowed VLANs are presented as a multi-select list
- Non-numeric Forti tokens such as "fortilink.quarantine" are filtered out
  so they are never rendered back as deployable VLANs

Key fixes in this version
-------------------------
- Falls back to VLANs observed on ports when explicit Forti VLAN inventory is
  empty (not only when it errors).
- Supports multiple common Forti key shapes such as:
  - native_vlan / native-vlan
  - allowed_vlans / allowed-vlans
  - vlanid / vlan_id / vid / id
- Supports VLAN values arriving as:
  - integers
  - numeric strings
  - CSV/range strings
  - lists
  - dictionaries
  - lists of dictionaries
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Any

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
        If a site is selected and no device is explicitly selected, the first
        device in the site list is auto-selected. If a device is available,
        all Forti ports are loaded immediately.
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
        Render the page and, if possible, load current Forti port state for
        the selected device.

        Important usability change:
        - If a site is selected but no device is selected, automatically pick
          the first available device in that site. This avoids unnecessary
          validation errors caused by selection-only form submits.
        """
        site_id = request.GET.get("site_id", "").strip()
        device_id = request.GET.get("device_id", "").strip()

        site = self._get_site(site_id)

        # Auto-select the first device when a site is selected and no device
        # has yet been chosen by the operator.
        if site and not device_id:
            first_device = self._get_first_device_for_site(site.id)
            if first_device:
                device_id = str(first_device.id)

        device = self._get_device(device_id)

        warnings_list: List[str] = []
        errors_list: List[str] = []

        # Load live ports from Forti for the selected device.
        port_rows = self._load_port_rows(
            site=site,
            device=device,
            warnings_list=warnings_list,
            errors_list=errors_list,
        )

        # Build the available VLAN list used by the UI controls.
        available_vlans = self._load_available_vlans(
            site=site,
            device=device,
            port_rows=port_rows,
            warnings_list=warnings_list,
        )

        context = self._build_context(
            site_id=site_id,
            device_id=device_id,
            submitted_data={},
            port_rows=port_rows,
            available_vlans=available_vlans,
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
        Handle all bulk form actions from the tool.

        Notes
        -----
        - Site/device selection is intentionally handled via GET in the
          template, not POST, to prevent accidental action validation when
          the operator is only changing selections.
        """
        submitted_data = {
            "site_id": request.POST.get("site_id", "").strip(),
            "device_id": request.POST.get("device_id", "").strip(),
            "action": request.POST.get("action", "").strip(),
            "dry_run": bool(request.POST.get("dry_run")),
        }

        selected_ports = [
            p.strip()
            for p in request.POST.getlist("selected_ports")
            if p.strip()
        ]

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

        # --------------------------------------------------------------
        # Resolve Forti site binding
        # --------------------------------------------------------------
        binding = None
        if site:
            binding = FortiSiteBinding.objects.filter(site=site, enabled=True).first()
            if not binding:
                errors_list.append("No enabled Forti site binding exists for the selected site.")

        # Always reload current rows so the page stays populated.
        port_rows = self._load_port_rows(
            site=site,
            device=device,
            warnings_list=warnings_list,
            errors_list=[],
        )

        available_vlans = self._load_available_vlans(
            site=site,
            device=device,
            port_rows=port_rows,
            warnings_list=warnings_list,
        )

        # Validate selected port names against the live Forti port rows.
        available_port_names = {row.get("port_name") for row in port_rows if row.get("port_name")}
        invalid_selected_ports = [p for p in selected_ports if p not in available_port_names]

        if not selected_ports:
            errors_list.append("At least one switch port must be selected.")

        if invalid_selected_ports:
            errors_list.append(
                "One or more selected ports are not present in the live Forti port list: "
                + ", ".join(sorted(invalid_selected_ports))
            )

        if submitted_data["action"] not in {"validate", "deploy", "sync"}:
            errors_list.append("A valid action must be selected.")

        if errors_list:
            context = self._build_context(
                site_id=submitted_data["site_id"],
                device_id=submitted_data["device_id"],
                submitted_data=submitted_data,
                port_rows=port_rows,
                available_vlans=available_vlans,
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
                # Build per-port desired state from submitted row fields.
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

            # Reload rows after action so the page reflects the current live state.
            port_rows = self._load_port_rows(
                site=site,
                device=device,
                warnings_list=warnings_list,
                errors_list=[],
            )

            available_vlans = self._load_available_vlans(
                site=site,
                device=device,
                port_rows=port_rows,
                warnings_list=warnings_list,
            )

        except Exception as exc:
            logger.exception("FortiSwitch port bulk action failed")
            errors_list.append(f"Unexpected error: {exc}")

        context = self._build_context(
            site_id=submitted_data["site_id"],
            device_id=submitted_data["device_id"],
            submitted_data=submitted_data,
            port_rows=port_rows,
            available_vlans=available_vlans,
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
        available_vlans: List[dict],
        result: Optional[dict],
        warnings_list: List[str],
        errors_list: List[str],
    ) -> dict:
        """
        Build page context for both GET and POST.

        Notes
        -----
        - `port_rows` is a normalised list of live Forti ports for the
          selected device.
        - `available_vlans` is a normalised list for UI rendering:
            [
                {"id": 10, "label": "10"},
                {"id": 20, "label": "20"},
            ]
        """
        sites = Site.objects.all().order_by("name")

        selected_site = self._get_site(site_id)
        selected_device = self._get_device(device_id)

        if selected_site:
            devices = Device.objects.filter(site_id=selected_site.id).order_by("name")
        else:
            devices = Device.objects.none()

        return {
            "sites": sites,
            "devices": devices,
            "selected_site": selected_site,
            "selected_device": selected_device,
            "submitted_data": submitted_data,
            "port_rows": port_rows,
            "available_vlans": available_vlans,
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
    def _get_first_device_for_site(site_id: int):
        """
        Return the first device for a site, ordered by name.
        """
        return Device.objects.filter(site_id=site_id).order_by("name").first() 
      
    @staticmethod
    def _get_interface_by_name(device: Device, port_name: str):
        """
        Attempt to map a Forti port name back to a NetBox interface.
        """
        return Interface.objects.filter(device=device, name=port_name).first()

    # ------------------------------------------------------------------
    # Generic row/value helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _get_first_present(mapping: Optional[dict], *keys, default=None):
        """
        Return the first present value from a mapping by trying multiple keys.

        This is used defensively because Forti-normalised responses can vary
        between underscores, hyphens, or other naming styles.
        """
        if not isinstance(mapping, dict):
            return default

        for key in keys:
            if key in mapping:
                return mapping.get(key)

        return default

    @staticmethod
    def _extract_vlan_id_from_dict(value: dict) -> Optional[int]:
        """
        Extract a VLAN ID from a dictionary, if one is present.

        Supported keys:
        - id
        - vid
        - vlan_id
        - vlanid
        """
        if(value, dict):
            return None

        for key in ("id", "vid", "vlan_id", "vlanid"):
            candidate = value.get(key)
            if isinstance(candidate, int) and 1 <= candidate <= 4094:
                return candidate
            if isinstance(candidate, str) and candidate.strip().isdigit():
                candidate_int = int(candidate.strip())
                if 1 <= candidate_int <= 4094:
                    return candidate_int

        return None

    # ------------------------------------------------------------------
    # Port loading helpers
    # ------------------------------------------------------------------
    def _load_port_rows(
        self,
        site,
        device,
        warnings_list,
        errors_list,
    ):
        """
        Load FortiSwitch ports using raw Forti data.
    
        - Native VLAN = value from "vlan"
        - Allowed VLANs = values from "allowed-vlans"
        - No numeric parsing
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
    
            # Handle Forti response
            if isinstance(raw_ports, dict):
                port_rows = raw_ports.get("results", [])
            else:
                port_rows = raw_ports
    
            enriched_rows = []
    
            for row in port_rows:
                if not isinstance(row, dict):
                    continue
    
                port_name = row.get("port-name")
                if not port_name:
                    continue
    
                # Native VLAN
                native_vlan = row.get("vlan")
    
                # Allowed VLANs
                allowed_vlans = []
                raw_allowed = row.get("allowed-vlans", [])
    
                if isinstance(raw_allowed, list):
                    for item in raw_allowed:
                        if isinstance(item, dict):
                            vlan_name = item.get("vlan-name")
                            if vlan_name:
                                allowed_vlans.append(vlan_name)
    
                interface = self._get_interface_by_name(device, port_name)
    
                enriched_rows.append({
                    "port_name": port_name,
                    "native_vlan": native_vlan,
                    "allowed_vlans": allowed_vlans,
                    "description": row.get("description"),
                    "netbox_interface_exists": bool(interface),
                    "netbox_connected": self._is_connected(interface) if interface else False,
                    "uplink_candidate": self._is_uplink_candidate(interface) if interface else False,
                })
    
            return enriched_rows
    
        except Exception as exc:
            logger.exception("Failed to load FortiSwitch ports")
            errors_list.append("Error loading ports: " + str(exc))
            return []
    
    def _build_observed_vlan_choices(self, port_rows: List[dict]) -> List[dict]:
        """
        Build VLAN choices from the VLANs already observed in live port rows.

        This is the primary fallback when explicit VLAN inventory is unavailable
        or empty.
        """
        observed_vlans = set()

        for row in port_rows:
            native_vlan = self._coerce_vlan_id(
                self._get_first_present(
                    row,
                    "native_vlan",
                    "native-vlan",
                    "nativeVlan",
                    "native",
                    default=None,
                )
            )
            if native_vlan is not None:
                observed_vlans.add(native_vlan)

            raw_allowed_vlans = self._get_first_present(
                row,
                "allowed_vlans",
                "allowed-vlans",
                "allowedVlans",
                "allowed",
                default=None,
            )

            for vlan_id in self._extract_numeric_vlans(raw_allowed_vlans):
                observed_vlans.add(vlan_id)

        return [{"id": vlan_id, "label": str(vlan_id)} for vlan_id in sorted(observed_vlans)]

    
    def _load_available_vlans(
        self,
        site,
        device,
        port_rows,
        warnings_list,
    ):
        """
        Build VLAN list from port data using names.
        """
    
        if not port_rows:
            return []
    
        observed_vlans = set()
    
        for row in port_rows:
            nv = row.get("native_vlan")
            if nv:
                observed_vlans.add(nv)
    
            for v in row.get("allowed_vlans", []):
                observed_vlans.add(v)
    
        result = []
        for v in sorted(observed_vlans):
            result.append({"id": v, "label": v})
    
        return result


    @staticmethod
    def _normalise_vlan_choices(raw_vlans) -> List[dict]:
        """
        Convert various possible VLAN response shapes into a stable UI list.

        Supported output format
        -----------------------
        [
            {"id": 10, "label": "10"},
            {"id": 20, "label": "20"},
        ]

        This helper is intentionally tolerant because the Forti client code was
        not provided in the published snippet.
        """
        choices = {}

        if raw_vlans is None:
            return []

        # If the result is a dict, try common envelope keys first.
        if isinstance(vlans, dict):
            for key in ("results", "items", "vlans", "data"):
                if isinstance(raw_vlans.get(key), list):
                    raw_vlans = raw_vlans[key]
                    break

        if not isinstance(raw_vlans, list):
            return []

        for item in raw_vlans:
            vlan_id = None
            label = None

            if isinstance(item, int):
                vlan_id = item
                label = str(item)

            elif isinstance(item, str):
                stripped = item.strip()
                if stripped.isdigit():
                    vlan_id = int(stripped)
                    label = stripped

            elif isinstance(item, dict):
                vlan_id = FortiSwitchPortToolView._extract_vlan_id_from_dict(item)

                if vlan_id is not None:
                    name = item.get("name") or item.get("interface") or item.get("description")
                    label = f"{vlan_id} - {name}" if name else str(vlan_id)

            if vlan_id is not None and 1 <= vlan_id <= 4094:
                choices[vlan_id] = label or str(vlan_id)

        return [{"id": vlan_id, "label": choices[vlan_id]} for vlan_id in sorted(choices)]

    # ------------------------------------------------------------------
    # Per-port desired state extraction
    # ------------------------------------------------------------------
    
    def _extract_desired_state_for_port(self, request, port_name: str) -> dict:
    
        native_vlan = request.POST.get(f"native_vlan__{port_name}", "").strip()
        description = request.POST.get(f"description__{port_name}", "").strip()
    
        allowed_vlan_values = request.POST.getlist(f"allowed_vlans__{port_name}")
    
        if not allowed_vlan_values:
            tmp = request.POST.get(f"allowed_vlans__{port_name}", "").strip()
            if tmp:
                allowed_vlan_values = [tmp]
            else:
                allowed_vlan_values = []
    
        return {
            "native_vlan": native_vlan or None,
            "allowed_vlans": allowed_vlan_values,
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
    # VLAN parsing and normalisation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_vlan_id(value):
        """
        Coerce a single VLAN value to an integer VLAN ID if possible.

        Returns
        -------
        - int for valid VLAN IDs in range 1..4094
        - None for blanks, invalid values, or non-numeric tokens
        """
        if value in (None, "", []):
            return None

        if isinstance(value, dict):
            extracted = FortiSwitchPortToolView._extract_vlan_id_from_dict(value)
            return extracted

        if isinstance(value, int):
            return value if 1 <= value <= 4094 else None

        value_str = str(value).strip()
        if not value_str.isdigit():
            return None

        vlan_id = int(value_str)
        return vlan_id if 1 <= vlan_id <= 4094 else None

    def _extract_numeric_vlans(self, value) -> List[int]:
        """
        Extract numeric VLAN IDs from a variety of possible input shapes.

        Accepted inputs
        ---------------
        - [10, 20, 30]
        - ["10", "20", "30"]
        - "10,20,30-35"
        - "10 20 30"
        - ["10,20", "30"]
        - [{"id": 10}, {"vlanid": "20"}]
        - strings containing tokens such  or
          "fortilink.quarantine" (these are ignored)

        Returns
        -------
        Sorted list of unique valid numeric VLAN IDs only.
        """
        if value in (None, "", []):
            return []

        parsed = set()

        # Normalise input into a list of fragments for parsing.
        fragments: List[Any] = []

        if isinstance(value, list):
            fragments.extend(value)
        else:
            fragments.append(value)

        for fragment in fragments:
            if fragment is None:
                continue

            # Direct integer support.
            if isinstance(fragment, int):
                if 1 <= fragment <= 4094:
                    parsed.add(fragment)
                continue

            # Dictionary support.
            if isinstance(fragment, dict):
                vlan_id = self._extract_vlan_id_from_dict(fragment)
                if vlan_id is not None:
                    parsed.add(vlan_id)
                continue

            # String support.
            fragment_str = str(fragment).strip()
            if not fragment_str:
                continue

            # Split on comma and whitespace, but still allow ranges such as 30-35.
            for part in re.split(r"[,\s]+", fragment_str):
                item = part.strip()
                if not item:
                    continue

                # Ignore tokens with no digits at all.
                if not re.search(r"\d", item):
                    continue

                if "-" in item:
                    start_str, end_str = item.split("-", 1)

                    if not start_str.strip().isdigit() or not end_str.strip().isdigit():
                        continue

                    start_vlan = int(start_str.strip())
                    end_vlan = int(end_str.strip())

                    if start_vlan > end_vlan:
                        continue

                    for vlan_id in range(start_vlan, end_vlan + 1):
                        if 1 <= vlan_id <= 4094:
                            parsed.add(vlan_id)
                else:
                    if item.isdigit():
                        vlan_id = int(item)
                        if 1 <= vlan_id <= 4094:
                            parsed.add(vlan_id)

        return sorted(parsed)

    # ------------------------------------------------------------------
    # Payload + diff helpers
    # ------------------------------------------------------------------
    
    def _build_forti_payload(self, desired_state: dict, actual_state: dict) -> dict:
    
        payload = {}
    
        # Native VLAN
        if desired_state.get("native_vlan") != actual_state.get("native_vlan"):
            if desired_state.get("native_vlan"):
                payload["vlan"] = desired_state["native_vlan"]
    
        # Allowed VLANs
        if desired_state.get("allowed_vlans") != actual_state.get("allowed_vlans"):
            if desired_state.get("allowed_vlans"):
                payload["allowed-vlans"] = desired_state["allowed_vlans"]
    
        # Description
        if desired_state.get("description") != actual_state.get("description"):
            payload["description"] = desired_state.get("description")
    
        return payload



    @staticmethod
    def _compare_states(desired_state: dict, actual_state: dict) -> List:
        """
        Compare desired and actual state and return differences.
        """
    
        diffs = []
    
        fields = ["native_vlan", "allowed_vlans", "description"]
    
        for f in fields:
            if desired_state.get(f) != actual_state.get(f):
                diffs.append({
                    "field": f,
                    "desired": desired_state.get(f),
                    "actual": actual_state.get(f),
                })
    
        return diffs



    def _humanise_actual_state(self, normalised_port: Optional[dict]) -> dict:
    
        if not normalised_port:
            return {
                "native_vlan": None,
                "allowed_vlans": [],
                "description": None,
            }
    
        port = normalised_port
    
        native_vlan = port.get("vlan")
    
        allowed_vlans = []
        for item in port.get("allowed-vlans", []):
            if isinstance(item, dict):
                name = item.get("vlan-name")
                if name:
                    allowed_vlans.append(name)
    
        return {
            "native_vlan": native_vlan,
            "allowed_vlans": allowed_vlans,
            "description": port.get("description"),
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
    
        interface = self._get_interface_by_name(device, port_name)
    
        row_warnings = list(warnings_list)
        row_errors = []
    
        if self._is_uplink_candidate(interface):
            row_errors.append("Port appears to be an uplink candidate in NetBox.")
    
        if self._is_connected(interface):
            row_warnings.append("NetBox indicates this port is connected.")
    
        live_raw = client.get_port(switch_identifier, port_name)
        live_normalised = client.normalise_port_response(live_raw)
    
        actual_state = self._humanise_actual_state(live_normalised.get("port"))
    
        diffs = self._compare_states(desired_state, actual_state)
    
        # BUILD PAYLOAD FROM DIFF ONLY
        payload = self._build_forti_payload(desired_state, actual_state)
    
        if action == "validate":
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
                    "diffs": diffs,
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
                    "diffs": diffs,
                }
    
            # Only call API if payload not empty
            update_result = {}
            if payload:
                update_result = client.update_port(
                    switch_identifier=switch_identifier,
                    port_name=port_name,
                    payload=payload,
                )
    
            return {
                "port_name": port_name,
                "action": "deploy",
                "status": "completed",
                "warnings": row_warnings,
                "errors": row_errors,
                "desired_state": desired_state,
                "actual_state": actual_state,
                "payload": payload,
                "update_result": update_result,
                "diffs": diffs,
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
        completed = len(
            [r for r in bulk_results if r["status"] in {"completed", "validated", "preview_only"}]
        )
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
