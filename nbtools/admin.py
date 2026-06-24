# nbtools/admin.py
from django.contrib import admin
from .models import FortiSiteBinding

@admin.register(FortiSiteBinding)
class FortiSiteBindingAdmin(admin.ModelAdmin):
    list_display = ("site", "credential_alias", "enabled")
