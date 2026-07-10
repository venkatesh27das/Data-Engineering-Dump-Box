from source_readiness_agent.models.contracts import (
    ConnectionValidationResult,
    FileProfile,
    Modality,
    SamplePolicy,
    SourceInventoryEstimate,
    SourceObject,
)
from source_readiness_agent.skills.readiness_scoring import DEFAULT_WEIGHTS, score_readiness
from source_readiness_agent.skills.sample_selection import select_sample
from source_readiness_agent.skills.source_profiling import build_source_profile


def make_obj(i, ext, size):
    return SourceObject(
        object_id=str(i),
        source_id="SRC",
        path_or_uri=f"mock://{i}.{ext}",
        file_name=f"{i}.{ext}",
        extension=ext,
        file_size_bytes=size,
    )


def make_profile(i, supported=True):
    return FileProfile(
        object_id=str(i),
        file_name=f"{i}.pdf",
        file_type="pdf",
        detected_mime_type="application/pdf",
        mime_match=True,
        size_bytes=10,
        zero_byte=False,
        modality=Modality.DOCUMENT,
        supported=supported,
    )


def test_hybrid_is_bounded_and_explained():
    objects = [make_obj(1, "pdf", 1), make_obj(2, "pdf", 20), make_obj(3, "exe", 5)]
    selected = select_sample(
        objects,
        SamplePolicy(maximum_files=2, maximum_total_bytes=10, maximum_individual_file_size=10),
    )
    assert len(selected) <= 2
    assert sum(x.source_object.file_size_bytes for x in selected) <= 10
    assert all(x.reasons for x in selected)


def test_blocking_access_overrides_numeric_score():
    profile = build_source_profile(
        "SRC",
        SourceInventoryEstimate(estimated_file_count=1, estimated_total_bytes=10),
        ConnectionValidationResult(accessible=False, allowed=False),
        [make_profile(1)],
    )
    result = score_readiness(profile)
    assert result.readiness_status == "ACCESS_BLOCKED"
    assert "SOURCE_OUTSIDE_ALLOWLIST" in result.blocking_issues


def test_no_supported_files_blocks_and_weights_validate():
    profile = build_source_profile(
        "SRC",
        SourceInventoryEstimate(estimated_file_count=1, estimated_total_bytes=10),
        ConnectionValidationResult(accessible=True, allowed=True),
        [make_profile(1, False)],
    )
    assert score_readiness(profile).readiness_status == "NOT_READY"
    bad = dict(DEFAULT_WEIGHTS)
    bad["sample_run_result"] = 1
    try:
        score_readiness(profile, weights=bad)
    except ValueError as exc:
        assert "total" in str(exc)
    else:
        raise AssertionError("invalid weights accepted")
