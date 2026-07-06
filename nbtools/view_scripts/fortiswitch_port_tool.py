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
"""

from __future__ import annotations

import logging
import re
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
    def _get_first_device_for_site(site_id: int) -> Optional[Device]:
        """
        Return the first device for a site, ordered by name.

        This is intentionally simple because the provided code and sources do
        not define a guaranteed "switch role" filter. If you later want only
        switch-role devices, this helper is the best place to add that filter.
        """
        return Device.objects.filter(site_id=site_id).order_by("name").first()

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

        This populates the editable table automatically from the live Forti
        state, not from stale local assumptions.
        """
        if not site or not device:
            return []

        binding = FortiSiteBinding.objects.filter(site=site, enabled=True).first()
        if not binding
            return []

        try:
            client = FortiAPIClient(binding)
            switch_identifier = client.get_switch_identifier(device)
            raw_ports = client.get_switch_ports(switch_identifier)
            port_rows = client.normalise_ports_response(raw_ports)

            enriched_rows = []
            for row in port_rows:
                interface = self._get_interface_by_name(device, row["port_name"])

                # Ensure only deployable numeric VLANs are rendered to the operator.
                native_vlan = self._coerce_vlan_id(row.get("native_vlan"))
                allowed_vlans = self._extract_numeric_vlans(row.get("allowed_vlans"))

                # Preserve the original row keys where useful, while standardising
                # the VLAN values used by the tool itself.
                row["native_vlan"] = native_vlan
                row["allowed_vlans"] = allowed_vlans

                # Add NetBox safety metadata per row.
                row["netbox_interface_exists"] = bool(interface)
                row["netbox_connected"] = self._is_connected(interface) if interface else False
                row["uplink_candidate"] = self._is_uplink_candidate(interface) if interface else False

                enriched_rows.append(row)

            return enriched_rows

        except Exception as exc:
            logger.exception("Failed to load FortiSwitch ports")
            errors_list.append(f"Could not load ports from Forti: {exc}")
            return []

    def _load_available_vlans(
        self,
        site: Optional[Site],
        device: Optional[Device],
        port_rows: List[dict],
        warnings_list: List[str],
    ) -> List[dict]:
        """
        Load the list of VLANs that should be available in the UI.

        Preferred source
        ----------------
        - Use Forti-side VLAN inventory if the existing FortiAPIClient exposes
          methods for it.

        Fallback source
        ---------------
        - If those client methods are not available, fall back to any numeric
          VLAN IDs already observed on the live switch ports.

        Why this is defensive
        ---------------------
        The provided code snippet includes port methods but does not include the
        FortiAPIClient implementation, so this method is careful to avoid making
        hard assumptions about unavailable client methods.
        """
        if not site or not device:
            return []

        binding = FortiSiteBinding.objects.filter(site=site, enabled=True).first()
        if not      return []

        try:
            client = FortiAPIClient(binding)
            switch_identifier = client.get_switch_identifier(device)

            # ----------------------------------------------------------
            # Preferred path: client exposes explicit VLAN inventory
            # ----------------------------------------------------------
            if hasattr(client, "get_switch_vlans"):
                raw_vlans = client.get_switch_vlans(switch_identifier)

                if hasattr(client, "normalise_vlans_response"):
                    normalised_vlans = client.normalise_vlans_response(raw_vlans)
                    return self._normalise_vlan_choices(normalised_vlans)

                return self._normalise_vlan_choices(raw_vlans)

            # ----------------------------------------------------------
            # Fallback path: build choices from VLAN IDs already seen on
            # the live port data for the selected switch.
            # ----------------------------------------------------------
            observed_vlans = set()
            for row in port_rows:
                native_vlan = self._coerce_vlan_id(row.get("native_vlan"))
                if native_vlan is not None:
                    observed_vlans.add(native_vlan)

                for vlan_id in self._extract_numeric_vlans(row.get("allowed_vlans")):
                    observed_vlans.add(vlan_id)

            return [{"id": vlan_id, "label": str(vlan_id)} for vlan_id in sorted(observed_vlans)]

        except Exception as exc:
            logger.exception("Failed to load available VLAN list")
            warnings_list.append(f"Could not load the full VLAN list from Forti. Falling back where possible. ({exc})")

            # Safe fallback from already-loaded port rows.
            observed_vlans = set()
            for row in port_rows:
                native_vlan = self._coerce_vlan_id(row.get("native_vlan"))
                if native_vlan is not None:
                    observed_vlans.add(native_vlan)

                for vlan_id in self._extract_numeric_vlans(row.get("allowed_vlans")):
                    observed_vlans.add(vlan_id)

            return [{"id": vlan_id, "label": str(vlan_id)} for vlan_id in sorted(observed_vlans)]

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
        if isinstance(raw_vlans, dict):
