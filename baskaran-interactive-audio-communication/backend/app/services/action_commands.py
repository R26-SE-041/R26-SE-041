"""Bounded action commands; browser playback never needs an LLM call."""
import re


def _normalize(command):
    text = re.sub(r"\s+", " ", command.strip().lower()).rstrip(".!?")
    # Explicit spelling aliases only; never guess an arbitrary language name.
    return re.sub(r"\b(?:singhala|singala|sinhalese)\b", "sinhala", text)


def parse_generation(command):
    text = _normalize(command)
    text = re.sub(r"^(?:please |(?:can|could|would) you )", "", text)
    text = text.replace("one minute", "one-minute").replace("flash cards", "flashcards")
    if text == "create flashcards from this document and save them":
        return {"intent": "flashcards"}
    if text == "create an audio revision of this section only and save it":
        return {"intent": "audio_revision", "scope": "section"}
    if text == "create a one-minute audio revision and save it":
        return {"intent": "audio_revision", "style": "one_minute", "target_duration": 60}
    if text == "create a detailed audio revision and save it":
        return {"intent": "audio_revision", "style": "detailed"}
    match = re.fullmatch(r"create an audio revision in (tamil|sinhala|english) and save it", text)
    if match:
        return {"intent": "audio_revision", "language": match[1]}
    return _natural_generation(text)


def _natural_generation(text):
    """Small, bounded grammar: accepts variations, never guesses arbitrary instructions."""
    text = re.sub(r"\s+please$", "", text)
    text = re.sub(r"^(?:i (?:want|need|would like) |please )", "", text)
    text = re.sub(r"^(?:create|make|generate|prepare|give me)\s+", "", text)
    # Remove only explicitly supported destinations. Other actions (email/share/etc.) remain
    # unmatched rather than silently executing half of a compound request.
    saving = bool(re.search(r"\s+(?:and )?(?:save|store)(?: (?:it|them|this|the revision))?$", text))
    text = re.sub(r"\s+(?:and )?(?:save|store)(?: (?:it|them|this|the revision))?$", "", text)
    languages = re.findall(r"\b(english|tamil|sinhala)\b", text)
    if len(set(languages)) > 1:
        return None
    options = {"language": languages[0]} if languages else {}
    text = re.sub(r"\b(?:in )?(?:english|tamil|sinhala)(?: language)?\b", "", text)
    section = bool(re.search(r"\b(?:(?:of|for|from) )?(?:this|the selected|selected|current) section only\b", text))
    text = re.sub(r"\b(?:(?:of|for|from) )?(?:this|the selected|selected|current) section only\b", "", text)
    text = re.sub(r"\b(?:of|for|from) (?:this|the|my|the selected|selected) (?:document|pdf|lecture|lecture notes|notes)\b", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(?:a|an|some) ", "", text)
    audio = re.fullmatch(r"(?:(short|detailed|one-minute|1-minute) )?audio(?: revision| review| summary| recap)?", text)
    if audio:
        options = {"intent": "audio_revision", **options}
        style = audio[1]
        if style in {"one-minute", "1-minute"}:
            if section:
                return None
            options.update(style="one_minute", target_duration=60)
        elif style == "detailed":
            options["style"] = "detailed"
        if section:
            options["scope"] = "section"
        return options
    if text == "flashcards" and not section:
        return {"intent": "flashcards", **options}
    if not section:
        if text == "summary" or re.fullmatch(r"summari[sz]e(?: (?:this|the|my|selected) (?:document|pdf|notes|lecture))?", text):
            return {"intent": "summarize_and_save" if saving else "summarize", **options}
        if re.fullmatch(r"save (?:the |my |this )?summary", text):
            return {"intent": "save", **options}
    return None


def interpret(command, language="english"):
    """Preview and execution share the same classifier. No model calls or side effects."""
    from app.services.document_actions import classify
    text = _normalize(command)
    options = parse_generation(command) or {}
    intent = classify(command)
    if text == "delete this saved revision":
        intent = "delete"
    if not intent:
        languages = set(re.findall(r"\b(english|tamil|sinhala)\b", text))
        example_language = (next(iter(languages)) if len(languages) == 1 else language).title()
        if len(languages) > 1:
            message = "Choose one output language: English, Tamil or Sinhala."
        elif re.search(r"\baudio\b", text) and re.search(r"\b(review|revision|create|make|generate)\b", text):
            message = f"Please describe one task, for example: Make an audio revision in {example_language}."
        else:
            message = f"What would you like to create? Try: Make {example_language} audio, summarize this document, or create flashcards."
        return {"status": "clarify", "message": message,
                **({"language": next(iter(languages))} if len(languages) == 1 else {})}
    effective_language = options.get("language", language)
    label = effective_language.title()
    names = {"summarize": "Create a summary", "save": "Save the existing summary",
             "summarize_and_save": "Create and save a summary", "flashcards": "Create and save flashcards",
             "audio_revision": "Create and save an audio revision", "delete": "Delete the opened saved result (confirmation required)"}
    description = names[intent]
    if intent != "delete":
        description += " in " + label
    if options.get("style") == "one_minute":
        description += " · about one minute"
    if options.get("style") == "detailed":
        description += " · detailed"
    if options.get("scope") == "section":
        description += " · selected source section only"
    return {"status": "ready", "intent": intent, "language": effective_language,
            "scope": options.get("scope", "document"), "message": description}
