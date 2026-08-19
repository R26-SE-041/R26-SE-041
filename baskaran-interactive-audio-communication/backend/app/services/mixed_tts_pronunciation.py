"""Central, editable English-to-Tamil pronunciations used by experimental Mode B.

Priority layer 1 in the Mode B conversion pipeline:

    pronunciation dictionary  →  acronym rules  →  eSpeak G2P  →  IndicXlit  →  original

Add curated entries here whenever a word needs a specific pronunciation that
eSpeak or IndicXlit would get wrong.  Keys are normalised with casefold() before
lookup, so all keys should be lower-cased.
"""

from __future__ import annotations

# Keys are case-insensitive (normalised via casefold() at lookup time).
# Keep curated pronunciations here rather than scattering them through the TTS
# route, so listening-test fixes require only one edit in one file.
PRONUNCIATION_DICTIONARY: dict[str, str] = {
    # ── Acronyms with explicit spacing (also caught by acronym rule, but
    #    dictionary takes priority and guarantees correct spacing) ──────────────
    "ai":       "ஏ ஐ",
    "api":      "ஏ பி ஐ",
    "cpu":      "சி பி யூ",
    "gpu":      "ஜி பி யூ",
    "gpt":      "ஜி பி டி",
    "gpt-4":    "ஜி பி டி 4",
    "url":      "யு ஆர் எல்",
    "pdf":      "பி டி எஃப்",
    "asr":      "ஏ எஸ் ஆர்",
    "tts":      "டி டி எஸ்",
    "rag":      "ஆர் ஏ ஜி",
    "llm":      "எல் எல் எம்",
    "nlp":      "என் எல் பி",
    "ml":       "எம் எல்",
    "dl":       "டி எல்",
    "ai-based": "ஏ ஐ பேஸ்ட்",

    # ── Technical / domain words from test cases ───────────────────────────────
    "artificial":     "ஆர்டிபிஷியல்",      # ஃ removed — IndicF5 hesitates; ப sounds same to listeners
    "intelligence":   "இன்டெலிஜென்ஸ்",
    "machine":        "மெஷின்",
    "learning":       "லேர்னிங்",
    "technology":     "டெக்னாலஜி",
    "data":           "டேட்டா",
    "science":        "சயின்ஸ்",
    "cloud":          "கிளவுட்",
    "internet":       "இன்டர்நெட்",
    "algorithm":      "அல்காரிதம்",
    "algorithms":     "அல்காரிதம்ஸ்",
    "cybersecurity":  "சைபர்செக்யூரிட்டி",
    "virtualization": "வர்ச்சுவலைசேஷன்",
    "kubernetes":     "குபெர்னெட்டீஸ்",
    "postgresql":     "போஸ்ட்கிரெஸ் எஸ்க்யூ எல்",
    "transformer":    "ட்ரான்ஸ்போர்மர்",    # ஃ removed — ட்ரான்ஸ்போர்மர் flows naturally
    "transformers":   "ட்ரான்ஸ்போர்மர்ஸ்",  # same
    "embeddings":     "எம்பெட்டிங்ஸ்",
    "embedding":      "எம்பெட்டிங்",
    "system":         "சிஸ்டம்",
    "systems":        "சிஸ்டம்ஸ்",
    "online":         "ஆன்லைன்",
    "education":      "எட்யுகேஷன்",

    # ── Test-sentence words ────────────────────────────────────────────────────
    "difficult":   "டிபிக்கல்ட்",   # ஃ removed — ப sounds same to listeners, far more common in IndicF5 training
    "topics":      "டாபிக்ஸ்",
    "simple":      "சிம்பிள்",
    "explain":     "எக்ஸ்ப்லேன்",    # ப்ள→ப்ல cluster, shorter = less hesitation
    "experience":  "எக்ஸ்பீரியன்ஸ்",
    "improve":     "இம்ப்ரூவ்",
    "chocolate":   "சாக்லேட்",
    "theobromine": "தியோப்ரோமைன்",
    "tools":       "டூல்ஸ்",
    "students":    "ஸ்டூடன்ட்ஸ்",
    "student":     "ஸ்டூடன்ட்",
    "own":         "ஓன்",
    "pace":        "பேஸ்",
    "learn":       "லேர்ன்",
    "based":       "பேஸ்ட்",
    "topics":      "டாபிக்ஸ்",

    # ── Common English words that appear in Tamil-English code-switching ────────
    "and":         "அண்ட்",
    "or":          "ஆர்",
    "for":         "போர்",          # ஃ at word START = rare in training data → hesitation
    "with":        "வித்",
    "from":        "பிரம்",          # ஃ at word START removed — பிரம் is most natural for IndicF5
    "by":          "பை",
    "at":          "அட்",
    "on":          "ஆன்",
    "in":          "இன்",
    "of":          "அவ்",           # English /əv/ → அவ் (no ஃ, natural IndicF5 output)
    "to":          "டு",
    "the":         "த",
    "is":          "இஸ்",
    "are":         "ஆர்",
    "was":         "வாஸ்",
    "very":        "வெரி",
    "more":        "மோர்",
    "now":         "நாவ்",           # English /naʊ/ → நாவ் (was நவ் — missing the long vowel)
    "today":       "டுடே",
    "using":       "யூஸிங்",
    "used":        "யூஸ்ட்",
    "use":         "யூஸ்",
    # ── Additional common code-switching words ────────────────────────────────
    "useful":      "யூஸ்புல்",
    "important":   "இம்போர்ட்டன்ட்",
    "this":        "திஸ்",
    "that":        "தட்",
    "which":       "விச்",
    "what":        "வாட்",
    "how":         "ஹவ்",
    "also":        "ஆல்சோ",
    "after":       "ஆப்டர்",          # ஃ removed
    "before":      "பிபோர்",          # ஃ removed
    "like":        "லைக்",
    "way":         "வே",
    "new":         "நியூ",
    "good":        "குட்",
    "best":        "பெஸ்ட்",
    "high":        "ஹை",
    "low":         "லோ",
    "need":        "நீட்",
    "many":        "மெனி",
    "different":   "டிபரன்ட்",    # ஃ removed
    "process":     "ப்ராசஸ்",
    "result":      "ரிசல்ட்",
    "model":       "மாடல்",
    "models":      "மாடல்ஸ்",
    "language":    "லாங்குவேஜ்",
    "network":     "நெட்வொர்க்",
    "networks":    "நெட்வொர்க்ஸ்",
    "training":    "ட்ரெயினிங்",
    "testing":     "டெஸ்டிங்",
    "output":      "அவுட்புட்",
    "input":       "இன்புட்",
    "performance": "பெர்போர்மன்ஸ்",  # ஃ removed — போர் is natural Tamil 'for'
}

