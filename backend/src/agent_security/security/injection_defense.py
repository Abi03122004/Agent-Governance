"""Untrusted Tool Output Labeling and Indirect Prompt Injection Defense Engine.

Provides:
1. Pattern detection for indirect prompt injection, system prompt overrides, and jailbreaks.
2. Exfiltration trigger detection (secrets transmission, unauthorized upload/curl).
3. Chat template delimiter smuggling detection (<|im_start|>, [INST], <<SYS>>, etc.).
4. Strict isolation boundary wrapper (<untrusted_tool_output>) with metadata labeling.
"""

import hashlib
import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class ThreatCategory(str, Enum):
    INDIRECT_PROMPT_INJECTION = "INDIRECT_PROMPT_INJECTION"
    SYSTEM_OVERRIDE = "SYSTEM_OVERRIDE"
    EXFILTRATION_TRIGGER = "EXFILTRATION_TRIGGER"
    DELIMITER_SMUGGLING = "DELIMITER_SMUGGLING"
    JAILBREAK_ATTEMPT = "JAILBREAK_ATTEMPT"


class TrustLevel(str, Enum):
    UNTRUSTED = "UNTRUSTED"
    SANITIZED = "SANITIZED"
    VERIFIED_INTERNAL = "VERIFIED_INTERNAL"


# Regex patterns for indirect prompt injection and system override
PROMPT_OVERRIDE_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|directions|prompts|rules)", re.IGNORECASE),
    re.compile(r"\bdisregard\b[^\n.!?]{0,35}\b(?:guidelines|instructions|directives|rules)\b", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:DAN|unrestricted|an\s+evil|in\s+developer\s+mode|freed)", re.IGNORECASE),
    re.compile(r"\b(?:system\s+override|override\s+system\s+prompt)\b", re.IGNORECASE),
    re.compile(r"new\s+(?:system\s+prompt|directive|instruction)\s*:", re.IGNORECASE),
    re.compile(r"bypass\s+(?:all\s+)?(?:security|guardrails|safety\s+filters|policies)", re.IGNORECASE),
    re.compile(r"forget\s+(?:all\s+)?(?:rules|restrictions|instructions)", re.IGNORECASE),
    re.compile(r"stop\s+acting\s+as\s+(?:an?\s+)?(?:ai|assistant)", re.IGNORECASE),
    re.compile(r"\benter\s+developer\s+mode\b", re.IGNORECASE),
]

# Regex patterns for credential/data exfiltration triggers
EXFILTRATION_PATTERNS = [
    re.compile(r"\b(?:exfiltrat(?:e|ion)|leak\s+secrets)\b", re.IGNORECASE),
    re.compile(r"\b(?:send|upload|post|transmit|forward)\b[^\n.!?]{0,60}\b(?:secrets?|tokens?|passwords?|credentials?|api_keys?|\.env)\b[^\n.!?]{0,60}\b(?:to|via|into)\b", re.IGNORECASE),
    re.compile(r"(?:curl|wget|fetch)\s+-[^\n]*https?://[^\s]+\b", re.IGNORECASE),
    re.compile(r"!\[(?:.*?)\]\(https?://[^\s)]+\?[^)]*(?:token|secret|key|password|credential|leak)=[^)]*\)", re.IGNORECASE),  # Markdown image exfiltration
    re.compile(r"<img\s+src=[\"']https?://[^\s\"']+\?[^\s\"']*(?:token|secret|key|password|credential)=[^\"']*[\"']", re.IGNORECASE),  # HTML image exfiltration
]

# Regex patterns for control token / chat template smuggling
DELIMITER_SMUGGLING_PATTERNS = [
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"<\|endoftext\|>", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"\[/INST\]", re.IGNORECASE),
    re.compile(r"<<SYS>>", re.IGNORECASE),
    re.compile(r"<</SYS>>", re.IGNORECASE),
    re.compile(r"Human:\s*\nAssistant:", re.IGNORECASE),
    re.compile(r"System:\s*\nYou\s+are", re.IGNORECASE),
]


