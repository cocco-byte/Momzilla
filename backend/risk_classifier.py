import json

import anthropic

from backend.config import MODEL_ID
from backend.models import ChatTurn, RiskTier

_client = anthropic.Anthropic()

CLASSIFIER_SYSTEM_PROMPT = """\
You are a background safety classifier for a student support chat. You are \
given the recent conversation. Your only job is to assess whether the \
student's own messages show signs of an ongoing dilemma, crisis, or risk of \
suicide/self-harm, and assign a risk tier. You do not respond to the \
student - you only classify.

Tiers:
- none: normal conversation, everyday stress, no concerning signals.
- low: general sadness, stress, or a hard day, with no hopelessness or \
ongoing crisis.
- medium: persistent hopelessness, feeling like a burden, withdrawal, or an \
ongoing unresolved crisis (family conflict, bullying, a breakup) - but no \
explicit mention of suicide, self-harm, or wanting to die.
- high: explicit suicidal ideation or self-harm thoughts without a concrete \
plan, means, or timeline (e.g. "sometimes I think about not being here \
anymore").
- imminent: explicit plan, means, timeline, or stated intent to attempt \
suicide or self-harm soon.

Err toward the higher tier when uncertain. Base the assessment only on what \
is actually in the conversation.
"""

_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "tier": {
            "type": "string",
            "enum": ["none", "low", "medium", "high", "imminent"],
        },
        "rationale": {
            "type": "string",
            "description": (
                "One short internal sentence naming the category of signal "
                "seen (e.g. 'persistent hopelessness, no ideation'). Never "
                "quote the student's messages verbatim."
            ),
        },
    },
    "required": ["tier", "rationale"],
    "additionalProperties": False,
}


def classify_risk(history: list[ChatTurn]) -> RiskTier:
    """Classify the conversation's risk tier.

    Only the tier is returned to callers. The rationale exists to give the
    model room to reason but is intentionally discarded here rather than
    logged or persisted - nothing about conversation content should survive
    past this function call.
    """
    transcript = "\n".join(f"{turn.role}: {turn.content}" for turn in history)

    response = _client.messages.create(
        model=MODEL_ID,
        max_tokens=256,
        system=CLASSIFIER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": transcript}],
        output_config={"format": {"type": "json_schema", "schema": _OUTPUT_SCHEMA}},
    )
    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    return RiskTier.from_str(data["tier"])
