"""
urls.py
=======

API URL configuration for the NetBox Tools (nbtools) plugin.

This defines the REST API routes for the Service and Application
models using NetBox's NetBoxRouter.

The resulting namespace will be:

    plugins-api:nbtools-api

And the view names will be:

    plugins-api:nbtools-api:service-list
    plugins-api:nbtools-api:service-detail
    plugins-api:nbtools-api:application-list
    plugins-api:nbtools-api:application-detail
"""

from netbox.api.routers import NetBoxRouter

from .views import ServiceViewSet, ApplicationViewSet

router = NetBoxRouter()
router.register("services", ServiceViewSet)
router.register("applications", ApplicationViewSet)

urlpatterns = router.urls