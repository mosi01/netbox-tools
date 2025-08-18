from dcim.models import Device
from virtualization.models import VirtualMachine
from datetime import date, timedelta
from netbox.jobs import Job

class DocumentationReviewJob(Job):
	description = "Audit Devices & VMs for stale or unreviewed documentation."

	def run(self, data, commit):
		cutoff = date.today() - timedelta(days=90)
		pending = []

		for qs, model in ((Device.objects.all(), Device), (VirtualMachine.objects.all(), VirtualMachine)):
			for obj in qs:
				last	= obj.cf["latest_update"]
				status	= obj.cf["reviewed"]
				if not status or last < cutoff:
					pending.append({
						"object_type": 	model._meta.verbose_name.title(),
						"name":		obj.name,
						"last_update":	last,
						"reviewed":	status,
					})

		self.log_success(f"{len(pending)} items need review.")
		return pending


