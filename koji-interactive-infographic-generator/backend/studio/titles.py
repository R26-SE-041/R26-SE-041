"""Name saved creations from existing metadata without another model call."""
import re


def prompt_title(prompt):
    if not isinstance(prompt, str):
        return None
    text = " ".join(prompt.split())
    text = re.sub(r"^(?:please\s+)?(?:generate|create|draw|make|show(?:\s+me)?)\s+(?:(?:an?|the)\s+)?(?:(?:image|picture|illustration|diagram)\s+of\s+)?", "", text, flags=re.I)
    if len(text) > 64:
        text = text[:65].rsplit(" ", 1)[0] if " " in text[:65] else text[:64]
    text = text.strip(" ,.;:-")
    return text[:1].upper() + text[1:] if text else None

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
    metadata = metadata if isinstance(metadata, dict) else {}
    saved_title = (row.get("title") or "").strip()
    original_prompt = metadata.get("prompt") or ""
    automatic_title = isinstance(original_prompt, str) and original_prompt.strip() and saved_title == original_prompt.strip()[:80]
    if saved_title.lower() in {"", "new conversation"} or automatic_title:
        title = generation_title({**metadata, "mode": row.get("mode")})
        if title:
            row["title"] = title
    return row


def generation_title(metadata):
    if metadata.get("mode") == "sketch":
        title = sketch_title(metadata.get("sketchMetadata")) or sketch_title(metadata.get("generationMetadata"))
    else:
        title = sketch_title(metadata.get("generationMetadata"))
        anatomy = metadata.get("anatomy")
        if not title and metadata.get("mode") == "anatomy" and isinstance(anatomy, dict):
            organ = anatomy.get("organ")
            title = prompt_title(organ.replace("_", " ")) if isinstance(organ, str) else None
    return title or prompt_title(metadata.get("prompt")) or prompt_title(metadata.get("enhancedPrompt"))
