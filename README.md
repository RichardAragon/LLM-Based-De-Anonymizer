# ESRC: Extract → Search → Reason → Calibrate

A research framework for structured OSINT attribution using a four-stage pipeline with explicit confidence calibration.

---

## What This Is

ESRC is a systematic framework for connecting pseudonymous or anonymous online identities to real-world context using only publicly available information. It is designed for:

- **Security researchers** investigating coordinated inauthentic behavior
- **Journalists** conducting public-interest investigations
- **Threat intelligence analysts** tracking malicious actors
- **Academic researchers** studying online identity and anonymity
- **Individuals** investigating harassment, doxxing, or fraud targeting themselves

The pipeline enforces structured reasoning and explicit uncertainty quantification at every stage, resisting the overconfidence that makes ad-hoc OSINT dangerous.

---

## Why This Exists

Deanonymization capabilities exist. The barrier to entry has dropped from "requires significant technical resources" to "requires an LLM and a few hours." Containment of this knowledge primarily benefits actors who already have it — well-resourced state and corporate entities — while leaving individuals, journalists, and civil society without equivalent tools or understanding.

This repository exists to:
1. Make the methodology legible so that **defenses can be built**
2. Give **accountable actors** structured access to capabilities that unaccountable ones already use
3. Force an honest public conversation about what is actually possible

If you are uncomfortable with this technology existing, the correct response is to advocate for the legal and social frameworks that govern its use — not to pretend the capability does not exist.

---

## The Pipeline

```
[Input: Username / Content / Profile]
         │
         ▼
   ┌─────────────┐
   │   EXTRACT   │  ← Pull identifiers, style markers, metadata
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │   SEARCH    │  ← Query public sources, cross-reference
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │   REASON    │  ← LLM-assisted hypothesis generation
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │  CALIBRATE  │  ← Confidence scoring, uncertainty propagation
   └──────┬──────┘
          │
          ▼
  [Output: Attributed profile with confidence intervals]
```

### Stage 1: Extract
Pulls structured signals from input content:
- Usernames, email fragments, profile metadata
- Writing style fingerprints (vocabulary, syntax patterns, punctuation habits)
- Temporal patterns (posting times → timezone inference)
- Technical artifacts (EXIF data, URL patterns, platform-specific metadata)
- Cross-platform consistency markers

### Stage 2: Search
Systematic querying of public sources using extracted signals:
- Search engine dorking with extracted identifiers
- Social platform search (public content only)
- Domain WHOIS / certificate transparency logs
- GitHub, HackerNews, Stack Overflow, Reddit search
- Wayback Machine / cached content
- Breach data indexes (public, non-password data only)

### Stage 3: Reason
LLM-assisted hypothesis generation and evidence synthesis:
- Generates candidate identity hypotheses from evidence clusters
- Identifies corroborating and contradicting evidence
- Flags coincidence vs. pattern vs. confirmation
- Explicitly tracks the evidence chain for each hypothesis

### Stage 4: Calibrate
Structured confidence scoring — the part most ad-hoc OSINT skips:
- Per-claim confidence scores (0.0–1.0) with explicit justification
- Independence weighting (correlated evidence doesn't compound)
- Minimum evidence thresholds before surfacing results
- Output formatted for auditability, not just consumption

---

## Installation

```bash
git clone https://github.com/yourusername/osrc-esrc
cd osrc-esrc
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

**Requirements:**
- Python 3.11+
- Anthropic API key (for Reason stage)
- Optional: SerpAPI key (for Search stage automation)

---

## Usage

```python
from esrc import Pipeline

pipeline = Pipeline()

result = pipeline.run(
    target="username_or_content",
    target_type="username",  # or "text_sample", "profile_url"
    search_depth="standard",  # or "surface", "deep"
)

print(result.summary())
print(result.confidence_report())
```

Or from the command line:

```bash
python -m esrc --target "example_username" --type username --depth standard
```

---

## Output Format

```json
{
  "hypotheses": [
    {
      "claim": "Subject is likely based in [region]",
      "confidence": 0.74,
      "evidence": ["posting_times", "language_variant", "referenced_locations"],
      "independence_adjusted": true,
      "contradicting_evidence": []
    }
  ],
  "overall_attribution_confidence": 0.61,
  "evidence_chain": [...],
  "warnings": ["Only 3 independent signal sources. Increase search depth for higher confidence."],
  "timestamp": "2026-02-27T00:00:00Z"
}
```

---

## Ethical Use

This tool surfaces public information. It does not:
- Access private accounts or data
- Bypass authentication
- Scrape at scale in violation of platform ToS
- Aggregate or store results in any central database

**You are responsible for what you do with output.** The following uses are outside the intended scope of this project and the author accepts no responsibility for them:
- Targeting private individuals who are not public figures and who have not engaged in public harm
- Harassment, stalking, or intimidation
- Use by authoritarian governments or actors targeting dissidents, journalists, or activists
- Commercial data aggregation

The calibration output is designed to resist overconfidence. If the tool says 0.4 confidence, that means the evidence is weak. Act accordingly.

---

## Architecture

```
esrc/
├── pipeline.py          # Main orchestration
├── stages/
│   ├── extract.py       # Signal extraction
│   ├── search.py        # Public source querying
│   ├── reason.py        # LLM hypothesis generation
│   └── calibrate.py     # Confidence scoring
├── sources/
│   ├── search_engines.py
│   ├── social_platforms.py
│   ├── domain_intel.py
│   └── code_repositories.py
├── models/
│   ├── hypothesis.py
│   ├── evidence.py
│   └── result.py
└── utils/
    ├── style_analysis.py
    ├── temporal_analysis.py
    └── metadata_extraction.py
```

---

## Contributing

PRs welcome. Priority areas:
- Additional public source integrations
- Improved style fingerprinting
- Better independence detection in evidence weighting
- Defensive use cases (helping individuals understand their own exposure)

---

## License

MIT. Use it. Build on it. Build defenses with it.
