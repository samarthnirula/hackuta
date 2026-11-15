"""Per-category hints. Device-agnostic: unknown categories fall back to DEFAULT.

These are *where to look* hints, never facts about a specific unit.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Hints:
    label_location: str
    label_alternative: str
    first_question: str
    synonyms: tuple[str, ...] = field(default_factory=tuple)
    heavy: bool = False


DEFAULT = Hints(
    label_location="the model or rating label, usually on the back, bottom, or inside a door",
    label_alternative="the manual, the original box, or a receipt",
    first_question="What's it doing, or not doing, that it should?",
)

HINTS: dict[str, Hints] = {
    "laptop": Hints(
        label_location="the model label on the bottom of the laptop, near the hinge",
        label_alternative="the system information screen, like 'About This Mac' or Settings > System > About",
        first_question="What's going on with it? Screen, power, keyboard, something else?",
        synonyms=("laptop", "notebook", "macbook", "chromebook", "computer"),
    ),
    "phone": Hints(
        label_location="Settings > General > About, since phones rarely have a printed label",
        label_alternative="the SIM tray or the original box",
        first_question="What's the phone doing that it shouldn't?",
        synonyms=("phone", "iphone", "smartphone", "android", "cell"),
    ),
    "refrigerator": Hints(
        label_location="the rating label inside the fridge, usually on a side wall or near the crisper drawers",
        label_alternative="the manual or a photo of the label from when it was installed",
        first_question="Is it not cooling, leaking, noisy, or something else?",
        synonyms=("fridge", "refrigerator", "freezer"),
        heavy=True,
    ),
    "washing_machine": Hints(
        label_location="the label inside the door rim or on the back panel",
        label_alternative="the manual or the original receipt",
        first_question="Is it not spinning, leaking, not draining, or something else?",
        synonyms=("washer", "washing machine", "dryer"),
        heavy=True,
    ),
    "microwave": Hints(
        label_location="the label inside the door frame or on the back",
        label_alternative="the manual",
        first_question="Is it not heating, not turning on, sparking, or something else?",
        synonyms=("microwave",),
    ),
}


def canonical(name: str | None) -> str | None:
    """Map a free-text object name to a category key, or None if unknown."""
    if not name:
        return None
    n = name.lower().strip()
    for key, h in HINTS.items():
        if n == key or any(s in n for s in h.synonyms):
            return key
    return n.replace(" ", "_")


def mentioned_category(text: str | None) -> str | None:
    """Category the user *names* in their request, if any."""
    if not text:
        return None
    t = text.lower()
    for key, h in HINTS.items():
        if any(s in t for s in h.synonyms):
            return key
    return None


def hints_for(category: str | None) -> Hints:
    return HINTS.get(category or "", DEFAULT)
