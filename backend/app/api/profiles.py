from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.deps import get_current_user
from app.models.user import User
from app.snmp.profile_runtime import profile_metadata
from kvm_profiles import PROFILE_CATALOG


router = APIRouter()


class ProfileMetadataOut(BaseModel):
    id: str
    version: str
    evidence_version: str
    product: str
    role: str
    system_oid: str
    label_key: str
    section_keys: list[str]


class ProfileListOut(BaseModel):
    items: list[ProfileMetadataOut]


@router.get("", response_model=ProfileListOut)
async def list_profiles(
    _: User = Depends(get_current_user),
) -> ProfileListOut:
    return ProfileListOut(
        items=[
            ProfileMetadataOut.model_validate(profile_metadata(profile))
            for profile in sorted(
                PROFILE_CATALOG.values(),
                key=lambda item: item.profile_id,
            )
        ]
    )


__all__ = ["router"]
