"""Canonical serialization used by every reproducibility hash."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


def to_primitive(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {field.name: to_primitive(getattr(value, field.name)) for field in dataclasses.fields(value) if field.metadata.get("serialize", True)}
    if isinstance(value, Mapping):
        return {str(key): to_primitive(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [to_primitive(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(to_primitive(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
