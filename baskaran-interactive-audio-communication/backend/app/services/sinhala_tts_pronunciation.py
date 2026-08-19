"""Curated English-to-Sinhala phonetic spellings for the isolated VITS test."""

from __future__ import annotations

# Keys are normalized with ``casefold`` by sinhala_mixed_phonetics.  Entries
# are pronunciations, never Sinhala semantic translations.
PRONUNCIATION_DICTIONARY: dict[str, str] = {
    "ai": "ඒ අයි", "ml": "එම් එල්", "api": "ඒ පී අයි",
    "cpu": "සී පී යූ", "gpu": "ජී පී යූ", "pdf": "පී ඩී එෆ්",
    "gpt": "ජී පී ටී", "gpt-4": "ජී පී ටී 4", "url": "යූ ආර් එල්",
    "teacher": "ටීචර්", "student": "ස්ටූඩන්ට්", "students": "ස්ටූඩන්ට්ස්",
    "school": "ස්කූල්", "computer": "කොම්පියුටර්", "internet": "ඉන්ටර්නෙට්",
    "technology": "ටෙක්නොලොජි", "learning": "ලර්නින්", "concept": "කොන්සෙප්ට්",
    "concepts": "කොන්සෙප්ට්ස්", "difficult": "ඩිෆිකල්ට්", "explain": "එක්ස්ප්ලේන්",
    "education": "එඩියුකේෂන්", "models": "මොඩල්ස්", "topics": "ටොපික්ස්",
    "understand": "අන්ඩර්ස්ටෑන්ඩ්", "artificial intelligence": "ආර්ටිෆිෂල් ඉන්ටලිජන්ස්",
    "machine learning": "මැෂින් ලර්නින්", "data science": "ඩේටා සයන්ස්",
    "cloud computing": "ක්ලවුඩ් කොම්පියුටින්", "learning experience": "ලර්නින් එක්ස්පීරියන්ස්",
}
