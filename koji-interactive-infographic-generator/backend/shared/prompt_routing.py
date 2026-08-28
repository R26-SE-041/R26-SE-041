"""Lightweight routing for anatomy-specific versus generic prompt enhancement."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal


PromptRoute = Literal["anatomy", "generic"]


@dataclass(frozen=True)
class RouteDecision:
    route: PromptRoute
    confidence: float
    reason_code: str
    source: Literal["rules", "qwen"]
    subject: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ANATOMY_INTENT = re.compile(
    r"\b(?:human anatomy|anatomical|organ anatomy|medical illustration|"
    r"histology|dissection|sagittal|coronal|axial|transverse|anterior|posterior|"
    r"dorsal|ventral|medial|superior|inferior)\b",
    re.I,
)
_HUMAN_ORGAN = re.compile(
    r"\b(?:adrenal glands?|appendix|bladder|bone marrow|brain|bronchi|colon|"
    r"diaphragm|duodenum|ears?|esophagus|eyes?|fallopian tubes?|gallbladder|"
    r"heart|hypothalamus|intestines?|kidneys?|larynx|liver|lungs?|lymph nodes?|"
    r"ovaries?|pancreas|parathyroid|penis|pituitary gland|placenta|prostate|"
    r"rectum|salivary glands?|skin|small bowel|spinal cord|spleen|stomach|"
    r"testes?|thymus|thyroid|tongue|tonsils?|trachea|ureters?|urethra|uterus|vagina|"
    r"vulva|cervix|endometrium|breasts?|mammary glands?)\b",
    re.I,
)
_ANATOMICAL_STRUCTURE = re.compile(
    r"\b(?:"
    r"aorta|arter(?:y|ies)|veins?|capillar(?:y|ies)|blood vessels?|"
    r"atri(?:um|a)|ventricles?|mitral valve|tricuspid valve|heart valves?|"
    r"cerebellum|cerebrum|cortex|brainstem|medulla|hippocampus|amygdala|neurons?|"
    r"cornea|retina|iris|pupil|lens|optic nerve|sclera|macula|eyelids?|eyebrows?|"
    r"renal artery|nephrons?|alveoli|bronchioles?|hepatic vein|pancreatic duct|"
    r"bones?|skeleton|skull|mandible|spine|vertebrae?|ribs?|rib cage|pelvis|"
    r"femur|tibia|fibula|patella|humerus|radius|ulna|scapula|clavicle|"
    r"muscles?|tendons?|ligaments?|joints?|cartilage|nerves?|"
    r"head|face|scalp|hair|neck|shoulders?|arms?|forearms?|elbows?|wrists?|hands?|palms?|fingers?|thumbs?|"
    r"chest|torso|abdomen|back|waist|hips?|buttocks?|groin|legs?|thighs?|calves?|knees?|ankles?|heels?|feet|foot|toes?|"
    r"nose|nostrils?|mouth|lips?|teeth|tooth|gums?|jaw|cheeks?|chin|"
    r"nasal cavity|sinuses?|pharynx|epiglottis|vocal cords?|"
    r"tissues?|organs?|body parts?|human body|"
    r"blood cells?|red blood cells?|white blood cells?|platelets?"
    r")\b",
    re.I,
)
_METAPHORICAL_ORGAN = re.compile(
    r"\b(?:heart[- ]shaped|heart icon|heart symbol|brain teaser|butterfly stomach|"
    r"hand[- ]drawn|hands? of (?:a )?clock|head of (?:a )?flower|foot of (?:a )?mountain)\b",
    re.I,
)
_OBVIOUS_GENERIC = re.compile(
    r"\b(?:cat|dog|horse|cow|pig|sheep|goat|rabbit|mouse|rat|monkey|ape|lion|"
    r"tiger|elephant|deer|bear|frog|snake|lizard|insect|butterfly|flower|rose|"
    r"tree|plant|forest|mountain|landscape|car|engine|robot|building|house|food|"
    r"logo|spaceship|ocean|sunset|bird|fish)\b",
    re.I,
)


def deterministic_route(prompt: str) -> RouteDecision | None:
    """Resolve high-confidence requests and defer ambiguous language to Qwen."""
    clean = re.sub(r"\s+", " ", prompt).strip()
    if not clean:
        return None
    if _METAPHORICAL_ORGAN.search(clean):
        return RouteDecision("generic", 0.99, "metaphorical_organ_term", "rules")
    organ = _HUMAN_ORGAN.search(clean)
    if organ and (_ANATOMY_INTENT.search(clean) or not _OBVIOUS_GENERIC.search(clean)):
        return RouteDecision("anatomy", 0.98, "human_organ_request", "rules", organ.group(0))
    structure = _ANATOMICAL_STRUCTURE.search(clean)
    if structure and not _OBVIOUS_GENERIC.search(clean):
        return RouteDecision("anatomy", 0.98, "human_structure_request", "rules", structure.group(0))
    if _ANATOMY_INTENT.search(clean) and re.search(r"\b(?:human|body|organ|tissue)\b", clean, re.I):
        return RouteDecision("anatomy", 0.97, "explicit_anatomy_request", "rules")
    if _OBVIOUS_GENERIC.search(clean):
        return RouteDecision("generic", 0.97, "general_visual_request", "rules")
    return None


def route_from_model(payload: dict[str, Any] | None) -> RouteDecision | None:
    """Validate the small routing contract returned by Qwen."""
    if not isinstance(payload, dict) or payload.get("route") not in {"anatomy", "generic"}:
        return None
    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None
    if not 0.0 <= confidence <= 1.0:
        return None
    reason = str(payload.get("reason_code") or "model_classification")[:80]
    subject = re.sub(r"\s+", " ", str(payload.get("subject") or "")).strip()[:80]
    return RouteDecision(payload["route"], confidence, reason, "qwen", subject)
