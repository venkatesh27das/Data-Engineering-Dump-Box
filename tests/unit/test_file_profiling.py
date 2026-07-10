from source_readiness_agent.models.contracts import SourceObject
from source_readiness_agent.skills.file_type_detection import detect_mime, profile_file


def obj(**changes):
    data = dict(
        object_id="1",
        source_id="SRC",
        path_or_uri="mock://x.pdf",
        file_name="x.pdf",
        extension="pdf",
        reported_mime_type="application/pdf",
        file_size_bytes=10,
        source_metadata={},
    )
    data.update(changes)
    return SourceObject(**data)


def test_signature_detection_and_supported_profile():
    assert detect_mime("x.bin", b"%PDF-1.4") == "application/pdf"
    profile = profile_file(obj(), {"pdf"}, 100, b"%PDF-1.4")
    assert profile.supported and profile.mime_match and not profile.zero_byte


def test_mime_mismatch_zero_byte_oversize_and_unsupported():
    profile = profile_file(
        obj(
            file_name="bad.exe", extension="exe", reported_mime_type="text/plain", file_size_bytes=0
        ),
        {"pdf"},
        100,
        b"MZ",
    )
    assert {"ZERO_BYTE", "MIME_MISMATCH", "UNSUPPORTED_FILE_TYPE"} <= set(profile.issues)
    assert "FILE_TOO_LARGE" in profile_file(obj(file_size_bytes=101), {"pdf"}, 100).issues


def test_encryption_and_metadata_completeness():
    profile = profile_file(
        obj(source_metadata={"owner": "x"}), {"pdf"}, 100, b"%PDF /Encrypt", {"owner", "region"}
    )
    assert profile.encrypted_or_password_protected
    assert profile.metadata_completeness == 0.5
