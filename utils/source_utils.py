from pathlib import Path
from uuid import UUID


def _looks_internal_id(value: str) -> bool:
    compact = value.replace("-", "")
    if len(compact) >= 16 and all(char in "0123456789abcdefABCDEF" for char in compact):
        return True

    try:
        UUID(value)
        return True
    except ValueError:
        return False


def deduplicate_document_sources(chunks: list[dict]) -> list[str]:
    """Return unique user-facing filenames from retrieved chunks."""
    sources = []
    seen = set()

    for chunk in chunks:
        metadata = chunk.get("metadata", {}) or {}
        raw_name = (
            metadata.get("filename")
            or metadata.get("source")
            or metadata.get("doc_name")
            or metadata.get("document_name")
            or metadata.get("doc_id")
        )
        if not raw_name:
            continue

        name = Path(str(raw_name).replace("\\", "/")).name.strip()
        if not name or _looks_internal_id(name):
            continue

        key = name.casefold()
        if key in seen:
            continue

        seen.add(key)
        sources.append(name)

    return sources
