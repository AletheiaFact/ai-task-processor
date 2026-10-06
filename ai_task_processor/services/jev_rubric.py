"""Jev questions for triage: impact area, and the severity rubric.

Jev answers three questions about the VR text only (harm, contestable, checkable).
Everything after that is fixed, auditable code:

1. priority matrix: no checkable claim -> Low; otherwise harm x contestable
2. reach matrix: adjusts the band from the personalities' Wikidata data
3. the band is limited to Low..Critical
4. the sub-band (_1, _2, _3) comes from where Jev's expected harm score falls
   within its most likely level

Any change to the questions, the matrices or the thresholds must bump RUBRIC_VERSION.
"""
from typing import Any, Dict, List, Optional

RUBRIC_VERSION = 1

# Long texts are truncated before going to Jev
MAX_TEXT_CHARS = 6000

LOW, MEDIUM, HIGH, CRITICAL = 0, 1, 2, 3
LEVEL_NAMES = ["Low", "Medium", "High", "Critical"]

HARM_INSTRUCTIONS = (
    "You are a triage analyst at a Brazilian fact-checking agency. Assess only the HARM: "
    "if what this content claims were false, or if a false version of it spread, what "
    "would the real-world harm be? Consider physical risk (public health, vulnerable "
    "populations, evacuation, panic), scale (environmental disaster, multi-million fraud, "
    "institutional crisis) and reach. Do not take into account the source or whether the "
    "information seems true: that is assessed in another question."
)

HARM_LEVELS = [
    "Low: little or no harm (entertainment, recipe, public service, local administrative routine)",
    "Medium: harm limited to a group or place, reversible (bill, municipal fee, local political dispute)",
    "High: widespread or hard-to-reverse harm (multi-million fraud, environmental disaster, institutional crisis, reputation of public figures)",
    "Critical: risk to the life or health of many people, or to the electoral process (health alert, evacuation, ongoing disaster, panic)",
]

CONTESTABLE_INSTRUCTIONS = (
    "The content makes at least one contestable claim: without a clear source, attributed "
    "only to social media or rumors, with doubtful data or quotes, or contradicting what is "
    "known. Factual news attributed to an official body or an identified source, with "
    "nothing doubtful, is NOT contestable."
)

CHECKABLE_INSTRUCTIONS = (
    "The content contains at least one specific factual claim that can be checked as true "
    "or false (a figure, number, statement attributed to someone or event), not just "
    "opinion, recipe, public service or entertainment."
)

# Probability at or above which a boolean answer counts as "yes"
BOOLEAN_THRESHOLD = 0.5

# Final band by harm band, fixed before seeing results.
# Harm Critical: Critical if contestable, otherwise High. Harm High: High if contestable,
# otherwise Medium. Harm Medium: Medium if contestable, otherwise Low. Harm Low: Low.
PRIORITY_MATRIX = {
    "contestable": [LOW, MEDIUM, HIGH, CRITICAL],
    "not_contestable": [LOW, LOW, MEDIUM, HIGH],
}

# Reach matrix: (minimum followers, band adjustment), checked from the highest minimum
# down; the first match wins, e.g. [(1_000_000, +1), (10_000, 0), (0, -1)].
# TODO: thresholds to be defined with the fact-checkers. Empty = neutral (no adjustment).
REACH_THRESHOLDS: List[tuple] = []

# Sub-band by the offset of the expected harm score from its most likely level:
# below -SUB_BAND_EDGE -> _1, above +SUB_BAND_EDGE -> _3, otherwise _2
SUB_BAND_EDGE = 1 / 6
SEVERITY_PREFIX = {LOW: "low", MEDIUM: "medium", HIGH: "high"}


IMPACT_AREA_INSTRUCTIONS = (
    "You are a triage analyst at a Brazilian fact-checking agency. Choose the MAIN impact "
    "area of this content: the area of society that would be most affected if what it "
    "claims were false. Choose \"Outros\" only if none of the other areas applies."
)


def text_state(text: str) -> Dict[str, str]:
    """What Jev sees: the VR text only."""
    return {"verification_request": (text or "")[:MAX_TEXT_CHARS]}


