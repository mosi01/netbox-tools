"""
forti_api client for nbtools.forti_api.py

Purpose
-------
- Resolve FortiGate connection details from PLUGINS_CONFIG
- Authenticate using an API token
- Provide helper methods for reading/updating FortiSwitch ports
- Normalise Forti API responses into UI-friendly structures

IMPORTANT
---------
The endpoint paths and payload keys below are a proposed implementation
and must be validated against your FortiOS build before production use.
The code is intentionally centralised here so you only need to adjust
one file if Forti API paths differ in your environment.
"""

from __future__ import annotations

from typing import Any, Dict, List

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

    
    def _load_vlan_mapping(self, site):
        """
        Load VLAN mapping from Forti interfaces.
        Returns:
            dict: {label -> vlan_id}
        """
    
        binding = FortiSiteBinding.objects.filter(site=site, enabled=True).first()
        if not binding:
            return {}
    
        try:
            client = FortiAPIClient(binding)
    
            # You need interface list from Forti
            interfaces = client.get_interfaces()
    
            mapping = {}
    
            for iface in interfaces:
                vlan_id = iface.get("vlanid")
                name = iface.get("name")
    
                if vlan_id and name:
                    mapping[name] = str(vlan_id)
    
            return mapping
    
        except Exception:
            return {}

    
    # ------------------------------------------------------------------
    # Response normalisation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_vlan_names(vlan_value: Any) -> List[str]:
        """
        Convert various Forti VLAN representations into a simple list of names.

        Observed forms include:
        - list of dicts with {"vlan-name": "..."}
        - list of plain strings
        - None / empty
        """
        if not vlan_value:
            return []

        if isinstance(vlan_value, list):
            names = []
            for item in vlan_value:
                if isinstance(item, dict):
                    names.append(item.get("vlan-name") or item.get("q_origin_key") or "")
                else:
                    names.append(str(item))
            return [name for name in names if name]

        return [str(vlan_value)]

    @classmethod
    def normalise_port_record(cls, raw_port: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a raw Forti port record into a UI-friendly structure.

        This deliberately keeps only the fields that matter to the operator.
        """
        allowed_vlans = cls._extract_vlan_names(raw_port.get("allowed-vlans"))
        untagged_vlans = cls._extract_vlan_names(raw_port.get("untagged-vlans"))

        return {
            "port_name": raw_port.get("port-name", ""),
            "switch_id": raw_port.get("switch-id", ""),
            "mode": raw_port.get("mode", ""),
            "native_vlan": raw_port.get("vlan", ""),
            "allowed_vlans": allowed_vlans,
            "untagged_vlans": untagged_vlans,
            "description": raw_port.get("description", "") or "",
            "status": raw_port.get("status", ""),
            "speed": raw_port.get("speed", ""),
            "poe_status": raw_port.get("poe-status", ""),
            "edge_port": raw_port.get("edge-port", ""),
            "dhcp_snooping": raw_port.get("dhcp-snooping", ""),
            "raw": raw_port,
        }

    @classmethod
    def normalise_port_response(cls, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a single-port Forti response into a normalised UI structure.
        """
        results = raw_response.get("results", []) if isinstance(raw_response, dict) else []
        port_record = results[0] if results else {}

        return {
            "http_status": raw_response.get("http_status"),
            "status": raw_response.get("status"),
            "switch_id": raw_response.get("mkey"),
            "port": cls.normalise_port_record(port_record) if port_record else None,
            "raw": raw_response,
        }

    @classmethod
    def normalise_ports_response(cls, raw_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert a multi-port Forti response into a list of normalised rows.
        """
        results = raw_response.get("results", []) if isinstance(raw_response, dict) else []
        return [cls.normalise_port_record(item) for item in results]

