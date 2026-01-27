from django.shortcuts import render
from django.views import View

from virtualization.models import VirtualMachine

import logging
import re

logger = logging.getLogger(__name__)

class SerialChecker(View):
    template_name = 'nbtools/serial_checker.html'

    def get(self, request):
        # Refresh everything on page load
        return self._render_page(request, index=0, refresh=True, show_list=False)

    def post(self, request):
        # Get index from form
        try:
            index = int(request.POST.get("index", 0))
        except ValueError:
            index = 0

        # Determine which button was pressed
        if "next" in request.POST:
            action = "next"
        elif "show_list" in request.POST:
            action = "show_list"
        else:
            action = "check"

        refresh = action == "check"
        show_list = action == "show_list"

        # Increment index if "next" was pressed
        if action == "next":
            index += 1

        return self._render_page(request, index=index, refresh=refresh, show_list=show_list)

    def _render_page(self, request, index, refresh, show_list):
        pattern = re.compile(r'^[A-Z]{2}\d{2,3}[A-Z]{3,5}(\d{4})$')
        all_numbers = [f"{i:04d}" for i in range(1, 10000)]

        # Refresh data or load from session
        if refresh or "taken_map" not in request.session:
            taken_map = {}
            for vm in VirtualMachine.objects.only("name"):
                match = pattern.match(vm.name)
                if match:
                    serial = match.group(1)
                    taken_map[serial] = vm.name

            taken_ints = sorted(int(s) for s in taken_map.keys())
            lowest_taken = taken_ints[0] if taken_ints else 0
            highest_taken = taken_ints[-1] if taken_ints else 0

            available_numbers = [
                n for n in all_numbers
                if n not in taken_map and int(n) > highest_taken
            ]

            # Save to session
            request.session["taken_map"] = taken_map
            request.session["available_numbers"] = available_numbers
            request.session["lowest_taken"] = lowest_taken
            request.session["highest_taken"] = highest_taken
        else:
            taken_map = request.session.get("taken_map", {})
            available_numbers = request.session.get("available_numbers", [])
            lowest_taken = request.session.get("lowest_taken", 0)
            highest_taken = request.session.get("highest_taken", 0)

        # Wrap index
        if index >= len(available_numbers):
            index = 0

        next_number = available_numbers[0] if available_numbers else "None"
        preview_number = available_numbers[index] if available_numbers else "None"

        # Build list table if requested
        list_table = []
        if show_list:
            start = lowest_taken
            end = min(highest_taken + 1000, 9999)
            for i in range(start, end + 1):
                serial = f"{i:04d}"
                list_table.append({
                    "serial": serial,
                    "name": taken_map.get(serial, "Available")
                })

        context = {
            "next_number": next_number,
            "preview_number": preview_number,
            "index": index,
            "available_count": len(available_numbers),
            "taken_count": len(taken_map),
            "total_count": len(all_numbers),
            "show_list": show_list,
            "list_table": list_table,
            "lowest_taken": f"{lowest_taken:04d}",
            "highest_taken": f"{highest_taken:04d}",
        }

        return render(request, self.template_name, context)