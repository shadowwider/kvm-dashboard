"""Compatibility export for the shared production Profile catalog."""

from importlib import reload

import kvm_profiles.profile_catalog as _shared

if globals().get("_SIMULATOR_PROFILE_CATALOG_LOADED"):
    reload(_shared)
_SIMULATOR_PROFILE_CATALOG_LOADED = True

from kvm_profiles.profile_catalog import *  # noqa: E402,F401,F403
from kvm_profiles.profile_catalog import __all__  # noqa: E402