def impact_area_questions(options: List[str]) -> Dict[str, Dict[str, Any]]:
    """One choice question over the closed list of impact areas sent by the backend."""
    return {
        "impact_area": {
            "type": "choice",
            "instructions": IMPACT_AREA_INSTRUCTIONS,
            "criteria": {option: None for option in options},
        }
    }


def severity_questions() -> Dict[str, Dict[str, Any]]:
    """The three questions Jev answers about the VR text."""
    return {
        "harm": {"type": "score", "instructions": HARM_INSTRUCTIONS, "criteria": HARM_LEVELS},
        "contestable": {"type": "boolean", "instructions": CONTESTABLE_INSTRUCTIONS},
        "checkable": {"type": "boolean", "instructions": CHECKABLE_INSTRUCTIONS},
    }


def reach_adjustment(personalities: List[Dict[str, Any]], thresholds: Optional[List[tuple]] = None) -> int:
    """Band adjustment from the reach of the personalities.

    Uses the personality with the most followers. A personality without Wikidata data
    (source "user_provided") or with 0 followers counts as unknown reach, never as low
    reach: Wikidata stores 0 when the followers property (P8687) is missing.

    TODO (F.1): identifying_data lists every person mentioned in the text, not the author
    of the claim. Identifying the author would make this adjustment measure the reach of
    whoever spreads the claim.
    """
    thresholds = REACH_THRESHOLDS if thresholds is None else thresholds
    if not thresholds:
        return 0

    known = [
        p.get("followers") or 0
        for p in personalities or []
        if p.get("source") != "user_provided"
    ]
    followers = max((f for f in known if f > 0), default=None)
    if followers is None:
        return 0

    for minimum, adjustment in sorted(thresholds, key=lambda t: t[0], reverse=True):
        if followers >= minimum:
            return adjustment
    return 0


def sub_band(harm_probabilities: List[float]) -> int:
    """Sub-band 1, 2 or 3 from where the expected harm falls within its most likely level."""
    total = sum(harm_probabilities) or 1.0
    expected = sum(i * p for i, p in enumerate(harm_probabilities)) / total
    most_likely = harm_probabilities.index(max(harm_probabilities))
    offset = expected - most_likely
    if offset < -SUB_BAND_EDGE:
        return 1
    if offset > SUB_BAND_EDGE:
        return 3
    return 2


def to_severity(band: int, sub: int) -> str:
    """SeverityEnum value. Critical has no sub-bands."""
    if band == CRITICAL:
        return "critical"
    return f"{SEVERITY_PREFIX[band]}_{sub}"


def compute_severity(
    answers: Dict[str, Dict[str, Any]],
    personalities: Optional[List[Dict[str, Any]]] = None,
    reach_thresholds: Optional[List[tuple]] = None,
) -> Dict[str, Any]:
    """
    Severity from Jev's normalized answers (see jev_client) and the enriched context.

    Returns the SeverityEnum value plus every intermediate step, for logs and audit.
    """
    harm_probabilities = answers["harm"]["probabilities"]
    harm_band = harm_probabilities.index(max(harm_probabilities))
    checkable = answers["checkable"]["probability"] >= BOOLEAN_THRESHOLD
    contestable = answers["contestable"]["probability"] >= BOOLEAN_THRESHOLD

    if not checkable:
        # Nothing to check: reach does not raise it
        matrix_band = LOW
        reach = 0
    else:
        matrix_band = PRIORITY_MATRIX["contestable" if contestable else "not_contestable"][harm_band]
        reach = reach_adjustment(personalities or [], reach_thresholds)

    band = max(LOW, min(CRITICAL, matrix_band + reach))
    sub = sub_band(harm_probabilities)

    return {
        "severity": to_severity(band, sub),
        "band": LEVEL_NAMES[band],
        "harm_band": LEVEL_NAMES[harm_band],
        "checkable": checkable,
        "contestable": contestable,
        "matrix_band": LEVEL_NAMES[matrix_band],
        "reach_adjustment": reach,
        "sub_band": sub,
        # Jev's raw answers, to judge how sure it was of each step
        "harm_probabilities": [round(p, 3) for p in harm_probabilities],
        "harm_confidence": answers["harm"].get("confidence"),
        "checkable_probability": round(answers["checkable"]["probability"], 3),
        "contestable_probability": round(answers["contestable"]["probability"], 3),
        "rubric_version": RUBRIC_VERSION,
    }
