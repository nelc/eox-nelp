"""
Wrapper xmodule.modulestore module.

This contains all the required dependencies from modulestore

Attributes:
    backend:Imported module by using the plugin settings.
    modulestore: Wrapper modulestore class.
    ItemNotFoundError: Wrapper ItemNotFoundError class.
    ModuleStoreEnum: Wrapper ModuleStoreEnum class.
    SignalHandler: Wrapper SignalHandler class.
"""
from importlib import import_module

from django.conf import settings

backend = import_module(settings.EOX_NELP_XMODULE_MODULESTORE)

modulestore = backend.get_modulestore()
ItemNotFoundError = backend.get_exception_ItemNotFoundError()
ModuleStoreEnum = backend.get_module_store_enum()
SignalHandler = backend.get_signal_handler()