@dataclass
class InjectionScanResult:
    threat_detected: bool
    categories: List[ThreatCategory] = field(default_factory=list)
    matched_patterns: List[str] = field(default_factory=list)
    risk_score: float = 0.0  # 0.0 (clean) to 1.0 (critical threat)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UntrustedOutputWrapper:
    source_tool: str
    trust_level: TrustLevel
    threat_scan: InjectionScanResult
    raw_content: str
    isolated_content: str
    content_hash: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_safe_for_consumption(self) -> bool:
        """Indicates if the output can be safely processed without executing attacker instructions."""
        return not self.threat_scan.threat_detected or self.threat_scan.risk_score < 0.7


class InjectionDetector:
    """Scans untrusted inputs and tool outputs for adversarial injections and exfiltration triggers."""

    @classmethod
    def scan(cls, content: str) -> InjectionScanResult:
        if not content or not content.strip():
            return InjectionScanResult(threat_detected=False, risk_score=0.0)

        categories: Set[ThreatCategory] = set()
        matched_patterns: List[str] = []
        score = 0.0

        # 1. Prompt override / System override detection
        for pat in PROMPT_OVERRIDE_PATTERNS:
            match = pat.search(content)
            if match:
                categories.add(ThreatCategory.INDIRECT_PROMPT_INJECTION)
                categories.add(ThreatCategory.SYSTEM_OVERRIDE)
                matched_patterns.append(match.group(0))
                score = max(score, 0.85)

        # 2. Exfiltration trigger detection
        for pat in EXFILTRATION_PATTERNS:
            match = pat.search(content)
            if match:
                categories.add(ThreatCategory.EXFILTRATION_TRIGGER)
                matched_patterns.append(match.group(0))
                score = max(score, 0.95)

        # 3. Delimiter / Template smuggling detection
        for pat in DELIMITER_SMUGGLING_PATTERNS:
            match = pat.search(content)
            if match:
                categories.add(ThreatCategory.DELIMITER_SMUGGLING)
                matched_patterns.append(match.group(0))
                score = max(score, 0.75)

        threat_detected = len(categories) > 0

        return InjectionScanResult(
            threat_detected=threat_detected,
            categories=sorted(list(categories), key=lambda c: c.value),
            matched_patterns=matched_patterns,
            risk_score=score if threat_detected else 0.0,
            details={
                "pattern_count": len(matched_patterns),
                "inspected_length": len(content),
            },
        )

    @classmethod
    def wrap_untrusted_output(
        cls,
        raw_output: Any,
        source_tool: str,
        sanitize: bool = True,
    ) -> UntrustedOutputWrapper:
        """Demarcates untrusted tool output inside cryptographic and semantic isolation boundaries."""
        content_str = str(raw_output) if not isinstance(raw_output, str) else raw_output
        scan = cls.scan(content_str)

        content_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()

        # Sanitize control delimiters so nested tags cannot escape boundary
        escaped_content = content_str
        if sanitize:
            # Neutralize template delimiters if present
            for pat in DELIMITER_SMUGGLING_PATTERNS:
                escaped_content = pat.sub("[STRIPPED_CONTROL_TOKEN]", escaped_content)
            # Escape angle brackets of potential fake closing tags
            escaped_content = escaped_content.replace("</untrusted_tool_output>", "&lt;/untrusted_tool_output&gt;")

        # Format immutable boundary wrapper
        trust_level = (
            TrustLevel.SANITIZED
            if (scan.threat_detected and sanitize)
            else (TrustLevel.UNTRUSTED)
        )

        isolated = (
            f'<untrusted_tool_output source="{html.escape(source_tool)}" '
            f'hash="sha256:{content_hash}" '
            f'trust_level="{trust_level.value}" '
            f'risk_score="{scan.risk_score:.2f}">\n'
            f"{escaped_content}\n"
            f"</untrusted_tool_output>"
        )

        return UntrustedOutputWrapper(
            source_tool=source_tool,
            trust_level=trust_level,
            threat_scan=scan,
            raw_content=content_str,
            isolated_content=isolated,
            content_hash=f"sha256:{content_hash}",
        )
