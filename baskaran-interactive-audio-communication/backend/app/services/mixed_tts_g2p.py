"""English G2P via eSpeak NG → Tamil phonetic approximation for Mode B.

This module is used exclusively by mixed_tts_phonetics._normalize_latin_token()
as the third priority layer:

    1. pronunciation dictionary      (mixed_tts_pronunciation.py)
    2. acronym rule                  (mixed_tts_phonetics._acronym_pronunciation)
    3. ★ THIS MODULE                 (eSpeak NG G2P → PHONEME_TO_TAMIL mapper)
    4. IndicXlit fallback            (mixed_tts_phonetics._indic_xlit_tamil)
    5. original token                (pass-through)

Design decisions
----------------
* eSpeak NG is called as a subprocess (``espeak-ng -q --ipa=3 -v en-us``).
  No Python pip package is required; the binary must be installed on the host
  (see tamil_parler_tts.py for the Modal apt_install line).
* CPU-only, no GPU required.
* Results are cached with functools.lru_cache so a repeated token within the
  same response never spawns a second subprocess call.
* PHONEME_TO_TAMIL is one central table — all pronunciation tweaks live here.
* The mapper is greedy-longest-match so digraphs like /tʃ/ and /dʒ/ take
  priority over single-phoneme entries.
* If too many IPA characters remain unmapped (> 20% of the IPA length),
  the function returns None to force the IndicXlit fallback — better to
  transliterate than to emit garbage Tamil.

Failure model
-------------
* eSpeak unavailable (binary missing, timeout, etc.) → returns None → caller
  falls back to IndicXlit.
* Phoneme mapping incomplete                          → returns None → same.
* Never raises; all exceptions are swallowed and logged as warnings.
"""

from __future__ import annotations

import re
import subprocess
from functools import lru_cache

from app.core.logging import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# IPA → Tamil phoneme table  (TTS-friendly approximation, not linguistic)
# ─────────────────────────────────────────────────────────────────────────────
# Ordering matters for greedy matching: longer keys must come first so that
# e.g. /tʃ/ matches before /t/ + /ʃ/ separately.
#
# The table covers:
#   • all IPA vowels and diphthongs produced by en-us eSpeak for English
#   • all English consonants and common clusters
#   • stress marks (ˈ ˌ) and syllable boundary (.) are stripped before matching
#
# Tamil TTS note: IndicF5 handles inherent vowels naturally; we output
# explicit vowel markers only where they change the sound.  When a consonant
# is word-final and has no vowel following it, we append ் (pulli / virama)
# to close the syllable correctly.
# ─────────────────────────────────────────────────────────────────────────────

# Diphthongs and affricates — must be matched before their component phonemes.
_DIPHTHONGS_AND_AFFRICATES: list[tuple[str, str]] = [
    # IPA              Tamil approximation
    ("eɪ",             "ஏ"),      # face, cake  → ஏ
    ("aɪ",             "ஐ"),      # price, ride → ஐ
    ("ɔɪ",             "ஓய்"),    # choice      → ஓய்
    ("aʊ",             "அவ்"),    # mouth, cloud → அவ்
    ("oʊ",             "ஓ"),      # goat, own   → ஓ
    ("juː",            "யூ"),     # use, cute   → யூ
    ("ɪə",             "இய"),     # near        → இய
    ("eə",             "ஏய"),     # square      → ஏய
    ("ʊə",             "உவ"),     # cure        → உவ
    ("tʃ",             "ச்"),     # church      → ச்
    ("dʒ",             "ஜ்"),     # judge       → ஜ்
    ("θr",             "த்ர"),    # three       → த்ர
    ("ʃr",             "ஷ்ர"),    # shrimp
    ("str",            "ஸ்ட்ர"), # string
    ("skr",            "ஸ்க்ர"), # screw
    ("spr",            "ஸ்ப்ர"), # spring
    ("spl",            "ஸ்ப்ல்"), # split
]

