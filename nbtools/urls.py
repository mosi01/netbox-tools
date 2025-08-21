from django.urls import path
from . import views

app_name = "nbtools"

urlpatterns = [
	path("", views.dashboard, name="dashboard"),
	path("documentation-reviewer/", views.documentation_reviewer, name="documentation_reviewer"),
	path("serial-checker/", views.SerialChecker.as_view(), name="serial_checker"),
	path("prefix-validator", views.prefix_validator_view, name="prefix_validator"),
]
