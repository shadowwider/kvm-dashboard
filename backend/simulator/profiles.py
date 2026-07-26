from .models import EvidenceStatus, ProfileId


FORMAL_TRAP = {
    "notification_oid": "1.3.6.1.4.1.32828.2.1.0.4",
    "level_oid": "1.3.6.1.4.1.32828.2.1.0.2",
    "message_oid": "1.3.6.1.4.1.32828.2.1.0.3",
}

PROFILE_DEFINITIONS = {
    ProfileId.CCDC_LEGACY: {
        "system_oid": "1.3.6.1.4.1.32828.3.257.16",
        "evidence": EvidenceStatus.LEGACY_COMPATIBILITY,
        "description": "Existing dashboard CCDC-shaped regression fixture; not vendor-MIB verified.",
    },
    ProfileId.CCDM_MATRIX: {
        "system_oid": "1.3.6.1.4.1.32828.3.257.10",
        "evidence": EvidenceStatus.VENDOR_BACKED,
        "description": "ControlCenter-Digital matrix fixture.",
    },
    ProfileId.VISIONXS_CPU: {
        "system_oid": "1.3.6.1.4.1.32828.3.768.768",
        "evidence": EvidenceStatus.VENDOR_BACKED,
        "description": "Standalone VisionXS CPU fixture.",
    },
    ProfileId.VISIONXS_CON: {
        "system_oid": "1.3.6.1.4.1.32828.3.769.768",
        "evidence": EvidenceStatus.VENDOR_BACKED,
        "description": "Standalone VisionXS CON fixture.",
    },
    ProfileId.DP12_MUX: {
        "system_oid": "1.3.6.1.4.1.32828.3.1792.17",
        "evidence": EvidenceStatus.VENDOR_BACKED,
        "description": "Read-only DP1.2-MUX-ATC fixture; SNMP SET is intentionally disabled.",
    },
}
