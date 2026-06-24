"""
fortiswitch_port_tool.py

Single-page FortiSwitch port tool for the nbtools NetBox plugin.

Purpose
-------
- Select Site / Device / Interface
- Validate intended switch port settings
- Preview changes with dry-run
- Deploy changes via FortiGate API
- Perform manual readback/sync

Notes
-----
- This file is intentionally modular and designed to be imported by views.py
- It uses FortiSiteBinding + FortiAPIClient
- It remains safe by:
  - warning if an interface looks connected in NetBox
  - blocking obvious uplink candidates
- Endpoint paths/payload keys used by the Forti client are proposed and
  must be validated against your FortiOS version
"""

from __future__ import annotations

import logging
from typing import List, Optional

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
    Single-page FortiSwitch port operations tool.

    Supported actions
    -----------------
    - validate
    - dry_run
    - deploy
    - sync
    """

    template_name = "nbtools/fortiswitch_port_tool.html"

    # ------------------------------------------------------------------
    # HTTP GET
    # ------------------------------------------------------------------
    def get(self, request):
        """
        Render the starting page.
        """
        site_id = request.GET.get("site_id", "").strip()
        device_id = request.GET.get("device_id", "").strip()
        interface_id = request.GET.get("interface_id", "").strip()

        context = self._build_context(
            site_id=site_id,
            device_id=device_id,
            interface_id=interface_id,
            submitted_data={},
            result=None,
            warnings_list=[],
            errors_list=[],
        )
        return render(request, self.template_name, context)

    # ------------------------------------------------------------------
    # HTTP POST
    # ------------------------------------------------------------------
    def post(self, request):
        """
        Handle all form actions from the single-page tool.
        """
        submitted_data = {
            "site_id": request.POST.get("site_id", "").strip(),
            "device_id": request.POST.get("device_id", "").strip(),
            "interface_id": request.POST.get("interface_id", "").strip(),
            "mode": request.POST.get("mode", "").strip(),
            "native_vlan": request.POST.get("native_vlan", "").strip(),
            "allowed_vlans": request.POST.get("allowed_vlans", "").strip(),
            "description": request.POST.get("description", "").strip(),
            "action": request.POST.get("action", "").strip(),
            "dry_run": bool(request.POST.get("dry_run")),
        }

        errors_list: List[str] = []
        warnings_list: List[str] = []
        result = None

        # --------------------------------------------------------------
        # Resolve selected objects
        # --------------------------------------------------------------
        site = self._get_site(submitted_data["site_id"])
        device = self._get_device(submitted_data["device_id"])
        interface = self._get_interface(submitted_data["interface_id"])

        if not site:
            errors_list.append("A valid site must be selected.")

        if not device:
            errors_list.append("A valid device must be selected.")

        if not interface:
            errors_list.append("A valid interface must be selected.")

        if site and device and device.site_id != site.id:
            errors_list.append("The selected device does not belong to the selected site.")

        if device and interface and interface.device_id != device.id:
            errors_list.append("The selected interface does not belong to the selected device.")

        if errors_list:
            context = self._build_context(
                site_id=submitted_data["site_id"],
                device_id=submitted_data["device_id"],
                interface_id=submitted_data["interface_id"],
                submitted_data=submitted_data,
                result=result,
                warnings_list=warnings_list,
                errors_list=errors_list,
            )
            return render(request, self.template_name, context)

        # --------------------------------------------------------------
        # Resolve Forti site binding
        # --------------------------------------------------------------
        binding = FortiSiteBinding.objects.filter(site=site, enabled=True).first()
        if not binding:
            errors_list.append(
                "No enabled Forti site binding exists for the selected site."
            )

        # --------------------------------------------------------------
        # Safety checks
        # --------------------------------------------------------------
        if self._is_uplink_candidate(interface):
            errors_list.append(
                "This interface appears to be an uplink and is blocked from configuration changes."
            )

        if self._is_connected(interface):
            warnings_list.append(
                "Warning: a device/client may already be connected to this port."
            )

        # --------------------------------------------------------------
        # Parse intended state
        # --------------------------------------------------------------
        parsed_native_vlan = self._parse_vlan_id(submitted_data["native_vlan"])
        parsed_allowed_vlans = self._parse_vlan_list(submitted_data["allowed_vlans"])

        if submitted_data["mode"] and submitted_data["mode"] not in {"access", "trunk"}:
            errors_list.append("Mode must be either 'access' or 'trunk'.")

        if submitted_data["native_vlan"] and parsed_native_vlan is None:
            errors_list.append("Native VLAN must be an integer between 1 and 4094.")

        if submitted_data["allowed_vlans"] and parsed_allowed_vlans is None:
            errors_list.append(
                "Allowed VLANs must be a comma-separated list of VLAN IDs and/or ranges."
            )

        if errors_list:
            context = self._build_context(
                site_id=submitted_data["site_id"],
                device_id=submitted_data["device_id"],
                interface_id=submitted_data["interface_id"],
                submitted_data=submitted_data,
                result=result,
                warnings_list=warnings_list,
                errors_list=errors_list,
            )
            return render(request, self.template_name, context)

        desired_state = {
            "mode": submitted_data["mode"] or None,
            "native_vlan": parsed_native_vlan,
            "allowed_vlans": parsed_allowed_vlans or [],
            "description": submitted_data["description"] or None,
        }

        action = submitted_data["action"]

        try:
            # Build the Forti client only once we know we need it
            client = FortiAPIClient(binding)
            switch_identifier = client.get_switch_identifier(device)

            if action == "validate":
                result = self._run_validation(
                    client=client,
                    switch_identifier=switch_identifier,
                    interface=interface,
                    desired_state=desired_state,
                    warnings_list=warnings_list,
                )
                messages.success(request, "Validation completed successfully.")

            elif action == "dry_run":
                result = self._run_dry_run(
                    client=client,
                    switch_identifier=switch_identifier,
                    interface=interface,
                    desired_state=desired_state,
                )
                messages.success(request, "Dry-run completed successfully.")

            elif action == "deploy":
                result = self._run_deploy(
                    client=client,
                    switch_identifier=switch_identifier,
                    interface=interface,
                    desired_state=desired_state,
                    dry_run=submitted_data["dry_run"],
                )
                messages.success(request, "Deploy action completed.")

            elif action == "sync":
                result = self._run_sync(
                    client=client,
                    switch_identifier=switch_identifier,
                    interface=interface,
                )
                messages.success(request, "Manual sync completed.")

            else:
                errors_list.append("Unknown action requested.")

        except Exception as exc:
            logger.exception("FortiSwitch port tool action failed")
            errors_list.append(f"Unexpected error: {exc}")

        context = self._build_context(
            site_id=submitted_data["site_id"],
            device_id=submitted_data["device_id"],
            interface_id=submitted_data["interface_id"],
            submitted_data=submitted_data,
            result=result,
            warnings_list=warnings_list,
            errors_list=errors_list,
        )
        return render(request, self.template_name, context)

    # ------------------------------------------------------------------
    # UI/context helper
    # ------------------------------------------------------------------
    def _build_context(
        self,
        site_id: str,
        device_id: str,
        interface_id: str,
        submitted_data: dict,
        result: Optional[dict],
        warnings_list: List[str],
        errors_list: List[str],
    ) -> dict:
        """
        Build the page context for both GET and POST.
        """
        sites = Site.objects.all().order_by("name")

        if site_id and site_id.isdigit():
            devices = Device.objects.filter(site_id=site_id).order_by("name")
        else:
            devices = Device.objects.none()

        if device_id and device_id.isdigit():
            interfaces = Interface.objects.filter(device_id=device_id).order_by("name")
        else:
            interfaces = Interface.objects.none()

        return {
            "sites": sites,
            "devices": devices,
            "interfaces": interfaces,
            "selected_site": self._get_site(site_id),
            "selected_device": self._get_device(device_id),
            "selected_interface": self._get_interface(interface_id),
            "submitted_data": submitted_data,
            "result": result,
            "warnings_list": warnings_list,
            "errors_list": errors_list,
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
    def _get_interface(interface_id: str):
        """
        Resolve an Interface safely by primary key.
        """
        return (
            Interface.objects.select_related("device", "device__site").filter(pk=interface_id).first()
            if interface_id and interface_id.isdigit()
            else None
        )

    # ------------------------------------------------------------------
    # Safety helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_connected(interface: Interface) -> bool:
        """
        Determine whether the port appears connected in NetBox.
        """
        return bool(
            getattr(interface, "cable_id", None)
            or getattr(interface, "mark_connected", False)
        )

    @staticmethod
    def _is_uplink_candidate(interface: Interface) -> bool:
        """
        Conservative temporary uplink block.

        This should later be replaced by a dedicated plugin-side uplink flag
        or explicit policy rule.
        """
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
    # Forti action helpers
    # ------------------------------------------------------------------
    def _build_forti_payload(self, desired_state: dict) -> dict:
        """
        Build a payload for the proposed FortiSwitch port update call.

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
            # Many Forti APIs represent VLAN lists as a space-separated string
            payload["allowed-vlans"] = " ".join(map(str, desired_state["allowed_vlans"]))

        if desired_state.get("description"):
            payload["description"] = desired_state["description"]

        return payload

    def _run_validation(
        self,
        client: FortiAPIClient,
        switch_identifier: str,
        interface: Interface,
        desired_state: dict,
        warnings_list: List[str],
    ) -> dict:
        """
        Validate intended state and retrieve current live state from Forti.
        """
        live_state = client.get_port(switch_identifier, interface.name)

        return {
            "action": "validate",
            "interface": f"{interface.device.name}:{interface.name}",
            "desired_state": desired_state,
            "live_state": live_state,
            "warnings": warnings_list,
            "status": "validated",
        }

    def _run_dry_run(
        self,
        client: FortiAPIClient,
        switch_identifier: str,
        interface: Interface,
        desired_state: dict,
    ) -> dict:
        """
        Build a dry-run preview by reading the current live state and
        comparing it with the desired payload.
        """
        live_state = client.get_port(switch_identifier, interface.name)
        payload = self._build_forti_payload(desired_state)

        return {
            "action": "dry_run",
            "interface": f"{interface.device.name}:{interface.name}",
            "desired_state": desired_state,
            "payload": payload,
            "live_state": live_state,
            "status": "preview_only",
        }

    def _run_deploy(
        self,
        client: FortiAPIClient,
        switch_identifier: str,
        interface: Interface,
        desired_state: dict,
        dry_run: bool,
    ) -> dict:
        """
        Deploy the intended port configuration and immediately read it back.

        If dry_run is set, do not call Forti update.
        """
        payload = self._build_forti_payload(desired_state)
        live_before = client.get_port(switch_identifier, interface.name)

        if dry_run:
            return {
                "action": "deploy",
                "interface": f"{interface.device.name}:{interface.name}",
                "dry_run": True,
                "payload": payload,
                "before": live_before,
                "status": "preview_only",
            }

        update_result = client.update_port(
            switch_identifier=switch_identifier,
            port_name=interface.name,
            payload=payload,
        )

        # Always read back live state after a real deploy
        live_after = client.get_port(switch_identifier, interface.name)

        return {
            "action": "deploy",
            "interface": f"{interface.device.name}:{interface.name}",
            "dry_run": False,
            "payload": payload,
            "before": live_before,
            "update_result": update_result,
            "after": live_after,
            "status": "completed",
        }

    def _run_sync(
        self,
        client: FortiAPIClient,
        switch_identifier: str,
        interface: Interface,
    ) -> dict:
        """
        Read the current state of the selected port from Forti.
        """
        live_state = client.get_port(switch_identifier, interface.name)

        return {
            "action": "sync",
            "interface": f"{interface.device.name}:{interface.name}",
            "live_state": live_state,
            "status": "completed",
        }
