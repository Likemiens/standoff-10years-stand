from __future__ import annotations

import re

from app.constants import VALID_DUAL_DIGIT_PATTERN


def parse_dual_digit_value(raw_value: str, fallback_role: str) -> tuple[str, str] | None:
    value = raw_value.strip()
    if re.fullmatch(r"\d", value):
        return fallback_role, value

    if not re.fullmatch(VALID_DUAL_DIGIT_PATTERN, value):
        return None

    prefix = value[0].lower()
    digit = value[-1]
    if prefix == "t":
        return "tens", digit
    if prefix in {"u", "o"}:
        return "ones", digit
    return None
