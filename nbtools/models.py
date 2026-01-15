from django.db import models

class SharePointConfig(models.Model):
    site_url = models.URLField()
    application_id = models.CharField(max_length=255)
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)
    folder_mappings = models.JSONField(default=dict)

    def __str__(self):
        return f"SharePoint Config for {self.site_url}"


class DocumentationBinding(models.Model):
    category = models.CharField(max_length=255)
    server_name = models.CharField(max_length=255, db_index=True)
    application_name = models.CharField(max_length=255, null=True, blank=True)
    file_name = models.CharField(max_length=255)
    version = models.CharField(max_length=50)
    file_type = models.CharField(max_length=50)
    sharepoint_url = models.TextField()

    def __str__(self):
        return f"{self.server_name} - {self.file_name} ({self.version})"
