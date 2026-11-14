"""Initial safety matrix (Phase 0). Deterministic, conservative. Expanded in Phase 1."""
from shared.schemas import SafetyClass

# Category -> keywords that trigger it (matched against user request + observation values).
BLOCKED_CATEGORIES: dict[str, tuple[str, ...]] = {
    "mains_high_voltage": ("mains", "high voltage", "exposed wire", "live wire", "240v", "120v", "power supply open"),
    "swollen_battery": ("swollen", "bulging", "puffy battery", "battery bulge"),
    "smoke_fire_sparks": ("smoke", "fire", "spark", "burning smell", "melting"),
    "gas": ("gas leak", "smell gas", "gas line"),
    "refrigerant": ("refrigerant", "freon", "compressor line"),
    "pressure": ("pressure vessel", "pressurized", "water heater tank"),
    "structural": ("structural", "load-bearing", "ceiling sag"),
    "vehicle_safety": ("brake", "airbag", "steering", "fuel line"),
}


def classify(texts: list[str]) -> tuple[SafetyClass, str | None]:
    """Return (classification, matched category). Any match blocks."""
    blob = " ".join(t.lower() for t in texts if t)
    for category, keywords in BLOCKED_CATEGORIES.items():
        if any(k in blob for k in keywords):
            return SafetyClass.BLOCKED, category
    return SafetyClass.LOW_RISK, None
