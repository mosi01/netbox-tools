"""
nbtools.api
===========

API package for the NetBox Tools (nbtools) plugin.

This package is required so that NetBox can import serializers for
plugin models using the path:

    nbtools.api.serializers.<ModelName>Serializer

The actual serializer classes are defined in serializers.py.
"""