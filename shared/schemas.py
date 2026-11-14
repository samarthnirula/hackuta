"""Shared contract v1.0 between Person 1 (realtime/perception) and Person 2 (investigation).

Source of truth: master project doc section 8. Changes require BOTH developers' review.
Unknown values must be None -- never fabricated placeholders.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# ---------- enums ----------

class Action(str, Enum):
    ASK_USER = "ask_user"
    REQUEST_VIEW = "request_view"
    RUN_SAFE_TEST = "run_safe_test"
    SEARCH = "search"
    ANSWER = "answer"
    GUIDE_STEP = "guide_step"
    STOP_UNSAFE = "stop_unsafe"
    REFER_PROFESSIONAL = "refer_professional"
    RECOVER_SESSION = "recover_session"


class Provenance(str, Enum):
    CAMERA_FRAME = "camera_frame"
    OCR_CANDIDATE = "ocr_candidate"
    USER_REPORT = "user_report"
    SYSTEM_METADATA = "system_metadata"
    DIAGNOSTIC_TEST = "diagnostic_test"
    MANUFACTURER_SOURCE = "manufacturer_source"
    TRUSTED_SECONDARY_SOURCE = "trusted_secondary_source"
    COMMERCIAL_LISTING = "commercial_listing"
    MODEL_INFERENCE = "model_inference"


class Certainty(str, Enum):
    CONFIRMED = "confirmed"
    LIKELY = "likely"
    UNKNOWN = "unknown"


class SafetyClass(str, Enum):
    LOW_RISK = "low_risk"
    CAUTION = "caution"
    BLOCKED = "blocked"


class VerificationResult(str, Enum):
    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"
    CANNOT_DETERMINE = "cannot_determine"


# ---------- Person 1 -> Person 2 ----------

class Observation(_Strict):
    observation_id: str
    kind: str  # e.g. object_class, visible_damage, visible_color, step_verification
    value: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)  # model confidence, NOT proof
    provenance: Provenance
    source_ref: Optional[str] = None  # frame/crop id
    verified: bool = False


class FrameQuality(_Strict):
    status: Literal["clear", "degraded", "unusable", "unavailable"] = "clear"
    issues: list[str] = Field(default_factory=list)  # blur, glare, dark, distant, obstructed


class TextCandidate(_Strict):
    candidate_id: str
    text: str
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source_ref: str  # frame/crop reference required for provenance
    bbox: Optional[list[float]] = None
    ambiguity_notes: Optional[str] = None


class Consent(_Strict):
    location_use: bool = False
    media_storage: bool = False


class UserConstraints(_Strict):
    cannot_move_object: bool = False


class MediaCapabilities(_Strict):
    raw_frames: Optional[bool] = None
    outgoing_video: Optional[bool] = None
    messaging: Optional[bool] = None


class ObservationEvent(_Strict):
    schema_version: Literal["1.0"]
    event_id: str
    session_id: str
    timestamp: datetime
    user_request: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("user_request", "user_utterance")
    )
    observations: list[Observation] = Field(default_factory=list)
    frame_quality: FrameQuality = Field(default_factory=FrameQuality)
    visible_text_candidates: list[TextCandidate] = Field(default_factory=list)
    consent: Consent = Field(default_factory=Consent)
    user_constraints: UserConstraints = Field(default_factory=UserConstraints)
    media_capabilities: MediaCapabilities = Field(default_factory=MediaCapabilities)


# ---------- Person 2 -> Person 1 ----------

class RequestedView(_Strict):
    target_object: str
    view: str  # e.g. "underside model label"
    reason: str
    safe_alternative: Optional[str] = None


class RequestedTest(_Strict):
    name: str
    steps: list[str]
    preconditions: list[str] = Field(default_factory=list)
    stop_condition: str


class Claim(_Strict):
    text: str
    supporting_evidence: list[str] = Field(default_factory=list)  # observation/source ids
    certainty: Certainty


class Source(_Strict):
    url: str
    title: Optional[str] = None
    publisher: Optional[str] = None
    retrieved_at: datetime
    model_scope: Optional[str] = None
    provenance: Provenance = Provenance.TRUSTED_SECONDARY_SOURCE


class Safety(_Strict):
    classification: SafetyClass = SafetyClass.LOW_RISK
    blocked: bool = False
    reason: Optional[str] = None


class ActionPlan(_Strict):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    event_id: str
    session_id: str
    in_reply_to: str
    action: Action
    message: str = Field(validation_alias=AliasChoices("message", "spoken_text"))
    requested_view: Optional[RequestedView] = None
    requested_test: Optional[RequestedTest] = None
    needs_more_evidence: bool = True
    claims: list[Claim] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    safety: Safety = Field(default_factory=Safety)

    @property
    def spoken_text(self) -> str:
        """Alias for Person 1's brief."""
        return self.message
