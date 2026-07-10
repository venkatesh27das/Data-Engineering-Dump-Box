"""Deterministic file-signature, MIME, and anomaly detection."""

from __future__ import annotations

import mimetypes
from pathlib import PurePosixPath

from source_readiness_agent.models.contracts import FileProfile, Modality, SourceObject

SIGNATURES = {
    b"%PDF": "application/pdf",
    b"PK\x03\x04": "application/zip",
    b"\x89PNG": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF8": "image/gif",
}
EXTENSION_MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "txt": "text/plain",
    "html": "text/html",
    "htm": "text/html",
    "xml": "application/xml",
    "json": "application/json",
}
MODALITIES = {
    "pdf": Modality.DOCUMENT,
    "docx": Modality.DOCUMENT,
    "pptx": Modality.DOCUMENT,
    "png": Modality.IMAGE,
    "jpg": Modality.IMAGE,
    "jpeg": Modality.IMAGE,
    "tif": Modality.IMAGE,
    "tiff": Modality.IMAGE,
    "txt": Modality.TEXT,
    "html": Modality.TEXT,
    "htm": Modality.TEXT,
    "xml": Modality.STRUCTURED,
    "json": Modality.STRUCTURED,
    "mp3": Modality.AUDIO,
    "wav": Modality.AUDIO,
    "mp4": Modality.VIDEO,
}


def detect_mime(name: str, content: bytes | None = None) -> str:
    if content:
        for signature, mime in SIGNATURES.items():
            if content.startswith(signature):
                if mime == "application/zip":
                    ext = PurePosixPath(name).suffix.lower().lstrip(".")
                    return EXTENSION_MIME.get(ext, mime)
                return mime
    ext = PurePosixPath(name).suffix.lower().lstrip(".")
    return EXTENSION_MIME.get(ext, mimetypes.guess_type(name)[0] or "application/octet-stream")


def profile_file(
    source_object: SourceObject,
    supported_extensions: set[str],
    maximum_size: int,
    content: bytes | None = None,
    required_metadata: set[str] | None = None,
) -> FileProfile:
    extension = source_object.extension.lower().lstrip(".")
    detected = detect_mime(source_object.file_name, content)
    reported = source_object.reported_mime_type
    expected = EXTENSION_MIME.get(extension)
    mime_match = (
        not reported or reported == detected or (expected is not None and reported == expected)
    )
    modality = MODALITIES.get(extension, Modality.UNKNOWN)
    supported = extension in supported_extensions and modality not in {
        Modality.AUDIO,
        Modality.VIDEO,
    }
    issues: list[str] = []
    if source_object.file_size_bytes == 0:
        issues.append("ZERO_BYTE")
    if source_object.file_size_bytes > maximum_size:
        issues.append("FILE_TOO_LARGE")
    if not mime_match:
        issues.append("MIME_MISMATCH")
    if not supported:
        issues.append("UNSUPPORTED_FILE_TYPE")
    if any(
        part in {"..", ""}
        for part in PurePosixPath(source_object.path_or_uri.replace("mock://", "")).parts
    ):
        issues.append("INVALID_PATH")
    encrypted = bool(
        content and (b"/Encrypt" in content[:100_000] or b"EncryptedPackage" in content[:100_000])
    )
    corrupt = bool(content is not None and source_object.file_size_bytes > 0 and len(content) == 0)
    if encrypted:
        issues.append("ENCRYPTED_OR_PASSWORD_PROTECTED")
    if corrupt:
        issues.append("CORRUPT_SIGNAL")
    required = required_metadata or set()
    present = sum(1 for key in required if source_object.source_metadata.get(key) not in (None, ""))
    completeness = present / len(required) if required else 1.0
    image_probability = 1.0 if modality == Modality.IMAGE else (0.4 if extension == "pdf" else 0.0)
    scanned_probability = (
        0.95 if modality == Modality.IMAGE else (0.5 if extension == "pdf" else 0.0)
    )
    return FileProfile(
        object_id=source_object.object_id,
        file_name=source_object.file_name,
        file_type=extension or "unknown",
        detected_mime_type=detected,
        reported_mime_type=reported,
        mime_match=mime_match,
        size_bytes=source_object.file_size_bytes,
        zero_byte=source_object.file_size_bytes == 0,
        encrypted_or_password_protected=encrypted,
        corrupt_signal=corrupt,
        modality=modality,
        scanned_probability=scanned_probability,
        page_estimate=None,
        layout_complexity=0.5 if extension in {"pdf", "pptx"} else 0.1,
        table_probability=0.4 if extension in {"pdf", "docx", "pptx"} else 0.1,
        image_probability=image_probability,
        supported=supported,
        issues=issues,
        metadata_completeness=completeness,
    )
