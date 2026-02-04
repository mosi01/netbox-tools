"""
fortigate_policy_toolset.py

View for the "Fortigate Policy Toolset" in the nbtools plugin.

Features:
- Import Fortinet firewall policy rules from a JSON file.
- Display rules in an editable table (per-request only; no DB storage).
- Validate rules:
  - Highlight "any-to-any" rules.
  - Highlight duplicate rules (same Source, Destination, Service, and Action).
- Test traffic:
  - Given src IP, dst IP, protocol and port, find the first matching rule and its action.
- Export:
  - JSON (close to original format, including "Security Profiles").
  - CSV.

All state is kept in memory for the duration of the request. Nothing is saved
in NetBox's database or plugin models.
"""

import json
import logging
from ipaddress import ip_address, ip_network
from io import StringIO
import csv

from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger("nbtools")


@method_decorator(csrf_exempt, name="dispatch")
class FortigatePolicyToolsetView(View):
    """
    Main view for the Fortigate Policy Toolset.

    - GET:
      Render an empty page with upload form.
    - POST:
      Handle actions:
        * upload_file  -> parse JSON and show editable table
        * validate     -> validate rules and highlight issues
        * test         -> test traffic against rules
        * export_json  -> download current rules as JSON
        * export_csv   -> download current rules as CSV

    Note: Rules are NOT persisted in the database. Each POST rebuilds
    the rules from the submitted form fields.
    """

    template_name = "nbtools/fortigate_policy_toolset.html"

    # Keys that should be treated as list fields. Include both the original FortiGate
    # name ("Security Profiles") and our normalized key ("Security_Profiles").
    LIST_FIELDS = {
        "From",
        "To",
        "Source",
        "Destination",
        "Schedule",
        "Service",
        "IP Pool",
        "Security Profiles",
        "Security_Profiles",
    }

    # These fields are scalars (plain strings) for display/export purposes.
    SCALAR_FIELDS = [
        "Policy",
        "Action",
        "NAT",
        "Type",
        "Log",
        "Bytes",
    ]

    # Service port mapping for common named services (best-effort approximation).
    # This is not an exhaustive FortiGate service mapping.
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

    # -------------------------------------------------------------
    # HTTP handlers
    # -------------------------------------------------------------

    def get(self, request):
        """
        Initial GET request: show empty tool with just the upload form.
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
        Handle all POST actions.

        The "action" field in POST determines what happens:
        - upload_file  : handle JSON upload
        - validate     : validate rules
        - test         : test traffic against rules
        - export_json  : export current rules as JSON
        - export_csv   : export current rules as CSV
        """
        action = request.POST.get("action")
        errors = []
        rules = []

        # ---------------------------------------------
        # 1) Handle file upload
        # ---------------------------------------------
        if action == "upload_file":
            uploaded_file = request.FILES.get("rules_file")
            if not uploaded_file:
                errors.append("No JSON file provided.")
            else:
                try:
                    file_content = uploaded_file.read().decode("utf-8")
                    rules, parse_errors = self._parse_rules_from_json(file_content)
                    errors.extend(parse_errors)
                    self._ensure_rule_defaults(rules)
                except UnicodeDecodeError as exc:
                    logger.exception("Failed to decode uploaded file as UTF-8")
                    errors.append(f"Failed to decode uploaded file as UTF-8: {exc}")
                except Exception as exc:  # Safety net for unexpected errors
                    logger.exception("Unexpected error while processing upload")
                    errors.append(f"Unexpected error while processing upload: {exc}")

            context = {
                "rules": rules,
                "errors": errors,
                "validation": self._build_empty_validation(),
                "test_result": None,
            }
            return render(request, self.template_name, context)

        # ---------------------------------------------
        # 2) Rebuild rules from the form for all other actions
        # ---------------------------------------------
        rules, rebuild_errors = self._rebuild_rules_from_post(request.POST)
        errors.extend(rebuild_errors)
        self._ensure_rule_defaults(rules)

        # If we still have no rules and the action is not an export, bail out.
        if not rules and action not in {"export_json", "export_csv"}:
            errors.append("No rules loaded. Please upload a JSON file first.")
            context = {
                "rules": [],
                "errors": errors,
                "validation": {},
                "test_result": None,
            }
            return render(request, self.template_name, context)

        # ---------------------------------------------
        # 3) Handle export actions early (no need for validation/test)
        # ---------------------------------------------
        if action == "export_json":
            return self._export_json_response(rules)

        if action == "export_csv":
            return self._export_csv_response(rules)

        # ---------------------------------------------
        # 4) Validation
        # ---------------------------------------------
        validation = self._build_empty_validation()
        if action == "validate":
            validation = self._validate_rules(rules)
            # Annotate rules so the template can highlight rows
            self._annotate_rules_with_validation(rules, validation)

        # ---------------------------------------------
        # 5) Test traffic
        # ---------------------------------------------
        test_result = None
        if action == "test":
            # We can validate and annotate as well so the table still shows issues
            validation = self._validate_rules(rules)
            self._annotate_rules_with_validation(rules, validation)
            test_result = self._test_traffic(request.POST, rules, errors)

        # ---------------------------------------------
        # 6) Default re-render with current rules
        # ---------------------------------------------
        context = {
            "rules": rules,
            "errors": errors,
            "validation": validation,
            "test_result": test_result,
        }
        return render(request, self.template_name, context)

    # -------------------------------------------------------------
    # Parsing / reconstruction helpers
    # -------------------------------------------------------------

    def _parse_rules_from_json(self, raw_json: str):
        """
        Parse rules from a JSON string.

        Expected format:
            [
              { "Policy": "...", "From": [...], "To": [...], ... },
              ...
            ]

        Returns:
            (list_of_rules, list_of_errors)
        """
        errors = []
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON: {exc}")
            return [], errors

        if not isinstance(data, list):
            errors.append(
                "JSON root must be a list of policy objects "
                "(e.g. [ { ... }, { ... } ])."
            )
            return [], errors

        rules = []
        for idx, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                errors.append(f"Entry #{idx} is not an object and was skipped.")
                continue

            # Ensure known list fields are lists
            for key in self.LIST_FIELDS:
                if key in item and not isinstance(item[key], list):
                    # Automatic simple fix: wrap scalar in list
                    item[key] = [item[key]]

            # Normalize special keys and enforce internal naming
            item = self._normalize_keys(item)

            # Warn about obviously missing core fields (but still include rule)
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
        Reconstruct rules from the submitted table form.

        Field naming convention:
            rule-<index>-<FieldName>

        Examples:
            rule-0-Policy
            rule-0-Source
            rule-0-Destination
            rule-0-Security_Profiles

        Returns:
            (list_of_rules, list_of_errors)
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
                # Ignore fields that don't match the expected pattern
                continue

            if idx not in rules_by_idx:
                rules_by_idx[idx] = {}

            raw_value = value.strip()

            # List fields are stored as comma-separated strings in the form
            if field_name in self.LIST_FIELDS:
                if not raw_value:
                    rules_by_idx[idx][field_name] = []
                else:
                    rules_by_idx[idx][field_name] = [
                        part.strip()
                        for part in raw_value.split(",")
                        if part.strip()
                    ]
            else:
                rules_by_idx[idx][field_name] = raw_value

        # Build ordered list of rules by index
        rules = []
        for i in sorted(rules_by_idx.keys()):
            rule = rules_by_idx[i]
            # Normalize internal keys (e.g. Security Profiles -> Security_Profiles)
            rule = self._normalize_keys(rule)
            rules.append(rule)

        return rules, errors

    def _normalize_keys(self, rule: dict) -> dict:
        """
        Normalize keys in a single rule dict.

        In particular:
        - Convert "Security Profiles" -> "Security_Profiles".
          If both exist, we merge them into one list.
        """
        if "Security Profiles" in rule:
            sp_value = rule.pop("Security Profiles")
            existing = rule.get("Security_Profiles", [])
            # Ensure both sides are lists
            if not isinstance(sp_value, list):
                sp_value = [sp_value]
            if not isinstance(existing, list):
                existing = [existing]
            rule["Security_Profiles"] = existing + sp_value
        return rule

    def _ensure_rule_defaults(self, rules):
        """
        Ensure each rule has all the fields needed by the template,
        with correct types (lists vs. scalars).

        This prevents template errors when keys are missing.
        """
        for rule in rules:
            # Ensure list fields exist and are lists
            for key in self.LIST_FIELDS:
                if key == "Security Profiles":
                    # We don't use this name internally
                    continue
                if key not in rule:
                    rule[key] = []
                else:
                    if not isinstance(rule[key], list):
                        rule[key] = [rule[key]]

            # Ensure scalar fields exist
            for key in self.SCALAR_FIELDS:
                if key not in rule:
                    rule[key] = ""

    # -------------------------------------------------------------
    # Validation logic
    # -------------------------------------------------------------

    def _build_empty_validation(self):
        """
        Build an empty validation structure.

        - any_any:   list of rule indexes (0-based) that are any-to-any.
        - duplicates: dict mapping rule index -> duplicate group id.
        """
        return {
            "any_any": [],
            "duplicates": {},
        }

    def _validate_rules(self, rules):
        """
        Validate:
        - Any-to-any rules.
        - Duplicate rules (same Source, Destination, Service, Action).

        Returns:
            validation dict as in _build_empty_validation().
        """
        validation = self._build_empty_validation()

        # 1) Any-to-any rules
        for idx, rule in enumerate(rules):
            src = rule.get("Source", [])
            dst = rule.get("Destination", [])
            if self._is_any_list(src) and self._is_any_list(dst):
                validation["any_any"].append(idx)

        # 2) Duplicate rules
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

    def _annotate_rules_with_validation(self, rules, validation):
        """
        Annotate rules with simple boolean/number flags for template use.

        Adds to each rule:
            _any_any:   True/False
            _dup_group: group id or None
        """
        any_any_indices = set(validation.get("any_any", []))
        duplicates_map = validation.get("duplicates", {})

        for idx, rule in enumerate(rules):
            rule["_any_any"] = idx in any_any_indices
            rule["_dup_group"] = duplicates_map.get(idx)

    def _is_any_list(self, values):
        """
        Determine if a list-like field represents "any".

        Heuristics:
        - Contains the literal "all" (case-insensitive).
        - Contains "Net.0.0.0.0/0".
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

    # -------------------------------------------------------------
    # Test traffic logic
    # -------------------------------------------------------------

    def _test_traffic(self, post_data, rules, errors):
        """
        Simulate traffic against the rules.

        Expected POST fields:
            test_src_ip
            test_dst_ip
            test_protocol (tcp/udp/icmp)
            test_port     (integer; required for tcp/udp)

        Returns:
            dict describing the result or None if input was invalid.
        """
        src_ip_str = post_data.get("test_src_ip", "").strip()
        dst_ip_str = post_data.get("test_dst_ip", "").strip()
        protocol = post_data.get("test_protocol", "").strip().lower()
        port_str = post_data.get("test_port", "").strip()

        if not src_ip_str or not dst_ip_str or not protocol:
            errors.append("Test requires source IP, destination IP, and protocol.")
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

        # Evaluate rules in order; first match wins
        for idx, rule in enumerate(rules):
            if not self._ip_matches_any(src_ip, rule.get("Source", [])):
                continue
            if not self._ip_matches_any(dst_ip, rule.get("Destination", [])):
                continue
            if not self._service_matches(protocol, port, rule.get("Service", [])):
                continue

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
        Check if an IP address matches any of the given Source/Destination entries.

        Supported entry formats (based on your sample JSON):
        - "IP.10.0.40.119"       -> exact IP
        - "Net.10.0.40.0/24"     -> subnet
        - "all"                  -> any IP
        - Other symbolic names   -> ignored (non-matching) here
        """
        if not entries:
            return False

        for entry in entries:
            entry = entry.strip()
            if entry.lower() == "all":
                return True

            # Exact IP
            if entry.lower().startswith("ip."):
                ip_str = entry[3:]
                try:
                    if ip_obj == ip_address(ip_str):
                        return True
                except ValueError:
                    logger.warning("Invalid IP entry in rule: %s", entry)
                    continue

            # Network
            if entry.lower().startswith("net."):
                net_str = entry[4:]
                try:
                    network = ip_network(net_str, strict=False)
                    if ip_obj in network:
                        return True
                except ValueError:
                    logger.warning("Invalid network entry in rule: %s", entry)
                    continue

            # Names like "Cisco-Meraki.Cloud" cannot be evaluated here.
        return False

    def _service_matches(self, protocol, port, services):
        """
        Check whether a service list matches the given protocol/port.

        Rules:
        - Empty service list -> treat as "any service".
        - "ALL"              -> matches everything.
        - "TCP:<port>"       -> matches that TCP port.
        - "UDP:<port>"       -> matches that UDP port.
        - "Port:<start>-<end>" -> any protocol, port in range.
        - Named common services (HTTP, HTTPS, etc.) use SERVICE_PORT_MAP.

        Unknown service names are ignored for matching.
        """
        if services is None or len(services) == 0:
            # Treat as any service
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

            # Port:start-end (any protocol, range)
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

            # Named services mapped to (protocol, port)
            if s in self.SERVICE_PORT_MAP:
                svc_proto, svc_port = self.SERVICE_PORT_MAP[s]
                if svc_proto == protocol and port == svc_port:
                    return True
                continue

            # Unknown service name
            logger.debug("Unknown service name encountered during test: %s", s)

        return False

    # -------------------------------------------------------------
    # Export helpers
    # -------------------------------------------------------------

    def _export_json_response(self, rules):
        """
        Build a JSON download response for the current rules.

        We map our internal "Security_Profiles" key back to
        "Security Profiles" so the JSON resembles the original
        FortiGate export format.
        """
        export_rules = []
        for rule in rules:
            # Create a shallow copy so we can adjust keys
            r = dict(rule)

            # Remove internal validation fields if present
            r.pop("_any_any", None)
            r.pop("_dup_group", None)

            # Map Security_Profiles -> Security Profiles
            if "Security_Profiles" in r:
                sp_val = r.pop("Security_Profiles")
                r["Security Profiles"] = sp_val

            export_rules.append(r)

        json_str = json.dumps(export_rules, indent=2)
        response = HttpResponse(json_str, content_type="application/json")
        response["Content-Disposition"] = (
            'attachment; filename="fortigate_policies.json"'
        )
        return response

    def _export_csv_response(self, rules):
        """
        Build a CSV download response for the current rules.

        List fields are joined using ", " in each column.
        """
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
            # Remove internal validation fields if present
            # (safe to ignore if missing)
            rule.pop("_any_any", None)
            rule.pop("_dup_group", None)

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
                ", ".join(rule.get("Security_Profiles", []) or []),
                rule.get("Log", ""),
                rule.get("Bytes", ""),
            ]
            writer.writerow(row)

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="fortigate_policies.csv"'
        )
        return response