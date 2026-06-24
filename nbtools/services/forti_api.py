"""
forti_api.py

FortiGate API client for nbtools.

Purpose
-------
- Resolve FortiGate connection details from PLUGINS_CONFIG
- Authenticate using an API token
- Provide helper methods for reading/updating FortiSwitch ports

IMPORTANT
---------
The endpoint paths and payload keys below are a proposed implementation
and must be validated against your FortiOS build before production use.
The code is intentionally centralised here so you only need to adjust
one file if Forti API paths differ in your environment.
"""

from __future__ import annotations

import requests

from django.conf import settings


class FortiAPIClient:
    """
    Minimal FortiGate API client using token authentication.

    The client expects a FortiSiteBinding instance and resolves:
    - host
    - token
    - vdom
    - verify_ssl
    - switch_identifier_field
    from:
        settings.PLUGINS_CONFIG["nbtools"]["forti"]["sites"][credential_alias]
    """

    def __init__(self, site_binding):
        """
        Build a client from a FortiSiteBinding model instance.
        """
        plugin_cfg = settings.PLUGINS_CONFIG.get("nbtools", {})
        forti_cfg = plugin_cfg.get("forti", {})
        sites_cfg = forti_cfg.get("sites", {})

        alias = site_binding.credential_alias
        site_cfg = sites_cfg.get(alias)

        if not site_cfg:
            raise ValueError(
                f"No Forti plugin config found for alias '{alias}'. "
                "Check PLUGINS_CONFIG['nbtools']['forti']['sites']."
            )

        self.base_url = site_cfg["host"].rstrip("/")
        self.token = site_cfg["token"]
        self.vdom = site_cfg.get("vdom", "root")
        self.verify_ssl = site_cfg.get(
            "verify_ssl",
            forti_cfg.get("default_verify_ssl", True),
        )
        self.switch_identifier_field = site_cfg.get("switch_identifier_field", "name")

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------
    def _request(self, method: str, endpoint: str, data=None):
        """
        Generic Forti API request helper.

        Raises:
            Exception on non-2xx responses
        """
        url = f"{self.base_url}{endpoint}"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        params = {
            "vdom": self.vdom,
        }

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=data,
            verify=self.verify_ssl,
            timeout=30,
        )

        if not response.ok:
            raise Exception(
                f"Forti API request failed: {response.status_code} {response.text}"
            )

        # Forti API commonly returns JSON
        return response.json()

    # ------------------------------------------------------------------
    # Switch identifier helpers
    # ------------------------------------------------------------------
    def get_switch_identifier(self, device):
        """
        Resolve the FortiSwitch identifier to use in API paths.

        Supported modes:
        - "name"   -> device.name
        - "serial" -> device.serial, fallback to device.name
        """
        if self.switch_identifier_field == "serial":
            return device.serial or device.name
        return device.name

    # ------------------------------------------------------------------
    # Proposed FortiSwitch port operations
    # ------------------------------------------------------------------
    def get_switch_ports(self, switch_identifier: str):
        """
        Retrieve all ports for a specific FortiSwitch.

        IMPORTANT:
        Validate this endpoint path against your FortiOS build.
        """
        endpoint = (
            f"/api/v2/cmdb/switch-controller/managed-switch/"
            f"{switch_identifier}/ports"
        )
        return self._request("GET", endpoint)

    def get_port(self, switch_identifier: str, port_name: str):
        """
        Retrieve a specific FortiSwitch port.

        IMPORTANT:
        Validate this endpoint path against your FortiOS build.
        """
        endpoint = (
            f"/api/v2/cmdb/switch-controller/managed-switch/"
            f"{switch_identifier}/ports/{port_name}"
        )
        return self._request("GET", endpoint)

    def update_port(self, switch_identifier: str, port_name: str, payload: dict):
        """
        Update a specific FortiSwitch port.

        IMPORTANT:
        Validate this endpoint path and payload schema against your FortiOS build.
        """
        endpoint = (
            f"/api/v2/cmdb/switch-controller/managed-switch/"
            f"{switch_identifier}/ports/{port_name}"
        )
        return self._request("PUT", endpoint, data=payload)
