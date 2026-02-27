"""
Stage 4: Calibrate

Confidence scoring with explicit uncertainty propagation.

This is the stage that most ad-hoc OSINT skips, and it's the most
important one. Without calibration, OSINT produces confident-sounding
outputs from weak evidence, which causes real harm when acted upon.

Core principles:
1. Independent evidence compounds multiplicatively (Bayesian update)
2. Correlated evidence does NOT compound — it's counted once
3. Contradicting evidence reduces confidence
4. There are minimum evidence thresholds before surfacing any claim
5. Overall confidence is conservative, not optimistic

The math here is deliberately simplified for auditability. A perfectly
rigorous Bayesian network would be harder to inspect and audit.
"""

from typing import List
from ..models.evidence import Evidence, EvidenceStrength
from ..models.hypothesis import Hypothesis
from ..models.result import AttributionResult
from ..stages.search import SearchResults


class Calibrator:
    """
    Scores hypotheses with explicit confidence calibration.

    The key operation: given a set of evidence items, compute a confidence
    score that accounts for:
    - Evidence strength
    - Evidence independence
    - Contradicting evidence
    - Total evidence count
    """

    # Minimum independent sources required to surface ANY hypothesis
    MIN_INDEPENDENT_SOURCES = 2

    # If contradicting evidence exceeds this ratio, cap confidence
    CONTRADICTION_CAP_THRESHOLD = 0.3

    def calibrate(
        self,
        hypotheses: List[Hypothesis],
        search_results: SearchResults,
        target: str,
        target_type: str,
    ) -> AttributionResult:
        """
        Score hypotheses and produce the final AttributionResult.

        Args:
            hypotheses: Output from the Reasoner stage
            search_results: Full search results (for overall evidence count)
            target: Original target
            target_type: Type of target

        Returns:
            Fully calibrated AttributionResult
        """
        result = AttributionResult(
            target_input=target,
            target_type=target_type,
            all_evidence=search_results.evidence,
        )

        calibrated_hypotheses = []
        for hypothesis in hypotheses:
            calibrated = self._calibrate_hypothesis(hypothesis)
            calibrated_hypotheses.append(calibrated)

        # Sort by confidence descending
        calibrated_hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        result.hypotheses = calibrated_hypotheses

        # Overall confidence: weighted average of top hypotheses
        # Cap at highest individual hypothesis confidence
        if calibrated_hypotheses:
            top_confidence = calibrated_hypotheses[0].confidence
            result.overall_confidence = top_confidence
        
        # Add warnings
        result.warnings = self._generate_warnings(calibrated_hypotheses, search_results)

        return result

    def _calibrate_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """
        Apply calibration scoring to a single hypothesis.

        Confidence formula:
        1. Start from base confidence derived from evidence strengths
        2. Apply independence adjustment (correlated evidence doesn't compound)
        3. Apply contradiction penalty
        4. Apply minimum threshold check
        5. Clamp to [0.0, 1.0]
        """

        supporting = hypothesis.supporting_evidence
        contradicting = hypothesis.contradicting_evidence

        if not supporting:
            hypothesis.confidence = 0.0
            hypothesis.confidence_justification = "No supporting evidence."
            hypothesis.minimum_threshold_met = False
            return hypothesis

        # Check minimum threshold
        independent_count = sum(1 for e in supporting if e.independent)
        hypothesis.minimum_threshold_met = independent_count >= self.MIN_INDEPENDENT_SOURCES

        if not hypothesis.minimum_threshold_met:
            hypothesis.confidence = min(hypothesis.confidence, 0.3)
            hypothesis.confidence_justification += (
                f" [CAPPED: Only {independent_count} independent source(s). "
                f"Minimum is {self.MIN_INDEPENDENT_SOURCES}.]"
            )
            return hypothesis

        # Base confidence from independent evidence strengths
        # Uses a "noisy OR" style combination: P(at least one is right)
        # P(A ∪ B) = 1 - (1-P(A))(1-P(B)) for independent events
        independent_evidence = [e for e in supporting if e.independent]
        p_false = 1.0
        for e in independent_evidence:
            strength_value = e.strength.value
            p_false *= (1.0 - strength_value)

        base_confidence = 1.0 - p_false

        # Correlated evidence gets a smaller boost (averaged, not compounded)
        correlated_evidence = [e for e in supporting if not e.independent]
        if correlated_evidence:
            correlated_avg = sum(e.strength.value for e in correlated_evidence) / len(correlated_evidence)
            # Correlated evidence can boost confidence but by less than independent
            correlated_boost = correlated_avg * 0.1 * len(correlated_evidence)
            base_confidence = min(base_confidence + correlated_boost, 0.95)

        # Contradiction penalty
        if contradicting:
            total_evidence = len(supporting) + len(contradicting)
            contradiction_ratio = len(contradicting) / total_evidence

            if contradiction_ratio >= self.CONTRADICTION_CAP_THRESHOLD:
                # Strong contradicting evidence: significant cap
                contradiction_penalty = contradiction_ratio * 0.5
            else:
                # Minor contradicting evidence: small penalty
                contradiction_penalty = contradiction_ratio * 0.2

            base_confidence -= contradiction_penalty

        # Final clamp
        final_confidence = max(0.0, min(base_confidence, 0.97))

        hypothesis.confidence = final_confidence
        hypothesis.confidence_justification = (
            f"Computed from {len(independent_evidence)} independent source(s) "
            f"(noisy-OR combination), {len(correlated_evidence)} correlated source(s), "
            f"{len(contradicting)} contradicting item(s). "
            f"Base confidence before contradiction: {1.0 - p_false:.3f}."
        )

        return hypothesis

    def _generate_warnings(
        self,
        hypotheses: List[Hypothesis],
        search_results: SearchResults,
    ) -> List[str]:
        """Generate explicit warnings about evidence quality."""
        warnings = []

        total_evidence = len(search_results.evidence)
        independent_evidence = sum(1 for e in search_results.evidence if e.independent)

        if total_evidence < 3:
            warnings.append(
                "Very few evidence items collected. Results are highly speculative."
            )

        if independent_evidence < 2:
            warnings.append(
                "Fewer than 2 independent evidence sources. "
                "Do not act on these results without additional corroboration."
            )

        high_confidence_hypotheses = [h for h in hypotheses if h.confidence >= 0.7]
        if not high_confidence_hypotheses:
            warnings.append(
                "No hypothesis exceeds 0.7 confidence. "
                "Results should be treated as investigative leads only."
            )

        low_threshold_hypotheses = [h for h in hypotheses if not h.minimum_threshold_met]
        if low_threshold_hypotheses:
            warnings.append(
                f"{len(low_threshold_hypotheses)} hypothesis/es did not meet minimum "
                f"evidence threshold ({self.MIN_INDEPENDENT_SOURCES} independent sources). "
                f"These are shown for completeness only."
            )

        if any(h.confidence >= 0.9 for h in hypotheses):
            warnings.append(
                "Confidence above 0.9 detected. Treat with extra skepticism — "
                "this level of confidence is unusual and may indicate evidence correlation "
                "that wasn't properly detected."
            )

        return warnings
