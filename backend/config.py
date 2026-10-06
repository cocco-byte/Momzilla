import os

from dotenv import load_dotenv

from backend.models import RiskTier

# Loads variables from a .env file in the working directory (if present) into
# the real process environment. Must happen before anything below reads
# os.environ, and before chat_agent.py / risk_classifier.py construct their
# anthropic.Anthropic() clients - both import this module first, so this
# runs in time as long as nothing constructs a client before importing
# backend.config.
load_dotenv()

MODEL_ID = os.environ.get("MOMZILLA_MODEL_ID", "claude-opus-5")

# Lowest tier that triggers a counselor notification. Below this, nothing
# leaves the process at all.
ESCALATION_MIN_TIER = RiskTier.MEDIUM

# Lowest tier at which the bot itself offers crisis resources directly to
# the student, independent of whether/when a counselor gets notified.
# Deliberately reserved for "imminent" (explicit plan/method/timeline) only -
# showing it at "high" (ideation without a plan) reads as the bot jumping to
# a diagnosis and can put students off opening up further.
CRISIS_RESOURCE_MIN_TIER = RiskTier.IMMINENT

# Never log raw message content. This flag only ever gates printing the
# classifier's risk TIER (not conversation text, not rationale) to stdout
# for local debugging. Leave off anywhere real students are talking.
DEBUG_LOG_TIERS = os.environ.get("MOMZILLA_DEBUG_LOG_TIERS", "false").lower() == "true"
