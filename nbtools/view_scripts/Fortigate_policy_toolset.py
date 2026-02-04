"""
Fortigate_policy_toolset.py

View for the "Fortigate Policy Toolset" in the nbtools plugin.

Features:
- Import Fortinet firewall policy rules from a JSON file.
- Display rules in an editable table (per request/session only, no DB storage).
- Validate rules:
  - Highlight any-to-any rules.
  - Highlight duplicate rules (same src, dst, services, action).
- Test traffic:
  - Given src IP, dst IP, protocol and port, show first matching rule and action.
- Export:
  - JSON (similar to original input structure).
  - CSV.

This view intentionally does NOT persist any data in NetBox models or plugin DB tables.
All state is carried in the POSTed form fields for each request.
"""

import json
import logging
from ipaddress import ip_address, ip_network

from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger("nbtools")


@method_decorator(csrf_exempt, name="dispatch")
class FortigatePolicyToolsetView(View):
    """
    Main view class for the Fortigate Policy Toolset.

    Supported actions (via POST "action" field):
    - upload_file: Load rules from uploaded JSON file.
    - validate: Run rule validation (any-to-any, duplicates).
    - test: Simulate traffic against the rules.
    - export_json: Download current (possibly edited) rules as JSON.
    - export_csv: Download current (possibly edited) rules as CSV.

    The source of truth for rules (after upload) are the table fields in the form.
    We reconstruct the rules from POST keys on every non-upload request.
    """

    template_name = "nbtools/fortigate_policy_toolset.html"

    # Keys that should be treated as lists in the JSON structure
    LIST_FIELDS = {
        "From",
        "To",
        "Source",
        "Destination",
        "Schedule",
        "Service",
        "IP Pool",
        "Security Profiles",
    }

    # Default mapping for common named services (best-effort)
    # NOTE: This is an approximation and may not reflect custom FortiGate service objects.
    SERVICE_PORT_MAP = {
        "HTTP": ("tcp", 80),
        "HTTPS": ("tcp", 443),
        "RDP": ("tcp", 3389),
        "FTP": ("tcp", 21),
        "SSH": ("tcp", 22),
        "SMTP": ("tcp", 25),
        "NTP": ("udp", 123),
        "SNMP": ("udp", 161),
    }

    def get(self, request):
        """
        Initial GET: display empty page with upload form.
        """
        context = {
            "rules": [],
            "errors": [],
            "validation": {},
            "test_result": None,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        """
        Handle all actions via POST.
        """
        action = request.POST.get("action")
        errors = []
        rules = []

        # 1) Handle file upload
        if action == "upload_file":
            uploaded_file = request.FILES.get("rules_file")
            if not uploaded_file:
                errors.append("No JSON file provided.")
            else:
                try:
                    file_content = uploaded_file.read().decode("utf-8")
                    rules, parse_errors = self._parse_rules_from_json(file_content)
                    errors.extend(parse_errors)
                except UnicodeDecodeError as exc:
                    logger.exception("Failed to decode uploaded file as UTF-8")
                    errors.append(
                        f"Failed to decode uploaded file as UTF-8: {exc}"
                    )
                except Exception as exc:  # Generic safety net
                    logger.exception("Unexpected error while processing upload")
                    errors.append(f"Unexpected error while processing upload: {exc}")

            context = {
                "rules": rules,
                "errors": errors,
                "validation": self._build_empty_validation(rules),
                "test_result": None,
            }
            return render(request, self.template_name, context)

        # 2) For all other actions, reconstruct rules from the table fields in POST
        rules, rebuild_errors = self._rebuild_rules_from_post(request.POST)
        errors.extend(rebuild_errors)

        # If we have no rules at this point, most actions are meaningless
        if not rules and action not in {"export_json", "export_csv"}:
            errors.append("No rules loaded. Please upload a JSON file first.")
            context = {
                "rules": [],
                "errors": errors,
                "validation": {},
                "test_result": None,
            }
            return render(request, self.template_name, context)

        # 3) Validate
        validation = self._build_empty_validation(rules)
        if action == "validate":
            validation = self._validate_rules(rules)

        # 4) Test traffic
        test_result = None
        if action == "test":
            test_result = self._test_traffic(request.POST, rules, errors)

        # 5) Export JSON
        if action == "export_json":
            return self._export_json_response(rules)

        # 6) Export CSV
        if action == "export_csv":
            return self._export_csv_response(rules)

        # 7) Default: re-render page
        context = {
            "rules": rules,
            "errors": errors,
            "validation": validation,
            "test_result": test_result,
        }
        return render(request, self.template_name, context)

    # -------------------------------------------------------------------------
    # Parsing / reconstruction helpers
    # -------------------------------------------------------------------------

    def _parse_rules_from_json(self, raw_json: str):
        """
        Parse rules from a JSON string.

        Expected format: a JSON array of objects (one per rule).

        Returns:
            (rules_list, errors_list)
        """
        errors = []
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON: {exc}")
            return [], errors

        if not isinstance(data, list):
            errors.append(
                "JSON root must be a list of policy objects (e.g. [ { ... }, { ... } ])."
            )
            return [], errors

        rules = []
        for idx, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                errors.append(f"Entry #{idx} is not an object and was skipped.")
                continue

            # Ensure all known list fields are lists
            for key in self.LIST_FIELDS:
                if key in item and not isinstance(item[key], list):
                    # Simple automatic fix: wrap as list
                    item[key] = [item[key]]

            # Ensure required minimal fields exist - we can still proceed if missing,
            # but we log them so user can fix them if needed.
            for required in ("Policy", "From", "To", "Source", "Destination", "Action"):
                if required not in item:
                    errors.append(
                        f"Rule #{idx} is missing required field '{required}'. "
                        "It will still be loaded but may not behave as expected."
                    )

            rules.append(item)

        return rules, errors

    def _rebuild_rules_from_post(self, post_data):
        """
        Reconstruct rules from the POSTed table form.

        We assume fields are named as:
            rule-<index>-<FieldName>

        Example:
            rule-0-Policy, rule-0-Source, rule-0-Destination, ...

        Returns:
            (rules_list, errors_list)
        """
        errors = []
        rules_by_idx = {}

        for key, value in post_data.items():
            if not key.startswith("rule-"):
                continue

            try:
                _, idx_str, field_name = key.split("-", 2)
                idx = int(idx_str)
            except ValueError:
                # Ignore non-conforming fields
                continue

            if idx not in rules_by_idx:
                rules_by_idx[idx] = {}

            field_value = value.strip()

            # List fields: split on comma
            if field_name in self.LIST_FIELDS:
                if not field_value:
                    rules_by_idx[idx][field_name] = []
                else:
                    # Split on commas, strip whitespace
                    rules_by_idx[idx][field_name] = [
                        part.strip() for part in field_value.split(",") if part.strip()
                    ]
            else:
                rules_by_idx[idx][field_name] = field_value

        # Sort by index to preserve order
        rules = [rules_by_idx[i] for i in sorted(rules_by_idx.keys())]

        return rules, errors

    # -------------------------------------------------------------------------
    # Validation logic
    # -------------------------------------------------------------------------

    def _build_empty_validation(self, rules):
        """
        Build an empty validation structure for the given rules length.

        Returns:
            {
                "any_any": set of rule indexes (0-based),
                "duplicates": {index: group_id, ...}
            }
        """
        return {
            "any_any": set(),
            "duplicates": {},
        }

    def _validate_rules(self, rules):
        """
        Validate:
        - Any-to-any rules.
        - Duplicates (same Source, Destination, Services, Action).

        Returns:
            validation dict as in _build_empty_validation().
        """
        validation = self._build_empty_validation(rules)

        # 1) Any-to-any
        for idx, rule in enumerate(rules):
            src = rule.get("Source", [])
            dst = rule.get("Destination", [])

            if self._is_any_list(src) and self._is_any_list(dst):
                validation["any_any"].add(idx)

        # 2) Duplicate detection
        signature_map = {}
        for idx, rule in enumerate(rules):
            src = tuple(sorted(rule.get("Source", [])))
            dst = tuple(sorted(rule.get("Destination", [])))
            services = tuple(sorted(rule.get("Service", [])))
            action = rule.get("Action", "")

            signature = (src, dst, services, action)
            signature_map.setdefault(signature, []).append(idx)

        group_id = 1
        for idx_list in signature_map.values():
            if len(idx_list) > 1:
                for idx in idx_list:
                    validation["duplicates"][idx] = group_id
                group_id += 1

        return validation

    def _is_any_list(self, values):
        """
        Determine if a list-like field represents "any".

        Heuristics:
        - Contains the literal "all".
        - Contains Net.0.0.0.0/0.
        """
        if not values:
            return False
        lowered = [v.lower() for v in values]
        if "all" in lowered:
            return True
        for v in lowered:
            if v.startswith("net.0.0.0.0/0"):
                return True
        return False

    # -------------------------------------------------------------------------
    # Test traffic logic
    # -------------------------------------------------------------------------

    def _test_traffic(self, post_data, rules, errors):
        """
        Simulate traffic against the rules.

        Expected POST fields:
            test_src_ip
            test_dst_ip
            test_protocol (e.g. tcp/udp/icmp)
            test_port (integer; not used for ICMP)

        Returns:
            dict with matched rule info, or a description if no match.
        """
        src_ip_str = post_data.get("test_src_ip", "").strip()
        dst_ip_str = post_data.get("test_dst_ip", "").strip()
        protocol = post_data.get("test_protocol", "").strip().lower()
        port_str = post_data.get("test_port", "").strip()

        if not src_ip_str or not dst_ip_str or not protocol:
            errors.append("Test requires source IP, destination IP and protocol.")
            return None

        try:
            src_ip = ip_address(src_ip_str)
        except ValueError:
            errors.append(f"Invalid source IP address: {src_ip_str}")
            return None

        try:
            dst_ip = ip_address(dst_ip_str)
        except ValueError:
            errors.append(f"Invalid destination IP address: {dst_ip_str}")
            return None

        if protocol not in {"tcp", "udp", "icmp"}:
            errors.append("Protocol must be one of: tcp, udp, icmp.")
            return None

        port = None
        if protocol in {"tcp", "udp"}:
            try:
                port = int(port_str)
            except (TypeError, ValueError):
                errors.append("Port must be an integer for TCP/UDP tests.")
                return None

        # Evaluate rules in order
        for idx, rule in enumerate(rules):
            if not self._ip_matches_any(src_ip, rule.get("Source", [])):
                continue
            if not self._ip_matches_any(dst_ip, rule.get("Destination", [])):
                continue
            if not self._service_matches(protocol, port, rule.get("Service", [])):
                continue

            # First match wins
            return {
                "matched": True,
                "index": idx,
                "policy_name": rule.get("Policy", f"Rule #{idx + 1}"),
                "action": rule.get("Action", "UNKNOWN"),
                "from_zones": rule.get("From", []),
                "to_zones": rule.get("To", []),
                "services": rule.get("Service", []),
            }

        # No rule matched
        return {
            "matched": False,
            "reason": "No matching rule found for the given traffic parameters.",
        }

    def _ip_matches_any(self, ip_obj, entries):
        """
        Check if an IP address matches any of the provided Source/Destination entries.

        Supported entry formats (examples from your JSON):
        - "IP.10.0.40.119"
        - "Net.10.0.40.0/24"
        - "all"
        - Other names (e.g. "Cisco-Meraki.Cloud") are treated as non-matching
          unless 'all' semantics are involved.
        """
        if not entries:
            return False

        for entry in entries:
            entry = entry.strip()
            if entry.lower() == "all":
                return True

            if entry.lower().startswith("ip."):
                ip_str = entry[3:]
                try:
                    return ip_obj == ip_address(ip_str)
                except ValueError:
                    logger.warning("Invalid IP entry in rule: %s", entry)
                    continue

            if entry.lower().startswith("net."):
                net_str = entry[4:]
                try:
                    network = ip_network(net_str, strict=False)
                    if ip_obj in network:
                        return True
                except ValueError:
                    logger.warning("Invalid network entry in rule: %s", entry)
                    continue

            # Other symbolic names (e.g., "Cisco-Meraki.Cloud") cannot be
            # resolved here. We treat them as non-matching.
        return False

    def _service_matches(self, protocol, port, services):
        """
        Check if a service list matches the given protocol/port.

        Rules:
        - If services list is empty => treat as "any service" (best-effort).
        - If entry is "ALL" => matches everything.
        - "TCP:<port>" or "UDP:<port>" => matches exact port on that protocol.
        - "Port:<start>-<end>" => matches port range for any protocol.
        - Named common services (HTTP, HTTPS, etc.) use SERVICE_PORT_MAP.
        - Unknown service names are ignored for matching.
        """
        # Empty service list: treat as any
        if services is None or len(services) == 0:
            return True

        for svc in services:
            s = svc.strip().upper()
            if s == "ALL":
                return True

            # TCP:x / UDP:x
            if s.startswith("TCP:") or s.startswith("UDP:"):
                if protocol not in {"tcp", "udp"}:
                    continue
                svc_proto = s.split(":", 1)[0].lower()
                try:
                    svc_port = int(s.split(":", 1)[1])
                except (IndexError, ValueError):
                    logger.warning("Invalid TCP/UDP service definition: %s", s)
                    continue
                if svc_proto == protocol and port == svc_port:
                    return True
                continue

            # Port:start-end
            if s.startswith("PORT:"):
                if protocol not in {"tcp", "udp"}:
                    continue
                try:
                    range_part = s.split(":", 1)[1]
                    if "-" in range_part:
                        start_str, end_str = range_part.split("-", 1)
                        start_port = int(start_str)
                        end_port = int(end_str)
                    else:
                        start_port = end_port = int(range_part)
                except (IndexError, ValueError):
                    logger.warning("Invalid Port range definition: %s", s)
                    continue

                if port is not None and start_port <= port <= end_port:
                    return True
                continue

            # Named services (HTTP, HTTPS, etc.)
            if s in self.SERVICE_PORT_MAP:
                svc_proto, svc_port = self.SERVICE_PORT_MAP[s]
                if svc_proto == protocol and port == svc_port:
                    return True
                continue

            # Unknown service name: cannot reliably match, so skip
            logger.debug("Unknown service name encountered during test: %s", s)

        return False

    # -------------------------------------------------------------------------
    # Export helpers
    # -------------------------------------------------------------------------

    def _export_json_response(self, rules):
        """
        Return an HttpResponse to download the current rules as JSON.
        """
        json_str = json.dumps(rules, indent=2)
        response = HttpResponse(json_str, content_type="application/json")
        response["Content-Disposition"] = 'attachment; filename="fortigate_policies.json"'
        return response

    def _export_csv_response(self, rules):
        """
        Return an HttpResponse to download the current rules as CSV.

        For simplicity we export a flat CSV with the most relevant fields.
        List fields are joined by ", " in the output columns.
        """
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)

        # CSV header
        header = [
            "Policy",
            "From",
            "To",
            "Source",
            "Destination",
            "Schedule",
            "Service",
            "Action",
            "IP Pool",
            "NAT",
            "Type",
            "Security Profiles",
            "Log",
            "Bytes",
        ]
        writer.writerow(header)

        for rule in rules:
            row = [
                rule.get("Policy", ""),
                ", ".join(rule.get("From", []) or []),
                ", ".join(rule.get("To", []) or []),
                ", ".join(rule.get("Source", []) or []),
                ", ".join(rule.get("Destination", []) or []),
                ", ".join(rule.get("Schedule", []) or []),
                ", ".join(rule.get("Service", []) or []),
                rule.get("Action", ""),
                ", ".join(rule.get("IP Pool", []) or []),
                rule.get("NAT", ""),
                rule.get("Type", ""),
                ", ".join(rule.get("Security Profiles", []) or []),
                rule.get("Log", ""),
                rule.get("Bytes", ""),
            ]
            writer.writerow(row)

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="fortigate_policies.csv"'
        return response