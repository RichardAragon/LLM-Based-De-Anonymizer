"""
Stage 1: Extract

Pull structured signals from the input. This stage is purely about
finding what's there — no hypothesis generation, no interpretation.
That comes later.

Signal types extracted:
- Hard identifiers (usernames, email fragments, IDs)
- Style markers (vocabulary, syntax, punctuation patterns)
- Temporal patterns (posting times)
- Technical artifacts (EXIF, URL patterns, platform metadata)
- Explicit location references
"""

import re
import hashlib
from collections import Counter
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from ..models.evidence import Evidence, EvidenceType, EvidenceStrength


@dataclass
class ExtractedSignals:
    """Container for all signals pulled from input."""
    hard_identifiers: List[str]
    email_fragments: List[str]
    url_patterns: List[str]
    style_fingerprint: Dict[str, float]
    temporal_signals: List[str]
    location_references: List[str]
    technical_artifacts: Dict[str, str]
    raw_evidence: List[Evidence]


class Extractor:
    """
    Pulls structured signals from usernames, text samples, or profile URLs.
    """

    # Common username separators and transformations
    USERNAME_TRANSFORMS = [
        lambda u: u.replace("_", ""),
        lambda u: u.replace("-", ""),
        lambda u: u.replace(".", ""),
        lambda u: u + "dev",
        lambda u: u + "_dev",
        lambda u: u + "1",
        lambda u: "the" + u,
    ]

    def extract(self, target: str, target_type: str) -> ExtractedSignals:
        """
        Main extraction entry point.

        Args:
            target: The username, text sample, or URL to analyze
            target_type: "username", "text_sample", or "profile_url"

        Returns:
            ExtractedSignals containing all found signals and Evidence objects
        """
        if target_type == "username":
            return self._extract_from_username(target)
        elif target_type == "text_sample":
            return self._extract_from_text(target)
        elif target_type == "profile_url":
            return self._extract_from_url(target)
        else:
            raise ValueError(f"Unknown target_type: {target_type}")

    def _extract_from_username(self, username: str) -> ExtractedSignals:
        evidence = []
        identifiers = [username]

        # Generate common username variants for cross-platform search
        variants = []
        for transform in self.USERNAME_TRANSFORMS:
            variant = transform(username.lower())
            if variant != username.lower() and len(variant) > 2:
                variants.append(variant)

        # Check for embedded patterns
        email_fragments = []
        # Some usernames contain real name fragments (e.g., john_smith_42)
        name_pattern = re.findall(r'[a-zA-Z]{3,}', username)

        # Check for year patterns (birth year inference)
        year_matches = re.findall(r'(19[6-9]\d|20[0-2]\d)', username)
        temporal_signals = []
        for year in year_matches:
            temporal_signals.append(f"Possible birth/significant year: {year}")
            evidence.append(Evidence(
                evidence_type=EvidenceType.TEMPORAL_PATTERN,
                source="username_analysis",
                raw_value=username,
                extracted_signal=f"Username contains year {year}, possible birth year or significant date",
                strength=EvidenceStrength.WEAK,
                independent=True,
                notes="Year in username is suggestive but not conclusive"
            ))

        # Check for number sequences that might indicate birth date
        date_patterns = re.findall(r'(\d{4}|\d{2}(?:0[1-9]|1[0-2]))', username)

        evidence.append(Evidence(
            evidence_type=EvidenceType.USERNAME_MATCH,
            source="input",
            raw_value=username,
            extracted_signal=f"Primary username: {username}. Variants for cross-platform search: {variants[:5]}",
            strength=EvidenceStrength.MODERATE,
            independent=True,
        ))

        return ExtractedSignals(
            hard_identifiers=identifiers + variants[:5],
            email_fragments=email_fragments,
            url_patterns=[],
            style_fingerprint={},
            temporal_signals=temporal_signals,
            location_references=[],
            technical_artifacts={"username_fragments": str(name_pattern)},
            raw_evidence=evidence,
        )

    def _extract_from_text(self, text: str) -> ExtractedSignals:
        evidence = []

        # --- Style fingerprinting ---
        style = self._compute_style_fingerprint(text)

        evidence.append(Evidence(
            evidence_type=EvidenceType.WRITING_STYLE,
            source="text_sample",
            raw_value=text[:100] + "..." if len(text) > 100 else text,
            extracted_signal=f"Style fingerprint computed: avg_word_len={style.get('avg_word_length', 0):.2f}, "
                             f"punct_density={style.get('punctuation_density', 0):.3f}",
            strength=EvidenceStrength.WEAK,
            independent=True,
            notes="Writing style alone is weak evidence. Useful for corroboration, not identification."
        ))

        # --- Location references ---
        locations = self._extract_location_references(text)
        for loc in locations:
            evidence.append(Evidence(
                evidence_type=EvidenceType.LOCATION_REFERENCE,
                source="text_sample",
                raw_value=loc,
                extracted_signal=f"Explicit location reference: {loc}",
                strength=EvidenceStrength.WEAK,
                independent=True,
                notes="Location references may be incidental, historical, or deliberate misdirection"
            ))

        # --- URL/username fragments in text ---
        urls = re.findall(r'https?://[^\s]+', text)
        usernames_mentioned = re.findall(r'@([a-zA-Z0-9_]{3,20})', text)
        email_fragments = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', text)

        # --- Temporal signals ---
        temporal = self._extract_temporal_signals(text)

        return ExtractedSignals(
            hard_identifiers=usernames_mentioned,
            email_fragments=email_fragments,
            url_patterns=urls,
            style_fingerprint=style,
            temporal_signals=temporal,
            location_references=locations,
            technical_artifacts={},
            raw_evidence=evidence,
        )

    def _extract_from_url(self, url: str) -> ExtractedSignals:
        evidence = []

        # Extract username from URL structure
        # e.g., twitter.com/username, github.com/username
        url_patterns = [
            r'twitter\.com/([^/?\s]+)',
            r'x\.com/([^/?\s]+)',
            r'github\.com/([^/?\s]+)',
            r'reddit\.com/u(?:ser)?/([^/?\s]+)',
            r'instagram\.com/([^/?\s]+)',
            r'linkedin\.com/in/([^/?\s]+)',
            r'youtube\.com/@([^/?\s]+)',
            r'mastodon\.[^/]+/@([^/?\s]+)',
        ]

        found_usernames = []
        platform = "unknown"
        for pattern in url_patterns:
            match = re.search(pattern, url)
            if match:
                found_usernames.append(match.group(1))
                platform = pattern.split(r'\.')[0].lstrip(r'(')

        for username in found_usernames:
            evidence.append(Evidence(
                evidence_type=EvidenceType.PLATFORM_METADATA,
                source=url,
                raw_value=url,
                extracted_signal=f"Username '{username}' on platform derived from URL",
                strength=EvidenceStrength.STRONG,
                independent=True,
            ))

        return ExtractedSignals(
            hard_identifiers=found_usernames,
            email_fragments=[],
            url_patterns=[url],
            style_fingerprint={},
            temporal_signals=[],
            location_references=[],
            technical_artifacts={"platform": platform},
            raw_evidence=evidence,
        )

    def _compute_style_fingerprint(self, text: str) -> Dict[str, float]:
        """
        Compute a basic writing style fingerprint.

        This is intentionally conservative — style analysis is useful for
        corroboration but should never be the primary evidence for attribution.
        """
        if not text:
            return {}

        words = text.split()
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        fingerprint = {}

        if words:
            fingerprint['avg_word_length'] = sum(len(w) for w in words) / len(words)
            fingerprint['vocabulary_richness'] = len(set(w.lower() for w in words)) / len(words)
            fingerprint['long_word_ratio'] = sum(1 for w in words if len(w) > 7) / len(words)

        if sentences:
            fingerprint['avg_sentence_length'] = len(words) / len(sentences)

        # Punctuation patterns
        fingerprint['punctuation_density'] = sum(
            1 for c in text if c in '.,;:!?-—'
        ) / max(len(text), 1)

        # Specific punctuation habits
        fingerprint['uses_oxford_comma'] = float(bool(re.search(r',\s+and\s+', text)))
        fingerprint['em_dash_usage'] = text.count('—') / max(len(sentences), 1)
        fingerprint['ellipsis_usage'] = text.count('...') / max(len(sentences), 1)

        # Capitalization
        fingerprint['all_lowercase_ratio'] = sum(
            1 for w in words if w.islower()
        ) / max(len(words), 1)

        return fingerprint

    def _extract_location_references(self, text: str) -> List[str]:
        """
        Simple location reference extraction.
        In production, this would use a proper NER model.
        """
        # Common US city/state patterns and other markers
        # This is illustrative — a real implementation would use spaCy or similar
        location_markers = re.findall(
            r'\b((?:in|from|near|at|visiting)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b',
            text
        )
        return location_markers

    def _extract_temporal_signals(self, text: str) -> List[str]:
        """Extract temporal signals that might indicate timezone or location."""
        signals = []

        # Time zone references
        tz_patterns = re.findall(r'\b(EST|CST|MST|PST|EDT|CDT|MDT|PDT|UTC[+-]\d+|GMT[+-]\d+)\b', text)
        signals.extend([f"Timezone reference: {tz}" for tz in tz_patterns])

        # "Tonight", "this morning" type phrases (timezone-suggestive if timestamped)
        temporal_anchors = re.findall(
            r'\b(tonight|this morning|this afternoon|yesterday|last night)\b',
            text, re.IGNORECASE
        )
        signals.extend([f"Temporal anchor: {t}" for t in temporal_anchors])

        return signals
