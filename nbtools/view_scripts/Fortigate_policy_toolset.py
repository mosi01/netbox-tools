"""
fortigate_policy_toolset.py

Fortigate Policy Toolset for the nbtools NetBox plugin (NetBox 4.5.0).

Features:
- Import Fortinet firewall policy rules from a JSON file.
- Display rules in an editable table (no DB persistence; all in-memory per request).
- Validate rules ("Validate Rules" button):
  - Highlight "any-to-any" rules.
  - Highlight duplicate rules, using:
      From, To, Source, Destination, Service, Action, NAT
  - Flag rules that include "all" in Source or Destination.
  - Flag rules that include "RFC1918-GRP" in Source or Destination.
- Smart validation ("Smart Validation" button):
  - Same as normal validation, plus a "smart duplicates" table that shows
    per Source entry (IP./Net.) where the same Destinations + Services + Action
    are reachable via multiple rules.
  - Only shows groups where ALL rules share the SAME From and To zones.
- Test traffic:
  - Given src IP, dst IP, protocol, port, shows the first matching rule and action.
- Export:
  - JSON (close to original FortiGate format, with "Security Profiles").
  - CSV (semicolon-delimited).

Note:
- Nothing is stored in NetBox's database; all state is re-derived from the form
  submission on each POST.
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
    """Main view for the Fortigate Policy Toolset."""

    template_name = "nbtools/fortigate_policy_toolset.html"

    # Keys that are list-like in the FortiGate JSON / internal structure
    LIST_FIELDS = {
        "From",
        "To",
        "Source",
        "Destination",
        "Schedule",
        "Service",
        "IP Pool",
        "Security Profiles",   # original FortiGate key
        "Security_Profiles",   # normalized internal key
    }

    # Keys that are simple scalar strings
    SCALAR_FIELDS = [
        "Policy",
        "Action",
        "NAT",
        "Type",
        "Log",
        "Bytes",
    ]

    # Simple named service → (protocol, port) mapping (best-effort)
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

    # ----------------------------------------------------------------------
    # HTTP handlers
    # ----------------------------------------------------------------------

    def get(self, request):
        """Initial GET: show empty tool with upload form only."""
        context = {
            "rules": [],
            "errors": [],
            "validation": self._build_empty_validation(),
            "summary": self._build_empty_summary(),
            "smart_groups": [],
            "test_result": None,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        """
        Handle all POST actions via the "action" field:

        - upload_file    : Parse uploaded JSON, show table.
        - validate       : Run validation (any-any + strict duplicates + all + RFC1918-GRP).
        - smart_validate : Same as validate + build smart duplicates table.
        - test           : Run traffic test.
        - export_json    : Download JSON.
        - export_csv     : Download CSV.
        """
        action = request.POST.get("action")
        errors = []

        # Defaults
        validation = self._build_empty_validation()
        summary = self._build_empty_summary()
        smart_groups = []
        test_result = None

        # ------------------------------------------------------------------
        # Upload JSON file
        # ------------------------------------------------------------------
        if action == "upload_file":
            uploaded_file = request.FILES.get("rules_file")
            rules = []
            if not uploaded_file:
                errors.append("No JSON file provided.")
            else:
                try:
                    raw = uploaded_file.read().decode("utf-8")
                    rules, parse_errors = self._parse_rules_from_json(raw)
                    errors.extend(parse_errors)
                    self._ensure_rule_defaults(rules)
                    # Initialize flags for safe template access
                    self._annotate_rules_with_validation(rules, validation)
                except UnicodeDecodeError as exc:
                    logger.exception("Failed to decode uploaded file as UTF-8.")
                    errors.append(f"Failed to decode uploaded file as UTF-8: {exc}")
                except Exception as exc:
                    logger.exception("Unexpected error while processing upload.")
                    errors.append(f"Unexpected error while processing upload: {exc}")

            context = {
                "rules": rules,
                "errors": errors,
                "validation": validation,
                "summary": summary,
                "smart_groups": smart_groups,
                "test_result": None,
            }
            return render(request, self.template_name, context)

        # ------------------------------------------------------------------
        # All other actions: rebuild rules from form fields
        # ------------------------------------------------------------------
        rules, rebuild_errors = self._rebuild_rules_from_post(request.POST)
        errors.extend(rebuild_errors)
        self._ensure_rule_defaults(rules)

        if not rules and action not in {"export_json", "export_csv"}:
            errors.append("No rules loaded. Please upload a JSON file first.")
            context = {
                "rules": [],
                "errors": errors,
                "validation": validation,
                "summary": summary,
                "smart_groups": smart_groups,
                "test_result": None,
            }
            return render(request, self.template_name, context)

        # ------------------------------------------------------------------
        # Export actions (no HTML rendering)
        # ------------------------------------------------------------------
        if action == "export_json":
            return self._export_json_response(rules)

        if action == "export_csv":
            return self._export_csv_response(rules)

        # ------------------------------------------------------------------
        # Validation / Smart Validation / Test
        # ------------------------------------------------------------------
        if action in {"validate", "smart_validate", "test"}:
            # Run standard validation, annotate rules, and build summary
            validation = self._validate_rules(rules)
            self._annotate_rules_with_validation(rules, validation)
            summary = self._build_summary(validation, rules)

        # Smart validation builds additional per-source groupings
        if action == "smart_validate":
            smart_groups = self._build_smart_groups(rules)

        # Traffic test
        if action == "test":
            test_result = self._test_traffic(request.POST, rules, errors)

        # ------------------------------------------------------------------
        # Final render
        # ------------------------------------------------------------------
        context = {
            "rules": rules,
            "errors": errors,
            "validation": validation,
            "summary": summary,
            "smart_groups": smart_groups,
            "test_result": test_result,
        }
        return render(request, self.template_name, context)

    # ======================================================================
    # JSON parsing & POST reconstruction
    # ======================================================================

    def _parse_rules_from_json(self, raw_json):
        """
        Parse rules from a JSON string.

        Expected format:
            [
              { "Policy": "...", "From": [...], "To": [...], ... },
              ...
            ]

        Returns:
            (rules_list, errors_list)
        """
        errors = []
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            return [], [f"Invalid JSON: {exc}"]

        if not isinstance(data, list):
            return [], ["JSON root must be a list of rule objects."]

        rules = []
        for idx, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                errors.append(f"Entry #{idx} is not an object and was skipped.")
                continue

            # Force list fields to be lists
            for key in self.LIST_FIELDS:
                if key in item and not isinstance(item[key], list):
                    item[key] = [item[key]]

            # Normalize keys (especially Security Profiles)
            item = self._normalize_keys(item)
            rules.append(item)

        return rules, errors

    def _rebuild_rules_from_post(self, post_data):
        """
        Reconstruct rules from submitted form fields.

        Expects fields named:
            rule-<index>-<FieldName>

        Example:
            rule-0-Policy
            rule-0-Source
            rule-0-Destination
            rule-0-Security_Profiles

        Returns:
            (rules_list, errors_list)
        """
        errors = []
        tmp = {}

        for key, value in post_data.items():
            if not key.startswith("rule-"):
                continue
            try:
                _, idx_str, field_name = key.split("-", 2)
                idx = int(idx_str)
            except ValueError:
                continue

            tmp.setdefault(idx, {})
            val = value.strip()

            if field_name in self.LIST_FIELDS:
                if val:
                    tmp[idx][field_name] = [x.strip() for x in val.split(",") if x.strip()]
                else:
                    tmp[idx][field_name] = []
            else:
                tmp[idx][field_name] = val

        rules = []
        for i in sorted(tmp.keys()):
            rule = tmp[i]
            rule = self._normalize_keys(rule)
            rules.append(rule)

        return rules, errors

    def _normalize_keys(self, rule):
        """
        Normalize keys in a rule dict.

        - Convert "Security Profiles" → "Security_Profiles" (internal key).
          If both exist, merge them into one list.
        """
        if "Security Profiles" in rule:
            vals = rule.pop("Security Profiles")
            if not isinstance(vals, list):
                vals = [vals]

            existing = rule.get("Security_Profiles", [])
            if not isinstance(existing, list):
                existing = [existing]

            rule["Security_Profiles"] = existing + vals

        return rule

    def _ensure_rule_defaults(self, rules):
        """
        Ensure each rule has all fields needed by validation and template,
        with the correct types (lists vs scalars).
        """
        for r in rules:
            # List fields
            for key in self.LIST_FIELDS:
                if key == "Security Profiles":  # we use Security_Profiles internally
                    continue
                r.setdefault(key, [])
                if not isinstance(r[key], list):
                    r[key] = [r[key]]

            # Scalar fields
            for key in self.SCALAR_FIELDS:
                r.setdefault(key, "")

            # Ensure normalized list exists
            r.setdefault("Security_Profiles", [])

    # ======================================================================
    # Validation & summary
    # ======================================================================

    def _build_empty_validation(self):
        """Return an empty validation structure."""
        return {
            "any_any": [],       # list of rule indexes
            "duplicates": {},    # rule_idx -> group_id
            "has_all": [],       # rules with 'all' in src/dst
            "has_rfc1918": [],   # rules with 'RFC1918-GRP' in src/dst
        }

    def _build_empty_summary(self):
        """Return an empty summary structure."""
        return {
            "any_any_rules": [],      # list of dicts describing any-to-any rules
            "duplicate_groups": [],   # list of {group_id, rules:[...]}
            "has_all_rules": [],      # list of dicts describing rules with 'all'
            "rfc1918_rules": [],      # list of dicts describing rules with RFC1918-GRP
        }

    def _list_contains_all(self, values):
        """Check if list contains the literal 'all' (case-insensitive)."""
        return any(str(v).strip().lower() == "all" for v in values or [])

    def _list_contains_rfc1918_grp(self, values):
        """Check if list contains 'RFC1918-GRP' (case-sensitive)."""
        return any(str(v).strip() == "RFC1918-GRP" for v in values or [])

    def _validate_rules(self, rules):
        """
        Validate:
        - Any-to-any rules.
        - Duplicate rules based on:
          From, To, Source, Destination, Service, Action, NAT.
        - Rules that include 'all' in Source or Destination.
        - Rules that include 'RFC1918-GRP' in Source or Destination.
        """
        validation = self._build_empty_validation()

        # Any-to-any & 'all' and 'RFC1918-GRP' detection
        for idx, r in enumerate(rules):
            src = r.get("Source", [])
            dst = r.get("Destination", [])

            # any-any
            if self._is_any_list(src) and self._is_any_list(dst):
                validation["any_any"].append(idx)

            # has 'all' in source or destination
            if self._list_contains_all(src) or self._list_contains_all(dst):
                validation["has_all"].append(idx)

            # has RFC1918-GRP in source or destination
            if self._list_contains_rfc1918_grp(src) or self._list_contains_rfc1918_grp(dst):
                validation["has_rfc1918"].append(idx)

        # Strict duplicates (include zones + NAT)
        signatures = {}
        for idx, r in enumerate(rules):
            sig = (
                tuple(sorted(r.get("From", []))),
                tuple(sorted(r.get("To", []))),
                tuple(sorted(r.get("Source", []))),
                tuple(sorted(r.get("Destination", []))),
                tuple(sorted(r.get("Service", []))),
                r.get("Action", ""),
                r.get("NAT", ""),
            )
            signatures.setdefault(sig, []).append(idx)

        group_id = 1
        for idx_list in signatures.values():
            if len(idx_list) > 1:
                for idx in idx_list:
                    validation["duplicates"][idx] = group_id
                group_id += 1

        return validation

    def _annotate_rules_with_validation(self, rules, validation):
        """
        Add highlight flags to rules for use in the template:

        - flag_any_any      : True if rule is any-to-any
        - flag_dup_group    : Group id if rule is part of a duplicate group, else None
        - flag_has_all      : True if rule has 'all' in src/dst
        - flag_has_rfc1918  : True if rule has 'RFC1918-GRP' in src/dst
        """
        any_any_set = set(validation.get("any_any", []))
        dup_map = validation.get("duplicates", {})
        has_all_set = set(validation.get("has_all", []))
        has_rfc1918_set = set(validation.get("has_rfc1918", []))

        for idx, r in enumerate(rules):
            r["flag_any_any"] = idx in any_any_set
            r["flag_dup_group"] = dup_map.get(idx)
            r["flag_has_all"] = idx in has_all_set
            r["flag_has_rfc1918"] = idx in has_rfc1918_set

    def _build_summary(self, validation, rules):
        """
        Build a top-of-page summary for:

        - Any-to-any rules (with basic info).
        - Duplicate groups (group id + rule info).
        - Rules with 'all' in source/destination.
        - Rules with 'RFC1918-GRP' in source/destination.
        """
        summary = self._build_empty_summary()

        # Helper to build a short info dict for summary lists
        def _rule_info(idx):
            r = rules[idx]
            return {
                "index": idx,
                "number": idx + 1,
                "policy": r.get("Policy", f"Rule #{idx+1}"),
                "source": ", ".join(r.get("Source", [])),
                "destination": ", ".join(r.get("Destination", [])),
                "action": r.get("Action", ""),
            }

        # Any-to-any summary
        for idx in validation.get("any_any", []):
            if 0 <= idx < len(rules):
                summary["any_any_rules"].append(_rule_info(idx))

        # Duplicate groups summary
        groups = {}
        for idx, group_id in validation.get("duplicates", {}).items():
            groups.setdefault(group_id, []).append(idx)

        for group_id in sorted(groups.keys()):
            rule_infos = []
            for idx in sorted(groups[group_id]):
                if 0 <= idx < len(rules):
                    rule_infos.append(_rule_info(idx))
            if rule_infos:
                summary["duplicate_groups"].append(
                    {"group_id": group_id, "rules": rule_infos}
                )

        # Rules with 'all'
        for idx in validation.get("has_all", []):
            if 0 <= idx < len(rules):
                summary["has_all_rules"].append(_rule_info(idx))

        # Rules with RFC1918-GRP
        for idx in validation.get("has_rfc1918", []):
            if 0 <= idx < len(rules):
                summary["rfc1918_rules"].append(_rule_info(idx))

        return summary

    def _build_smart_groups(self, rules):
        """
        Build "smart duplicate" groups.

        For each Source entry (individual IP./Net.), we group rules where this
        source can reach the same Destinations + Services + Action via
        more than one rule.

        Group key:
            (source_entry, sorted(Destination), sorted(Service), Action)

        Additional constraint:
        - All rules in the group must share the SAME From and To zones.
          If From or To differ across rules, the group is discarded.

        Returns:
            list of groups:
            [
              {
                "source": "Net.10.0.104.0/24",
                "destinations": [...],
                "services": [...],
                "action": "ACCEPT",
                "rule_numbers": [94, 95],
                "rule_policies": [...],
                "nats": [...],
                "from_zones": [...],
                "to_zones": [...],
              },
              ...
            ]
        """
        groups = {}

        for idx, r in enumerate(rules):
            destinations = tuple(sorted(r.get("Destination", [])))
            services = tuple(sorted(r.get("Service", [])))
            action = r.get("Action", "")

            for src in r.get("Source", []):
                key = (src, destinations, services, action)
                g = groups.setdefault(
                    key,
                    {
                        "source": src,
                        "destinations": list(destinations),
                        "services": list(services),
                        "action": action,
                        "rule_indices": [],
                        "rule_policies": [],
                        "nats": set(),
                        "from_zones": set(),
                        "to_zones": set(),
                    },
                )
                g["rule_indices"].append(idx)
                g["rule_policies"].append(r.get("Policy", f"Rule #{idx+1}"))
                g["nats"].add(r.get("NAT", ""))
                g["from_zones"].update(r.get("From", []))
                g["to_zones"].update(r.get("To", []))

        smart_groups = []
        for g in groups.values():
            # Need more than one rule
            if len(g["rule_indices"]) <= 1:
                continue

            # NEW: require that all rules share the SAME From and To zones
            if len(g["from_zones"]) != 1 or len(g["to_zones"]) != 1:
                # Skip this group; scopes/zones differ
                continue

            # Convert sets to sorted lists and add human-friendly rule numbers
            g["rule_numbers"] = [i + 1 for i in g["rule_indices"]]
            g["nats"] = sorted(n for n in g["nats"] if n)
            g["from_zones"] = sorted(z for z in g["from_zones"] if z)
            g["to_zones"] = sorted(z for z in g["to_zones"] if z)

            smart_groups.append(g)

        # Sort for stable display: by source then by first rule number
        smart_groups.sort(key=lambda x: (x["source"], min(x["rule_numbers"])))
        return smart_groups

    def _is_any_list(self, values):
        """
        Determine if a list-like field represents "any" address.

        Heuristics:
        - Contains "all" (case-insensitive), or
        - Contains "Net.0.0.0.0/0".
        """
        if not values:
            return False
        low = [str(v).lower() for v in values]
        if "all" in low:
            return True
        return any(v.startswith("net.0.0.0.0/0") for v in low)

    # ======================================================================
    # Traffic test
    # ======================================================================

    def _test_traffic(self, post_data, rules, errors):
        """
        Simulate traffic against the rules.

        POST fields:
            test_src_ip
            test_dst_ip
            test_protocol (tcp/udp/icmp)
            test_port (int for tcp/udp)
        """
        src_raw = post_data.get("test_src_ip", "").strip()
        dst_raw = post_data.get("test_dst_ip", "").strip()
        proto = post_data.get("test_protocol", "").strip().lower()
        port_raw = post_data.get("test_port", "").strip()

        if not src_raw or not dst_raw or not proto:
            errors.append("Test requires source IP, destination IP, and protocol.")
            return None

        try:
            src_ip = ip_address(src_raw)
        except ValueError:
            errors.append(f"Invalid source IP address: {src_raw}")
            return None

        try:
            dst_ip = ip_address(dst_raw)
        except ValueError:
            errors.append(f"Invalid destination IP address: {dst_raw}")
            return None

        if proto not in {"tcp", "udp", "icmp"}:
            errors.append("Protocol must be one of: tcp, udp, icmp.")
            return None

        port = None
        if proto in {"tcp", "udp"}:
            try:
                port = int(port_raw)
            except (TypeError, ValueError):
                errors.append("Port must be an integer for TCP/UDP tests.")
                return None

        # First-match-wins semantics
        for idx, r in enumerate(rules):
            if not self._ip_matches_any(src_ip, r.get("Source", [])):
                continue
            if not self._ip_matches_any(dst_ip, r.get("Destination", [])):
                continue
            if not self._service_matches(proto, port, r.get("Service", [])):
                continue

            return {
                "matched": True,
                "index": idx,
                "policy_name": r.get("Policy", f"Rule #{idx+1}"),
                "action": r.get("Action", "UNKNOWN"),
                "from_zones": r.get("From", []),
                "to_zones": r.get("To", []),
                "services": r.get("Service", []),
            }

        return {
            "matched": False,
            "reason": "No matching rule found for the given traffic parameters.",
        }

    def _ip_matches_any(self, ip_obj, entries):
        """
        Check if IP matches any of the given Source/Destination entries.

        Supported examples:
        - "IP.10.0.40.119"        -> exact match
        - "Net.10.0.40.0/24"      -> subnet match
        - "all"                   -> any
        - Other names ("Cisco-Meraki.Cloud") are ignored for matching.
        """
        if not entries:
            return False

        for entry in entries:
            e = str(entry).strip()
            if e.lower() == "all":
                return True

            if e.lower().startswith("ip."):
                try:
                    if ip_obj == ip_address(e[3:]):
                        return True
                except ValueError:
                    continue

            if e.lower().startswith("net."):
                try:
                    net = ip_network(e[4:], strict=False)
                    if ip_obj in net:
                        return True
                except ValueError:
                    continue

        return False

    def _service_matches(self, proto, port, services):
        """
        Check if services list matches given protocol + port.

        Behavior:
        - Empty list -> any service.
        - "ALL"      -> any service.
        - "TCP:x" / "UDP:x" -> specific port.
        - "Port:a-b"        -> range (any proto).
        - Named services (HTTP, HTTPS, ...) via SERVICE_PORT_MAP.
        """
        if not services:
            return True

        for s in services:
            up = str(s).strip().upper()

            if up == "ALL":
                return True

            # TCP:NNN / UDP:NNN
            if up.startswith("TCP:") or up.startswith("UDP:"):
                if proto not in {"tcp", "udp"}:
                    continue
                try:
                    svc_proto, svc_port_str = up.split(":", 1)
                    svc_proto = svc_proto.lower()
                    svc_port = int(svc_port_str)
                except (ValueError, IndexError):
                    continue
                if svc_proto == proto and port == svc_port:
                    return True
                continue

            # Port:range
            if up.startswith("PORT:"):
                if proto not in {"tcp", "udp"}:
                    continue
                try:
                    range_part = up.split(":", 1)[1]
                    if "-" in range_part:
                        a, b = range_part.split("-", 1)
                        a = int(a)
                        b = int(b)
                        if port is not None and a <= port <= b:
                            return True
                    else:
                        if port is not None and int(range_part) == port:
                            return True
                except (ValueError, IndexError):
                    continue
                continue

            # Named services
            if up in self.SERVICE_PORT_MAP:
                svc_proto, svc_port = self.SERVICE_PORT_MAP[up]
                if svc_proto == proto and port == svc_port:
                    return True

        return False

    # ======================================================================
    # Export helpers
    # ======================================================================

    def _export_json_response(self, rules):
        """
        Return HttpResponse for JSON export.

        - Remove internal flags.
        - Map Security_Profiles back to "Security Profiles" for FortiGate-like JSON.
        """
        export_rules = []
        for r in rules:
            rr = dict(r)
            rr.pop("flag_any_any", None)
            rr.pop("flag_dup_group", None)
            rr.pop("flag_has_all", None)
            rr.pop("flag_has_rfc1918", None)

            if "Security_Profiles" in rr:
                rr["Security Profiles"] = rr.pop("Security_Profiles")

            export_rules.append(rr)

        body = json.dumps(export_rules, indent=2)
        resp = HttpResponse(body, content_type="application/json")
        resp["Content-Disposition"] = 'attachment; filename="fortigate_policies.json"'
        return resp

    def _export_csv_response(self, rules):
        """
        Return HttpResponse for CSV export.

        List fields are joined with ", " in each cell.
        CSV is semicolon-delimited.
        """
        sio = StringIO()
        writer = csv.writer(sio, delimiter=';')

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

        for r in rules:
            # Drop internal flags if present
            r.pop("flag_any_any", None)
            r.pop("flag_dup_group", None)
            r.pop("flag_has_all", None)
            r.pop("flag_has_rfc1918", None)

            writer.writerow(
                [
                    r.get("Policy", ""),
                    ", ".join(r.get("From", [])),
                    ", ".join(r.get("To", [])),
                    ", ".join(r.get("Source", [])),
                    ", ".join(r.get("Destination", [])),
                    ", ".join(r.get("Schedule", [])),
                    ", ".join(r.get("Service", [])),
                    r.get("Action", ""),
                    ", ".join(r.get("IP Pool", [])),
                    r.get("NAT", ""),
                    r.get("Type", ""),
                    ", ".join(r.get("Security_Profiles", [])),
                    r.get("Log", ""),
                    r.get("Bytes", ""),
                ]
            )

        resp = HttpResponse(sio.getvalue(), content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="fortigate_policies.csv"'
        return resp