"""Data Classification, Provenance Tracking, and Outbound Inspection Engine."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from agent_security.core.redaction import SENSITIVE_KEY_PATTERNS, SECRET_REGEXES, REDACTION_MASK


class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


CLASSIFICATION_ORDER = {
    DataClassification.PUBLIC: 1,
    DataClassification.INTERNAL: 2,
    DataClassification.CONFIDENTIAL: 3,
    DataClassification.RESTRICTED: 4,
}


class ClassificationTag(str, Enum):
    PII = "PII"
    CREDENTIALS = "CREDENTIALS"
    FINANCIAL = "FINANCIAL"
    HEALTH = "HEALTH"
    SYSTEM_SECRET = "SYSTEM_SECRET"


# PII and Financial regex patterns
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


@dataclass
class ProvenanceRecord:
    source_id: str
    source_type: str  # e.g., "file", "database", "http_api"
    source_resource: str
    classification: DataClassification
    tags: Set[ClassificationTag] = field(default_factory=set)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OutboundInspectionEngine:
    """Inspects outbound tool calls for classification violations and credential leakages."""

    @classmethod
    def classify_text(cls, text: str) -> Tuple[DataClassification, Set[ClassificationTag]]:
        tags: Set[ClassificationTag] = set()

        # Check for hard secrets
        for pattern in SECRET_REGEXES:
            if pattern.search(text):
                tags.add(ClassificationTag.CREDENTIALS)
                tags.add(ClassificationTag.SYSTEM_SECRET)

        # Check for credit card / SSN
        if CREDIT_CARD_REGEX.search(text):
            tags.add(ClassificationTag.FINANCIAL)
        if SSN_REGEX.search(text):
            tags.add(ClassificationTag.PII)

        if ClassificationTag.CREDENTIALS in tags or ClassificationTag.SYSTEM_SECRET in tags:
            return DataClassification.RESTRICTED, tags
        if ClassificationTag.FINANCIAL in tags or ClassificationTag.PII in tags:
            return DataClassification.CONFIDENTIAL, tags

        return DataClassification.INTERNAL, tags

    @classmethod
    def inspect_payload(
        cls,
        payload: Any,
        max_allowed_classification: DataClassification = DataClassification.INTERNAL,
    ) -> Tuple[bool, List[str], Any]:
        """Inspects payload for egress. Returns (is_permitted, list_of_violations, sanitized_payload)."""
        violations: List[str] = []
        max_allowed_rank = CLASSIFICATION_ORDER[max_allowed_classification]

        def _scan(data: Any, path: str = "") -> Any:
            if isinstance(data, dict):
                sanitized_dict = {}
                for k, v in data.items():
                    k_str = str(k).lower().replace("-", "_")
                    sub_path = f"{path}.{k}" if path else str(k)
                    if any(pat in k_str for pat in SENSITIVE_KEY_PATTERNS):
                        violations.append(f"Forbidden sensitive key '{sub_path}' detected in outbound payload")
                        sanitized_dict[k] = REDACTION_MASK
                    else:
                        sanitized_dict[k] = _scan(v, sub_path)
                return sanitized_dict
            elif isinstance(data, list):
                return [_scan(item, f"{path}[{i}]") for i, item in enumerate(data)]
            elif isinstance(data, str):
                classification, tags = cls.classify_text(data)
                rank = CLASSIFICATION_ORDER[classification]
                if rank > max_allowed_rank:
                    tag_names = ", ".join(t.value for t in tags)
                    violations.append(
                        f"Data classification violation at '{path or 'root'}': contains {classification.value} data ({tag_names}) exceeding allowed {max_allowed_classification.value}"
                    )
                sanitized_str = data
                for pattern in SECRET_REGEXES:
                    sanitized_str = pattern.sub(REDACTION_MASK, sanitized_str)
                return sanitized_str
            return data

        sanitized_payload = _scan(payload)
        is_permitted = len(violations) == 0
        return is_permitted, violations, sanitized_payload
