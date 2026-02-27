"""
Stage 3: Reason

LLM-assisted hypothesis generation from the evidence corpus.

This stage is explicitly NOT doing the attribution — it's generating
candidate hypotheses that the Calibrate stage will then score.
The distinction matters: the LLM is a hypothesis generator, not
an oracle. Its outputs require calibration before acting on them.

Uses Anthropic Claude via the API. The prompt is structured to:
1. Force explicit chain-of-reasoning
2. Generate both supporting AND contradicting considerations
3. Produce multiple competing hypotheses rather than one confident answer
4. Flag its own uncertainty explicitly
"""

import os
import json
from typing import List, Optional
import anthropic
from ..models.evidence import Evidence, EvidenceType, EvidenceStrength
from ..models.hypothesis import Hypothesis
from ..stages.search import SearchResults


class Reasoner:
    """
    Uses an LLM to generate candidate hypotheses from the evidence corpus.

    The key design principle: the LLM generates possibilities, not conclusions.
    Calibration happens in the next stage.
    """

    SYSTEM_PROMPT = """You are an OSINT analyst assistant. Your job is to generate 
candidate hypotheses from a body of evidence — NOT to reach conclusions.

Your outputs will be fed into a calibration stage that will score them against
the actual evidence. Your job is to be a good hypothesis generator, which means:

1. Generate MULTIPLE competing hypotheses, not one confident answer
2. For each hypothesis, list BOTH supporting AND contradicting considerations
3. Be explicit about what you DON'T know and what evidence is missing
4. Flag when evidence is correlated (comes from the same source) vs independent
5. Never generate a hypothesis with confidence above 0.8 — if you think something
   is certain, check your reasoning for overconfidence
6. Consider alternative explanations: shared usernames, coincidental matches,
   deliberate misdirection

Output valid JSON only. No prose outside the JSON structure."""

    HYPOTHESIS_PROMPT = """Here is the evidence corpus for an attribution investigation.

TARGET: {target}
TARGET TYPE: {target_type}

EVIDENCE ITEMS:
{evidence_summary}

Generate 2-5 candidate hypotheses. For each hypothesis:
- State the specific claim
- List supporting evidence items (reference them by index)
- List contradicting evidence items
- Note any missing evidence that would significantly change confidence
- Suggest a preliminary confidence range (min, max)

Return JSON in this exact format:
{{
  "hypotheses": [
    {{
      "claim": "string",
      "supporting_evidence_indices": [0, 2, 4],
      "contradicting_evidence_indices": [1],
      "missing_evidence": ["what would confirm this", "what would deny this"],
      "preliminary_confidence_min": 0.2,
      "preliminary_confidence_max": 0.6,
      "reasoning": "brief explanation"
    }}
  ],
  "overall_notes": "any meta-observations about the evidence quality or gaps"
}}"""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-opus-4-6"):
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model

    def reason(self, search_results: SearchResults, target: str, target_type: str) -> List[Hypothesis]:
        """
        Generate candidate hypotheses from search results.

        Args:
            search_results: Output from the Searcher stage
            target: Original target input
            target_type: Type of target

        Returns:
            List of Hypothesis objects for the Calibrator to score
        """
        if not search_results.evidence:
            return []

        evidence_summary = self._format_evidence_for_prompt(search_results.evidence)

        prompt = self.HYPOTHESIS_PROMPT.format(
            target=target,
            target_type=target_type,
            evidence_summary=evidence_summary,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        raw_output = response.content[0].text

        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError:
            # If JSON parsing fails, return empty rather than crashing
            return []

        hypotheses = []
        for h_data in parsed.get("hypotheses", []):
            h = Hypothesis(claim=h_data.get("claim", ""))

            # Map evidence by index
            evidence_list = search_results.evidence
            for idx in h_data.get("supporting_evidence_indices", []):
                if 0 <= idx < len(evidence_list):
                    h.add_supporting(evidence_list[idx])

            for idx in h_data.get("contradicting_evidence_indices", []):
                if 0 <= idx < len(evidence_list):
                    h.add_contradicting(evidence_list[idx])

            # Store preliminary confidence range as metadata for calibrator
            h.confidence = (
                h_data.get("preliminary_confidence_min", 0) +
                h_data.get("preliminary_confidence_max", 0)
            ) / 2
            h.confidence_justification = h_data.get("reasoning", "")

            hypotheses.append(h)

        return hypotheses

    def _format_evidence_for_prompt(self, evidence: List[Evidence]) -> str:
        lines = []
        for i, e in enumerate(evidence):
            lines.append(
                f"[{i}] TYPE: {e.evidence_type.value} | "
                f"SOURCE: {e.source} | "
                f"SIGNAL: {e.extracted_signal} | "
                f"STRENGTH: {e.strength.name} | "
                f"INDEPENDENT: {e.independent}"
            )
        return "\n".join(lines)
