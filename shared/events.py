"""Shared event names. Change only with both developers' agreement."""

OBSERVATION = "observation"          # P1 -> P2: ObservationEvent
ACTION_PLAN = "action_plan"          # P2 -> P1: ActionPlan
STEP_VERIFICATION = "step_verification"  # P1 -> P2: observation kind for verified/not_verified/cannot_determine
SESSION_START = "session_start"
SESSION_END = "session_end"
SESSION_CLEAR = "session_clear"
CONTRACT_ERROR = "contract_error"
