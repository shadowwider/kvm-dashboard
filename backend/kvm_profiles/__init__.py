"""Shared immutable KVM Profile schema and simulator fixture catalog."""

from .profile_catalog import (
    CATALOG_SHA256,
    PROFILE_CATALOG,
    get_profile,
    normalize_catalog_profile_id,
    profile_schema_metadata,
)
from .profile_fixture import DEFAULT_FIXTURES

__all__ = [
    "CATALOG_SHA256",
    "DEFAULT_FIXTURES",
    "PROFILE_CATALOG",
    "get_profile",
    "normalize_catalog_profile_id",
    "profile_schema_metadata",
]
