"""
fortigate_policy_toolset.py

Single-page FortiGate / FortiSwitch port tool for NetBox 4.5.0 plugin.

This module is designed to:
- Be imported by views.py
- Contain ALL logic for the Forti tool
- Keep the plugin structure modular and maintainable

IMPORTANT
---------
- This is a controller + validation scaffold
- No real Forti API integration is implemented yet
- Safe to deploy without risk of configuration changes
"""

import logging
from typing import List

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from dcim.models import Device, Interface, Site

logger = logging.getLogger("nbtools")


class FortigatePolicyToolsetView(LoginRequiredMixin, View):
    """
    Single-page Forti tool (controller view)

    Handles:
    - Site selection
    - Device selection
    - Interface selection
    - Validate / Dry-run / Deploy (mock) / Sync (mock)
    """

    template_name = "nbtools/fortigate_policy_toolset.html"

    # ================================================================
    # GET
    # ================================================================
    def get(self, request, *args, **kwargs):

        site_id = request.GET.get("site_id")
        device_id = request.GET.get("device_id")
        interface_id = request.GET.get("interface_id")

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

    # ================================================================
    # POST
    # ================================================================
    def post(self, request, *args, **kwargs):

        submitted_data = {
            "site_id": request.POST.get("site_id", ""),
            "device_id": request.POST.get("device_id", ""),
            "interface_id": request.POST.get("interface_id", ""),
            "mode": request.POST.get("mode", ""),
            "native_vlan": request.POST.get("native_vlan", ""),
            "allowed_vlans": request.POST.get("allowed_vlans", ""),
            "description": request.POST.get("description", ""),
            "action": request.POST.get("action", ""),
            "dry_run": bool(request.POST.get("dry_run")),
        }

        errors_list: List[str] = []
        warnings_list: List[str] = []
        result = None

        # ------------------------------------------------------------
        # Resolve objects
        # ------------------------------------------------------------
        site = self._get_site(submitted_data["site_id"])
        device = self._get_device(submitted_data["device_id"])
        interface = self._get_interface(submitted_data["interface_id"])

        if not site:
            errors_list.append("Invalid site selected.")

        if not device:
            errors_list.append("Invalid device selected.")

        if not interface:
            errors_list.append("Invalid interface selected.")

        if device and site and device.site_id != site.id:
            errors_list.append("Device does not belong to selected site.")

        if interface and device and interface.device_id != device.id:
            errors_list.append("Interface does not belong to device.")

        if errors_list:
            return render(
                request,
                self.template_name,
                self._build_context(
                    submitted_data["site_id"],
                    submitted_data["device_id"],
                    submitted_data["interface_id"],
                    submitted_data,
                    result,
                    warnings_list,
                    errors_list,
                ),
            )

        # ------------------------------------------------------------
        # Safety checks
        # ------------------------------------------------------------
        if self._is_uplink_candidate(interface):
            errors_list.append("Port appears to be an uplink and is blocked.")

        if self._is_connected(interface):
            warnings_list.append("Device may already be connected.")

        # ------------------------------------------------------------
        # Parse VLANs
        # ------------------------------------------------------------
        native_vlan = self._parse_vlan(submitted_data["native_vlan"])
        allowed_vlans = self._parse_vlan_list(submitted_data["allowed_vlans"])

        if submitted_data["native_vlan"] and native_vlan is None:
            errors_list.append("Invalid native VLAN.")

        if submitted_data["allowed_vlans"] and allowed_vlans is None:
            errors_list.append("Invalid allowed VLAN list.")

        if errors_list:
            return render(
                request,
                self.template_name,
                self._build_context(
                    submitted_data["site_id"],
                    submitted_data["device_id"],
                    submitted_data["interface_id"],
                    submitted_data,
                    result,
                    warnings_list,
                    errors_list,
                ),
            )

        desired_state = {
            "mode": submitted_data["mode"],
            "native_vlan": native_vlan,
            "allowed_vlans": allowed_vlans,
            "description": submitted_data["description"],
        }

        action = submitted_data["action"]

        # ------------------------------------------------------------
        # Execute
        # ------------------------------------------------------------
        try:
            if action == "validate":
                result = self._run_validation(interface, desired_state, warnings_list)
                messages.success(request, "Validation complete.")

            elif action == "dry_run":
                result = self._run_dry_run(interface, desired_state)
                messages.success(request, "Dry run complete.")

            elif action == "deploy":
                result = self._run_deploy(interface, desired_state, submitted_data["dry_run"])
                messages.success(request, "Deploy executed.")

            elif action == "sync":
                result = self._run_sync(interface)
                messages.success(request, "Sync complete.")

            else:
                errors_list.append("Unknown action.")

        except Exception as exc:
            logger.exception("Forti action failed")
            errors_list.append(str(exc))

        return render(
            request,
            self.template_name,
            self._build_context(
                submitted_data["site_id"],
                submitted_data["device_id"],
                submitted_data["interface_id"],
                submitted_data,
                result,
                warnings_list,
                errors_list,
            ),
        )

    # ================================================================
    # Context builder
    # ================================================================
    def _build_context(
        self,
        site_id,
        device_id,
        interface_id,
        submitted_data,
        result,
        warnings_list,
        errors_list,
    ):

        sites = Site.objects.all()
        devices = Device.objects.filter(site_id=site_id) if site_id else Device.objects.none()
        interfaces = Interface.objects.filter(device_id=device_id) if device_id else Interface.objects.none()

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

    # ================================================================
    # Helpers
    # ================================================================
    def _get_site(self, pk):
        return Site.objects.filter(pk=pk).first() if pk and pk.isdigit() else None

    def _get_device(self, pk):
        return Device.objects.filter(pk=pk).first() if pk and pk.isdigit() else None

    def _get_interface(self, pk):
        return Interface.objects.filter(pk=pk).first() if pk and pk.isdigit() else None

    def _is_connected(self, interface):
        return bool(interface.cable_id or getattr(interface, "mark_connected", False))

    def _is_uplink_candidate(self, interface):
        text = f"{interface.name} {interface.description}".lower()
        return any(x in text for x in ["uplink", "wan", "core", "stack"])

    def _parse_vlan(self, val):
        try:
            v = int(val)
            return v if 1 <= v <= 4094 else None
        except:
            return None

    def _parse_vlan_list(self, val):
        if not val:
            return []

        try:
            result = set()
            for part in val.split(","):
                part = part.strip()
                if "-" in part:
                    a, b = map(int, part.split("-"))
                    result.update(range(a, b + 1))
                else:
                    result.add(int(part))
            return sorted(result)
        except:
            return None

    # ================================================================
    # Actions (mock)
    # ================================================================
    def _run_validation(self, interface, desired_state, warnings):
        return {
            "type": "validation",
            "interface": str(interface),
            "desired": desired_state,
            "warnings": warnings,
        }

    def _run_dry_run(self, interface, desired_state):
        return {
            "type": "dry_run",
            "interface": str(interface),
            "changes": desired_state,
        }

    def _run_deploy(self, interface, desired_state, dry_run):
        return {
            "type": "deploy",
            "dry_run": dry_run,
            "message": "No Forti API yet (safe mock)",
        }

    def _run_sync(self, interface):
        return {
            "type": "sync",
            "message": "Placeholder sync result",
        }
