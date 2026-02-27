"""
Stage 2: Search

Query public sources using signals extracted in Stage 1.
All queries target publicly accessible information only.

This stage is intentionally modular — each source is a separate
method so contributors can add/remove sources without touching
the core pipeline logic.
"""

import time
import os
from typing import List, Dict, Optional
from dataclasses import dataclass
from ..models.evidence import Evidence, EvidenceType, EvidenceStrength
from ..stages.extract import ExtractedSignals


@dataclass
class SearchResults:
    """Container for search results before reasoning stage."""
    raw_results: List[Dict]
    evidence: List[Evidence]
    queries_executed: List[str]
    sources_checked: List[str]


class Searcher:
    """
    Queries public sources for signals.

    Search depth options:
    - "surface": Top-level search engine + obvious platform checks
    - "standard": Surface + code repos, domain intel, cached content
    - "deep": Standard + historical content, adjacent username variants
    """

    PLATFORMS = [
        "github.com",
        "reddit.com",
        "stackoverflow.com",
        "news.ycombinator.com",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "instagram.com",
        "mastodon.social",
        "lobste.rs",
    ]

    def __init__(self, serp_api_key: Optional[str] = None):
        self.serp_api_key = serp_api_key or os.getenv("SERP_API_KEY")

    def search(self, signals: ExtractedSignals, depth: str = "standard") -> SearchResults:
        """
        Execute searches based on extracted signals.

        Args:
            signals: Output from the Extractor stage
            depth: "surface", "standard", or "deep"

        Returns:
            SearchResults with evidence items and raw results
        """
        all_evidence = list(signals.raw_evidence)  # Carry forward extraction evidence
        all_results = []
        queries_executed = []
        sources_checked = []

        for identifier in signals.hard_identifiers[:10]:  # Cap to avoid abuse
            if len(identifier) < 3:
                continue

            # Cross-platform username checks
            platform_evidence, platform_queries = self._check_platforms(identifier)
            all_evidence.extend(platform_evidence)
            queries_executed.extend(platform_queries)
            sources_checked.extend(self.PLATFORMS)

            if depth in ("standard", "deep"):
                # Code repository search
                code_evidence, code_queries = self._search_code_repos(identifier)
                all_evidence.extend(code_evidence)
                queries_executed.extend(code_queries)

                # Domain intelligence
                domain_evidence, domain_queries = self._check_domain_intel(identifier)
                all_evidence.extend(domain_evidence)
                queries_executed.extend(domain_queries)

            if depth == "deep":
                # Wayback Machine / cached content
                archive_evidence, archive_queries = self._search_archives(identifier)
                all_evidence.extend(archive_evidence)
                queries_executed.extend(archive_queries)

        # Email fragment searches
        for email in signals.email_fragments[:5]:
            email_evidence, email_queries = self._search_email_fragment(email)
            all_evidence.extend(email_evidence)
            queries_executed.extend(email_queries)

        return SearchResults(
            raw_results=all_results,
            evidence=all_evidence,
            queries_executed=queries_executed,
            sources_checked=list(set(sources_checked)),
        )

    def _check_platforms(self, username: str) -> tuple[List[Evidence], List[str]]:
        """
        Check for username presence across platforms.
        Uses HEAD requests where possible to avoid scraping content.

        In a production implementation, this would use platform-specific
        APIs where available (GitHub API, Reddit API, etc.)
        """
        evidence = []
        queries = []

        # This is where you'd make actual HTTP requests.
        # Scaffolded here with the pattern — implementors fill in the HTTP layer.
        platform_url_patterns = {
            "github": f"https://github.com/{username}",
            "reddit": f"https://reddit.com/user/{username}",
            "stackoverflow": f"https://stackoverflow.com/users/0/{username}",
            "hackernews": f"https://news.ycombinator.com/user?id={username}",
            "twitter": f"https://twitter.com/{username}",
            "mastodon": f"https://mastodon.social/@{username}",
        }

        for platform, url in platform_url_patterns.items():
            queries.append(f"HEAD {url}")
            # Implementors: make a HEAD request here and check response code
            # If 200: create Evidence with MODERATE strength
            # If 404: no evidence to add
            # Rate limit: 1 request/second minimum

        # Also execute a search engine query for the username
        search_query = f'"{username}" site:github.com OR site:reddit.com OR site:stackoverflow.com'
        queries.append(search_query)

        return evidence, queries

    def _search_code_repos(self, username: str) -> tuple[List[Evidence], List[str]]:
        """Search GitHub and similar for code contributions."""
        evidence = []
        queries = [
            f"https://api.github.com/users/{username}",
            f"https://api.github.com/search/users?q={username}",
        ]

        # GitHub API is free for public data, no auth required for basic lookups
        # Implementors: query GitHub API, extract:
        # - Real name if public
        # - Email if public  
        # - Location if public
        # - Joined date
        # - Bio / website
        # - Commit email addresses from public repos (often reveal real email)

        return evidence, queries

    def _check_domain_intel(self, identifier: str) -> tuple[List[Evidence], List[str]]:
        """
        Check domain registration data and certificate transparency logs.

        WHOIS data is increasingly privacy-protected, but:
        - Older registrations may have real data
        - Certificate transparency logs show all domains ever issued a cert
        - Historical WHOIS through services like DomainTools
        """
        evidence = []
        queries = [
            f"https://crt.sh/?q={identifier}&output=json",  # Certificate transparency
            f"https://whois.domaintools.com/{identifier}.com",  # WHOIS (illustrative)
        ]

        # crt.sh is a public CT log search — no API key required
        # Implementors: query crt.sh for domains containing the identifier
        # Domains registered with this name pattern → WHOIS data → potential real info

        return evidence, queries

    def _search_archives(self, identifier: str) -> tuple[List[Evidence], List[str]]:
        """
        Search Wayback Machine and Google Cache for historical content.

        Historical content is particularly valuable because:
        - People were less privacy-conscious in earlier years
        - Old forum posts may contain real names, emails, locations
        - Profile information may have since been scrubbed
        """
        evidence = []
        queries = [
            f"https://web.archive.org/web/*/{identifier}",
            f"https://archive.org/search?query={identifier}",
        ]

        return evidence, queries

    def _search_email_fragment(self, email: str) -> tuple[List[Evidence], List[str]]:
        """Search for an email address across public sources."""
        evidence = []
        queries = [
            f'"{email}"',  # Search engine exact match
            f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",  # HIBP (requires API key)
        ]

        # Note: HIBP API requires a key but is legitimate and designed for this use
        # Only public breach *metadata* is returned, not actual breach data

        if email:
            evidence.append(Evidence(
                evidence_type=EvidenceType.EMAIL_FRAGMENT,
                source="input_text",
                raw_value=email,
                extracted_signal=f"Email address found: {email}",
                strength=EvidenceStrength.STRONG,
                independent=True,
                notes="Email addresses are strong identifiers if verified as active"
            ))

        return evidence, queries
