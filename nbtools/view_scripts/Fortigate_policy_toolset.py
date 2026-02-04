"""
fortigate_policy_toolset.py

Updated: Replaced _any_any and _dup_group with flag_any_any and flag_dup_group
to comply with Django template restrictions preventing underscore-prefixed access.
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

    template_name = "nbtools/fortigate_policy_toolset.html"

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

    SCALAR_FIELDS = [
        "Policy",
        "Action",
        "NAT",
        "Type",
        "Log",
        "Bytes",
    ]

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

    # -----------------------------------------------------------
    # GET
    # -----------------------------------------------------------
    def get(self, request):
        return render(
            request,
            self.template_name,
            {"rules": [], "errors": [], "validation": {}, "test_result": None},
        )

    # -----------------------------------------------------------
    # POST
    # -----------------------------------------------------------
    def post(self, request):
        action = request.POST.get("action")
        errors = []

        # ---------------------------
        # UPLOAD JSON
        # ---------------------------
        if action == "upload_file":
            uploaded_file = request.FILES.get("rules_file")
            rules = []
            if not uploaded_file:
                errors.append("No JSON file provided.")
            else:
                try:
                    data = uploaded_file.read().decode("utf-8")
                    rules, parse_errors = self._parse_rules_from_json(data)
                    errors.extend(parse_errors)
                    self._ensure_rule_defaults(rules)
                except Exception as exc:
                    errors.append(f"Failed to process uploaded file: {exc}")

            return render(
                request,
                self.template_name,
                {
                    "rules": rules,
                    "errors": errors,
                    "validation": {},
                    "test_result": None,
                },
            )

        # ---------------------------
        # REBUILD RULES FROM POST
        # ---------------------------
        rules, rebuild_errors = self._rebuild_rules_from_post(request.POST)
        errors.extend(rebuild_errors)
        self._ensure_rule_defaults(rules)

        if not rules and action not in ("export_json", "export_csv"):
            errors.append("No rules loaded. Upload a JSON file first.")
            return render(
                request,
                self.template_name,
                {"rules": [], "errors": errors, "validation": {}, "test_result": None},
            )

        # ---------------------------
        # EXPORT JSON / CSV
        # ---------------------------
        if action == "export_json":
            return self._export_json_response(rules)

        if action == "export_csv":
            return self._export_csv_response(rules)

        # ---------------------------
        # VALIDATE
        # ---------------------------
        validation = {}
        if action == "validate":
            validation = self._validate_rules(rules)
            self._annotate_rules_with_validation(rules, validation)

        # ---------------------------
        # TEST
        # ---------------------------
        test_result = None
        if action == "test":
            validation = self._validate_rules(rules)
            self._annotate_rules_with_validation(rules, validation)
            test_result = self._test_traffic(request.POST, rules, errors)

        # ---------------------------
        # RENDER RESULT
        # ---------------------------
        return render(
            request,
            self.template_name,
            {
                "rules": rules,
                "errors": errors,
                "validation": validation,
                "test_result": test_result,
            },
        )

    # =======================================================================
    # PARSING
    # =======================================================================
    def _parse_rules_from_json(self, raw_json):
        errors = []
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            return [], [f"Invalid JSON: {exc}"]

        if not isinstance(data, list):
            return [], ["JSON root must be a list"]

        rules = []
        for idx, item in enumerate(data, 1):
            if not isinstance(item, dict):
                errors.append(f"Rule #{idx} is not an object.")
                continue

            for key in self.LIST_FIELDS:
                if key in item and not isinstance(item[key], list):
                    item[key] = [item[key]]

            item = self._normalize_keys(item)
            rules.append(item)

        return rules, errors

    # =======================================================================
    # REBUILD RULES FROM POST
    # =======================================================================
    def _rebuild_rules_from_post(self, post):
        errors = []
        result = {}

        for key, val in post.items():
            if not key.startswith("rule-"):
                continue
            try:
                _, idx, field = key.split("-", 2)
                idx = int(idx)
            except ValueError:
                continue

            result.setdefault(idx, {})
            v = val.strip()

            if field in self.LIST_FIELDS:
                result[idx][field] = [x.strip() for x in v.split(",") if x.strip()]
            else:
                result[idx][field] = v

        rules = []
        for i in sorted(result.keys()):
            r = self._normalize_keys(result[i])
            rules.append(r)

        return rules, errors

    # =======================================================================
    # NORMALIZATION
    # =======================================================================
    def _normalize_keys(self, rule):
        if "Security Profiles" in rule:
            vals = rule.pop("Security Profiles")
            if not isinstance(vals, list):
                vals = [vals]

            existing = rule.get("Security_Profiles", [])
            if not isinstance(existing, list):
                existing = [existing]

            rule["Security_Profiles"] = existing + vals

        return rule

    # =======================================================================
    # DEFAULTS
    # =======================================================================
    def _ensure_rule_defaults(self, rules):
        for r in rules:
            for key in self.LIST_FIELDS:
                if key == "Security Profiles":
                    continue
                r.setdefault(key, [])
                if not isinstance(r[key], list):
                    r[key] = [r[key]]

            for key in self.SCALAR_FIELDS:
                r.setdefault(key, "")

            r.setdefault("Security_Profiles", [])

    # =======================================================================
    # VALIDATION
    # =======================================================================
    def _validate_rules(self, rules):
        validation = {"any_any": [], "duplicates": {}}

        # ANY-ANY
        for idx, r in enumerate(rules):
            if self._is_any_list(r["Source"]) and self._is_any_list(r["Destination"]):
                validation["any_any"].append(idx)

        # DUPLICATES
        sigs = {}
        for idx, r in enumerate(rules):
            sig = (
                tuple(sorted(r["Source"])),
                tuple(sorted(r["Destination"])),
                tuple(sorted(r["Service"])),
                r["Action"],
            )
            sigs.setdefault(sig, []).append(idx)

        gid = 1
        for lst in sigs.values():
            if len(lst) > 1:
                for idx in lst:
                    validation["duplicates"][idx] = gid
                gid += 1

        return validation

    def _annotate_rules_with_validation(self, rules, validation):
        for idx, r in enumerate(rules):
            r["flag_any_any"] = idx in validation["any_any"]
            r["flag_dup_group"] = validation["duplicates"].get(idx)

    def _is_any_list(self, lst):
        if not lst:
            return False
        low = [x.lower() for x in lst]
        return "all" in low or any(x.startswith("net.0.0.0.0/0") for x in low)

    # =======================================================================
    # TRAFFIC TEST
    # =======================================================================
    def _test_traffic(self, post, rules, errors):
        src_raw = post.get("test_src_ip", "").strip()
        dst_raw = post.get("test_dst_ip", "").strip()
        proto = post.get("test_protocol", "").strip().lower()
        port_raw = post.get("test_port", "").strip()

        if not src_raw or not dst_raw or not proto:
            errors.append("Test requires source IP, destination IP, protocol.")
            return None

        try:
            src = ip_address(src_raw)
        except:
            errors.append(f"Invalid source IP: {src_raw}")
            return None

        try:
            dst = ip_address(dst_raw)
        except:
            errors.append(f"Invalid destination IP: {dst_raw}")
            return None

        if proto not in ("tcp", "udp", "icmp"):
            errors.append("Protocol must be tcp, udp, or icmp.")
            return None

        port = None
        if proto in ("tcp", "udp"):
            try:
                port = int(port_raw)
            except:
                errors.append("Port must be an integer.")
                return None

        for idx, r in enumerate(rules):
            if not self._ip_matches_any(src, r["Source"]):
                continue
            if not self._ip_matches_any(dst, r["Destination"]):
                continue
            if not self._service_matches(proto, port, r["Service"]):
                continue

            return {
                "matched": True,
                "index": idx,
                "policy_name": r["Policy"],
                "action": r["Action"],
                "from_zones": r["From"],
                "to_zones": r["To"],
                "services": r["Service"],
            }

        return {"matched": False, "reason": "No matching rule found."}

    # =======================================================================
    # MATCH HELPERS
    # =======================================================================
    def _ip_matches_any(self, ip_obj, entries):
        for e in entries:
            e = e.strip()
            if e.lower() == "all":
                return True

            if e.lower().startswith("ip."):
                try:
                    if ip_obj == ip_address(e[3:]):
                        return True
                except:
                    continue

            if e.lower().startswith("net."):
                try:
                    if ip_obj in ip_network(e[4:], strict=False):
                        return True
                except:
                    continue

        return False

    def _service_matches(self, proto, port, services):
        if not services:
            return True

        for s in services:
            up = s.upper()

            if up == "ALL":
                return True

            if up.startswith("TCP:") or up.startswith("UDP:"):
                if proto in ("tcp", "udp"):
                    try:
                        svc_proto, svc_port = up.split(":", 1)
                        if svc_proto.lower() == proto and int(svc_port) == port:
                            return True
                    except:
                        continue

            if up.startswith("PORT:"):
                try:
                    rng = up.split(":", 1)[1]
                    if "-" in rng:
                        a, b = rng.split("-", 1)
                        if int(a) <= port <= int(b):
                            return True
                    else:
                        if int(rng) == port:
                            return True
                except:
                    continue

            if up in self.SERVICE_PORT_MAP:
                expected_proto, expected_port = self.SERVICE_PORT_MAP[up]
                if expected_proto == proto and expected_port == port:
                    return True

        return False

    # =======================================================================
    # EXPORT
    # =======================================================================
    def _export_json_response(self, rules):
        output = []
        for r in rules:
            rr = dict(r)
            rr.pop("flag_any_any", None)
            rr.pop("flag_dup_group", None)

            if "Security_Profiles" in rr:
                rr["Security Profiles"] = rr.pop("Security_Profiles")

            output.append(rr)

        response = HttpResponse(
            json.dumps(output, indent=2), content_type="application/json"
        )
        response["Content-Disposition"] = (
            'attachment; filename="fortigate_policies.json"'
        )
        return response

    def _export_csv_response(self, rules):
        sio = StringIO()
        w = csv.writer(sio)

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
        w.writerow(header)

        for r in rules:
            r.pop("flag_any_any", None)
            r.pop("flag_dup_group", None)

            w.writerow(
                [
                    r["Policy"],
                    ", ".join(r["From"]),
                    ", ".join(r["To"]),
                    ", ".join(r["Source"]),
                    ", ".join(r["Destination"]),
                    ", ".join(r["Schedule"]),
                    ", ".join(r["Service"]),
                    r["Action"],
                    ", ".join(r["IP Pool"]),
                    r["NAT"],
                    r["Type"],
                    ", ".join(r["Security_Profiles"]),
                    r["Log"],
                    r["Bytes"],
                ]
            )

        response = HttpResponse(sio.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="fortigate_policies.csv"'
        )
        return response