# Single IPA vowels — ordered long before short where both exist
_VOWELS: list[tuple[str, str]] = [
    ("iː",  "ஈ"),    # fleece
    ("ɑː",  "ஆ"),    # palm
    ("ɔː",  "ஆ"),    # thought
    ("ɜː",  "ஆர்"),  # nurse (long)
    ("uː",  "ஊ"),    # goose
    ("ɪ",   "ி"),    # kit   (short i — combining matra)
    ("e",   "எ"),    # dress
    ("ɛ",   "எ"),    # dress variant
    ("æ",   "அ"),    # trap
    ("ɑ",   "அ"),    # lot
    ("ɒ",   "ஒ"),    # lot (British)
    ("ɔ",   "ஓ"),    # cloth variant
    ("ʌ",   "அ"),    # strut
    ("ə",   ""),     # schwa — silent; let consonant carry inherent vowel
    ("ɜ",   "அர்"), # nurse short
    ("ʊ",   "உ"),    # foot
    ("i",   "ி"),    # happy (combining matra)
    ("u",   "உ"),    # influence
    ("o",   "ஓ"),    # open o
    ("a",   "அ"),    # open a
]

# Single IPA consonants
_CONSONANTS: list[tuple[str, str]] = [
    # Stops
    ("p",  "ப்"),
    ("b",  "ப்"),    # Tamil lacks voiced stops; ப் approximates both
    ("t",  "ட்"),    # alveolar t → retroflex ட் (natural in Tamil loanwords)
    ("d",  "ட்"),
    ("k",  "க்"),
    ("g",  "க்"),
    ("ʔ",  ""),      # glottal stop — skip
    # Fricatives
    ("f",  "ஃப்"),
    ("v",  "வ்"),
    ("θ",  "த்"),    # thin  → த்
    ("ð",  "த்"),    # this  → த்
    ("s",  "ஸ்"),
    ("z",  "ஸ்"),    # Tamil has no /z/ fricative; ஸ் approximates
    ("ʃ",  "ஷ்"),
    ("ʒ",  "ஷ்"),    # measure → ஷ்
    ("h",  "ஹ்"),
    # Nasals
    ("m",  "ம்"),
    ("n",  "ன்"),    # alveolar n → ன்
    ("ŋ",  "ங்"),    # sing  → ங்
    ("ɲ",  "ஞ்"),    # canyon → ஞ்
    # Approximants / liquids
    ("r",  "ர்"),
    ("ɹ",  "ர்"),    # American r
    ("ɾ",  "ர்"),    # flap r
    ("l",  "ல்"),
    ("ɫ",  "ல்"),    # dark l
    ("w",  "வ்"),
    ("j",  "ய்"),
    # Lateral fricative
    ("ɬ",  "ல்"),
]

# Build the ordered lookup list: affricates/diphthongs first, then consonants,
# then vowels — longest-match takes priority.
_ORDERED_PHONEME_MAP: list[tuple[str, str]] = (
    _DIPHTHONGS_AND_AFFRICATES
    + _CONSONANTS
    + _VOWELS
)

# Characters that eSpeak inserts but are not IPA phonemes — strip before matching.
_ESPEAK_NOISE_RE = re.compile(r"[ˈˌ.,()\[\]/ \t\n\r]+")


