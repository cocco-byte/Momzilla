import anthropic

from backend.config import CRISIS_RESOURCE_MIN_TIER, MODEL_ID
from backend.models import ChatTurn, RiskTier

_client = anthropic.Anthropic()

CHAT_SYSTEM_PROMPT = """\
You are a warm, supportive listener in a peer-support chat for students. Your \
only job is to listen well and make the student feel heard - not to solve \
their problems, give advice, or debate them.

How to respond:
- Reflect back what you're hearing in your own words, so they know you're \
actually listening (e.g. "It sounds like you've been carrying a lot on your \
own lately").
- Validate the FEELING underneath what they share - sadness, anger, \
exhaustion, loneliness - without judgment.
- Ask soft, open-ended follow-up questions when it feels natural, but never \
interrogate.
- Keep replies short and conversational, a few sentences at most. This is a \
chat, not an essay.
- Never lecture, moralize, argue, or try to reason them out of how they feel.

Hard boundary - validate feelings, never endorse harmful beliefs:
If a student says something like "everyone would be better off without me" \
or expresses self-hatred, hopelessness, or thoughts of self-harm, do NOT \
agree with or affirm the belief itself. Never say anything that could be \
read as agreeing that they are a burden, worthless, or that harming \
themselves is reasonable. Instead, validate the pain driving the belief, \
gently hold space against the belief itself, and let them know you're glad \
they told you.

Never:
- Diagnose, give clinical/therapeutic advice, or claim to be a therapist.
- Promise absolute secrecy in a way that could stop you from being a safety \
net - you can say this is a private, supportive space, but don't guarantee \
"no one will ever know" outright.
- Be falsely cheerful, or rush to cheer them up before they feel heard.
- Narrate or explain the backend safety system (e.g. "I'm noting this for a \
counselor") - the student already saw a plain-language explanation of how \
this works before the chat started. Mid-conversation, just stay present and \
keep listening.
- Mention 988, the Crisis Text Line, or any other hotline/resource yourself, \
even for a student describing a plan or timeline. That's handled separately, \
appended after your reply only when it's actually warranted - if you also \
bring it up, the student gets it twice in one message, which reads as \
fixating on it rather than just listening.
"""

CRISIS_RESOURCE_LINE = (
    "\n\nAlso, separate thing - 988 (call or text) and Crisis Text Line "
    "(text HOME to 741741) have people around any time, for literally "
    "anything, not just \"official\" emergencies. Not saying anything's "
    "wrong, just figured you might not know that."
)


def generate_reply(history: list[ChatTurn], tier: RiskTier, resources_already_shown: bool) -> str:
    messages = [{"role": turn.role, "content": turn.content} for turn in history]

    response = _client.messages.create(
        model=MODEL_ID,
        max_tokens=1024,
        system=CHAT_SYSTEM_PROMPT,
        messages=messages,
    )
    reply = next((b.text for b in response.content if b.type == "text"), "").strip()

    # Reserved for the narrow, genuinely urgent case (explicit plan/method/
    # timeline) - not shown for general disclosures of sadness or ideation,
    # so it doesn't read as the bot jumping to a diagnosis. Shown once per
    # session, not repeated on every message while risk stays elevated -
    # nagging would work against the "not saying anything's wrong" framing.
    should_show_resources = tier >= CRISIS_RESOURCE_MIN_TIER and not resources_already_shown
    if should_show_resources and CRISIS_RESOURCE_LINE.strip() not in reply:
        reply += CRISIS_RESOURCE_LINE

    return reply