key in ("results", "items", "vlans", "data"):
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
                # Accept only clean numeric strings.
                if item.isdigit():
                    vlan_id = int(item)
                    label = item

            elif isinstance(item, dict):
                for key in ("id", "vid", "vlan_id", "vlanid"):
                    value = item.get(key)
                    if isinstance(value, int):
                        vlan_id = value
                        break
                    if isinstance(value, str) and value.isdigit():
                        vlan_id = int(value)
                        break

                # Build a friendly label if a name exists.
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
        """
        Extract row-specific desired values from the POST.

        Expected field names in the template:
        - native_vlan__<port_name>
        - allowed_vlans__<port_name>   (multi-select list box)
        - description__<port_name>

        Legacy compatibility:
        - If allowed_vlans__<port_name> arrives as a single CSV string rather
          than a multi-value POST field, it will still be parsed safely.
        """
        native_vlan_raw = request.POST.get(f"native_vlan__{port_name}", "").strip()
        description = request.POST.get(f"description__{port_name}", "").strip()

        # Multi-select list box values arrive as a list.
        allowed_vlan_values = request.POST.getlist(f"allowed_vlans__{port_name}")

        # Backward compatibility for a single text field form.
        if not allowed_vlan_values:
            legacy_allowed_vlans_raw = request.POST.get(f"allowed_vlans__{port_name}", "").strip()
            allowed_vlan_values = [legacy_allowed_vlans_raw] if legacy_allowed_vlans_raw else []

        parsed_native_vlan = self._coerce_vlan_id(native_vlan_raw)
        parsed_allowed_vlans = self._extract_numeric_vlans(allowed_vlan_values)

        return {
            "native_vlan": parsed_native_vlan,
            "allowed_vlans": parsed_allowed_vlans,
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
        - strings containing tokens such as "quarantine" or
          "fortilink.quarantine" (these are ignored)

        Returns

        Sorted list of unique valid numeric VLAN IDs only.
        """
        if value in (None, "", []):
            return []

        parsed = set()

        # Normalise input into a list of string fragments for parsing.
        fragments: List[str] = []

        if isinstance(value, list):
            for item in value:
                if item is None:
                    continue
                fragments.append(str(item))
        else:
            fragments.append(str(value))

        for fragment in fragments:
            # Split on comma and whitespace, but still allow ranges such as 30-35.
            for part in re.split(r"[,\s]+", fragment.strip()):
                item = part.strip()
                if not item:
                    continue

                # Ignore known non-numeric Forti tokens.
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
    def _build_forti_payload(self, desired_state: dict) -> dict:
        """
        Build a payload for the FortiSwitch update call.

        Notes
        -----
        - The "mode" field has been intentionally removed.
        - Allowed VLANs are exported as numeric VLAN IDs only.
        - Non-numeric tokens are never included.
        """
        payload = {}

        if desired_state.get("native_vlan") is not None:
            payload["native-vlan"] = desired_state["native_vlan"]

        if desired_state.get("allowed_vlans") is not None:
            payload["allowed-vlans"] = " ".join(map(str, desired_state["allowed_vlans"]))

        if desired_state.get("description") is not None:
            payload["description"] = desired_state["description"]

        return payload

    @staticmethod
    def _compare_states(desired_state: dict, actual_state: dict) -> List[dict]:
        """
        Compare desired vs actual state and return only meaningful differences.

        The removed "mode" field is intentionally not part of the comparison.
        """
        diffs = []

        comparable_fields = [
            ("native_vlan", "Native VLAN"),
            ("allowed_vlans", "Allowed VLANs"),
scription", "Description"),
        ]

        for field_key, label in comparable_fields:
            desired_value = desired_state.get(field_key)
            actual_value = actual_state.get(field_key)

            # Normalise blanks for stable comparisons.
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

    def _humanise_actual_state(self, normalised_port: Optional[dict]) -> dict:
        """
        Extract the operator-relevant Forti state from a normalised port row.

        Any non-numeric allowed VLAN tokens are filtered out here as well.
        """
        if not normalised_port:
            return {
                "native_vlan": None,
                "allowed_vlans": [],
                "description": None,
            }

        return {
            "native_vlan": self._coerce_vlan_id(normalised_port.get("native_vlan")),
            "allowed_vlans": self._extract_numeric_vlans(normalised_port.get("allowed_vlans", [])),
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

        # Safety warnings/errors at row level.
        row_warnings = list(warnings_list)
        row_errors = []

        if self._is_uplink_candidate(interface):
            row_errors.append("Port appears to be an uplink candidate in NetBox.")
        if self._is_connected(interface):
            row_warnings.append("NetBox indicates this port is connected.")

        # Always read current live state first.
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