# ─────────────────────────────────────────────────────────────────────────────
# eSpeak NG subprocess wrapper
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=512)
def espeak_phonemes(word: str) -> str | None:
    """Return the IPA string produced by eSpeak NG for an English word.

    Parameters
    ----------
    word : str
        A single Latin-script word (no spaces, no Tamil characters).

    Returns
    -------
    str | None
        Raw IPA string (may still contain stress marks etc.) or None if
        eSpeak is unavailable or the call fails.
    """
    try:
        result = subprocess.run(
            ["espeak-ng", "-q", "--ipa=3", "-v", "en-us", word],
            capture_output=True,
            text=True,
            timeout=2,
        )
        ipa = result.stdout.strip()
        if ipa:
            return ipa
        # eSpeak sometimes writes to stderr instead
        ipa_err = result.stderr.strip()
        return ipa_err if ipa_err else None
    except FileNotFoundError:
        logger.warning(
            "espeak-ng binary not found; eSpeak G2P layer disabled for Mode B. "
            "Install with: apt-get install espeak-ng"
        )
        return None
    except subprocess.TimeoutExpired:
        logger.warning("espeak-ng timed out for word %r", word)
        return None
    except Exception as exc:
        logger.warning("espeak-ng call failed for %r: %s", word, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# IPA → Tamil mapper
# ─────────────────────────────────────────────────────────────────────────────

def phonemes_to_tamil(ipa: str) -> str | None:
    """Convert an IPA string to a Tamil phonetic approximation.

    Uses greedy longest-match scan over ``_ORDERED_PHONEME_MAP``.
    Returns None if more than 20% of the cleaned IPA characters remain
    unmapped after the scan (triggers the IndicXlit fallback instead of
    emitting garbled Tamil).

    Parameters
    ----------
    ipa : str
        Raw IPA as returned by eSpeak (stress marks and syllable boundaries
        are stripped internally before matching).

    Returns
    -------
    str | None
        Tamil Unicode string or None on failure.
    """
    if not ipa:
        return None

    # Strip noise characters from the IPA string
    clean = _ESPEAK_NOISE_RE.sub("", ipa)
    if not clean:
        return None

    tamil_parts: list[str] = []
    pos = 0
    unmatched = 0

    while pos < len(clean):
        matched = False
        for phoneme, tamil in _ORDERED_PHONEME_MAP:
            if clean.startswith(phoneme, pos):
                tamil_parts.append(tamil)
                pos += len(phoneme)
                matched = True
                break

        if not matched:
            # Unknown IPA character — count as unmatched, advance by one
            unmatched += 1
            pos += 1

    # Safety gate: too many unrecognised characters → give up and use IndicXlit
    if unmatched > max(1, len(clean) * 0.20):
        logger.debug(
            "phonemes_to_tamil: %d/%d chars unmatched in %r — IndicXlit fallback",
            unmatched, len(clean), ipa,
        )
        return None

    result = "".join(tamil_parts).strip()
    return result if result else None


# ─────────────────────────────────────────────────────────────────────────────
# Post-processing: fix virama + vowel binding artefacts
# ─────────────────────────────────────────────────────────────────────────────

# Map standalone Tamil vowel letters → their combining matra equivalents
# so they bind to a preceding consonant correctly after virama removal.
_VOWEL_TO_MATRA: dict[str, str] = {
    "அ": "",     # inherent a — virama removal is enough
    "ஆ": "ா",
    "இ": "ி",
    "ஈ": "ீ",
    "உ": "ு",
    "ஊ": "ூ",
    "எ": "ெ",
    "ஏ": "ே",
    "ஐ": "ை",
    "ஒ": "ொ",
    "ஓ": "ோ",
    "ஔ": "ௌ",
}

_VIRAMA = "்"


def _fix_tamil_syllables(raw: str) -> str:
    """Remove virama before a vowel sign and substitute combining matra.

    The phoneme mapper can emit patterns like:
      ப்ஆ (consonant + virama + standalone vowel) → should become பா
      ப்ா  (consonant + virama + combining matra)  → should become பா

    This pass iterates through the assembled Tamil and fixes both cases so
    IndicF5 receives well-formed Unicode syllables.

    This is a lightweight string-level fix; a full Unicode syllabifier is
    not required for the English loanword phonemes we handle.
    """
    if not raw:
        return raw

    # Tamil combining (matra) vowel signs — these already bind to the preceding
    # consonant; a virama before them must be stripped.
    _COMBINING_MATRAS = frozenset("ாிீுூெேைொோௌ")

    result = list(raw)
    i = 0
    while i < len(result) - 1:
        if result[i] == _VIRAMA:
            nxt = result[i + 1]
            if nxt in _VOWEL_TO_MATRA:
                # Virama followed by standalone vowel letter:
                # remove virama, replace letter with its combining matra
                matra = _VOWEL_TO_MATRA[nxt]
                result[i] = ""
                result[i + 1] = matra
            elif nxt in _COMBINING_MATRAS:
                # Virama followed by combining matra: just strip the virama
                result[i] = ""
        i += 1

    return "".join(result)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=512)
def espeak_to_tamil(word: str) -> str | None:
    """Convert an English word to a Tamil phonetic approximation via eSpeak NG.

    This is the single entry-point called by mixed_tts_phonetics.

    Priority in the full Mode B pipeline::

        1. pronunciation dictionary  → fast exact match
        2. acronym rule              → all-caps letter spelling
        3. ★ this function           → eSpeak G2P + Tamil mapper
        4. IndicXlit                 → transliteration fallback
        5. original token            → last resort

    Parameters
    ----------
    word : str
        A single Latin-script word (no Tamil, no spaces).

    Returns
    -------
    str | None
        Tamil Unicode approximation or None if eSpeak is unavailable,
        phoneme mapping fails, or the mapped result is empty.
    """
    ipa = espeak_phonemes(word)
    if not ipa:
        return None

    raw_tamil = phonemes_to_tamil(ipa)
    if not raw_tamil:
        return None

    fixed = _fix_tamil_syllables(raw_tamil)
    logger.debug("G2P: %r → IPA %r → Tamil %r", word, ipa, fixed)
    return fixed if fixed.strip() else None
