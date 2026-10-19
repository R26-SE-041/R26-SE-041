"""Use existing sketch recognition for concise titles without another model call."""

def sketch_title(metadata):
    if not isinstance(metadata, dict):
        return None
    subject = metadata.get("subject")
    if not isinstance(subject, str) or not subject.strip():
        recognition = metadata.get("recognition")
        subject = recognition.get("subject") if isinstance(recognition, dict) else None
    if not isinstance(subject, str):
        return None
    subject = " ".join(subject.split())[:80]
    return subject[:1].upper() + subject[1:] if subject else None


def display_chat_title(row):
    """Repair legacy placeholder display without rewriting saved conversations."""
    metadata = row.pop("generation_metadata", None)
    if row.get("mode") == "sketch" and row.get("title", "").strip().lower() in {"", "new conversation"}:
        metadata = metadata if isinstance(metadata, dict) else {}
        title = sketch_title(metadata.get("sketchMetadata")) or sketch_title(metadata.get("generationMetadata"))
        if title:
            row["title"] = title
    return row
