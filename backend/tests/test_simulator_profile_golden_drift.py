"""L2 Profile catalog must fully project to the independent L1 goldens."""

from tools.report_simulator_profile_drift import build_report


def test_l2_profile_catalog_matches_all_l1_object_semantics():
    report = build_report()

    assert report["ok"] is True
    assert report["schema_version"] == 2
    assert report["production_loader_reads_test_goldens"] is False
    assert (
        report["golden_source_policy"]
        == "local curated device dictionary snapshot; original MIB not "
        "reverified in this run"
    )

    expected = {
        "ccdc_legacy": (0, 0),
        "ccdm_matrix": (20, 142),
        "visionxs_cpu": (2, 28),
        "visionxs_con": (2, 27),
        "dp12_mux_atc": (4, 35),
    }
    for profile_id, (tables, leaves) in expected.items():
        profile = report["profiles"][profile_id]
        assert profile["current_table_count"] == tables
        assert profile["current_declared_leaf_count"] == leaves
        assert profile["missing_definition_oids"] == []
        assert profile["unexpected_definition_oids"] == []
        assert profile["duplicate_definition_oids"] == []
        assert profile["semantic_differences"] == []
        assert profile["table_semantics_match"] is True
        assert profile["sys_object_id_matches"] is True
        assert profile["evidence_status_matches"] is True
        assert profile["fixture_validation_errors"] == []
        assert profile["matches_l1_golden"] is True


def test_ccdc_vendor_projection_remains_intentionally_empty():
    report = build_report()["profiles"]["ccdc_legacy"]

    assert report["golden_evidence_status"] == "legacy-unverified"
    assert report["current_table_count"] == 0
    assert report["current_declared_leaf_count"] == 0
