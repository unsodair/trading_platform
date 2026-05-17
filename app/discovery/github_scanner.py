"""
GitHub strategy discovery service — searches GitHub for trading algorithm
repositories, collects metadata, scores them for suitability to Indian
markets, and stores them as CANDIDATE only.

**CRITICAL**: Discovered code is NEVER executed directly.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from github import Github, GithubException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_models import DiscoveredStrategy
from app.models.schemas import CandidateStrategy, StrategyStatus

# ── Search queries tuned for Indian markets ────────────────────────────────────

DEFAULT_QUERIES = [
    "nifty trading strategy python",
    "Indian stock market algo trading",
    "NSE BSE trading bot python",
    "nifty options strategy python",
    "zerodha kite trading strategy",
    "dhan trading algorithm python",
    "banknifty algo strategy",
    "Indian market mean reversion",
    "NSE momentum strategy python",
]

# ── Keywords that boost Indian-market relevance ────────────────────────────────

INDIAN_KEYWORDS = {
    "nifty", "banknifty", "nse", "bse", "sensex", "zerodha", "dhan",
    "kite", "fyer", "upstox", "angel", "indian", "intraday",
    "mcx", "nifty50", "finnifty", "midcpnifty",
}


class GitHubStrategyScanner:
    """
    Searches GitHub, extracts repo metadata, scores relevance, and persists
    candidate strategies. NEVER downloads or executes code.
    """

    def __init__(self) -> None:
        token = settings.github_token
        self._gh = Github(token) if token else Github()

    # ── Public API ─────────────────────────────────────────────────────────

    async def search(
        self,
        queries: list[str] | None = None,
        max_results_per_query: int = 10,
    ) -> list[CandidateStrategy]:
        """Run search queries and return scored candidates."""
        queries = queries or DEFAULT_QUERIES
        all_candidates: dict[str, CandidateStrategy] = {}

        for query in queries:
            try:
                results = await asyncio.to_thread(
                    self._search_github, query, max_results_per_query
                )
                for c in results:
                    if c.repo_url not in all_candidates:
                        all_candidates[c.repo_url] = c
            except Exception as exc:
                logger.error(f"GitHub search error for '{query}': {exc}")

        candidates = list(all_candidates.values())
        candidates.sort(key=lambda c: c.relevance_score, reverse=True)
        logger.info(f"Discovered {len(candidates)} unique candidate strategies")
        return candidates

    async def persist_candidates(
        self, candidates: list[CandidateStrategy], db: AsyncSession
    ) -> int:
        """Save candidates to the database, skipping duplicates."""
        saved = 0
        for c in candidates:
            existing = await db.execute(
                select(DiscoveredStrategy).where(
                    DiscoveredStrategy.repo_url == c.repo_url
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            row = DiscoveredStrategy(
                repo_url=c.repo_url,
                repo_name=c.repo_name,
                description=c.description,
                stars=c.stars,
                language=c.language,
                topics=c.topics,
                relevance_score=c.relevance_score,
                indian_market_compatible=c.indian_market_compatible,
                status=StrategyStatus.CANDIDATE.value,
                discovered_at=c.discovered_at,
            )
            db.add(row)
            saved += 1

        await db.commit()
        logger.info(f"Persisted {saved} new candidate strategies")
        return saved

    async def get_all_candidates(self, db: AsyncSession) -> list[CandidateStrategy]:
        """Retrieve all discovered candidates from the DB."""
        result = await db.execute(
            select(DiscoveredStrategy).order_by(
                DiscoveredStrategy.relevance_score.desc()
            )
        )
        rows = result.scalars().all()
        return [
            CandidateStrategy(
                repo_url=r.repo_url,
                repo_name=r.repo_name,
                description=r.description or "",
                stars=r.stars,
                language=r.language or "",
                topics=r.topics or [],
                relevance_score=r.relevance_score,
                indian_market_compatible=r.indian_market_compatible,
                status=StrategyStatus(r.status),
                discovered_at=r.discovered_at,
                review_notes=r.review_notes or "",
            )
            for r in rows
        ]

    # ── Internal ───────────────────────────────────────────────────────────

    def _search_github(
        self, query: str, max_results: int
    ) -> list[CandidateStrategy]:
        """Synchronous GitHub API search (called via to_thread)."""
        candidates: list[CandidateStrategy] = []
        try:
            repos = self._gh.search_repositories(
                query=query, sort="stars", order="desc"
            )
            for repo in repos[:max_results]:
                desc_lower = (repo.description or "").lower()
                topics = repo.get_topics() if hasattr(repo, "get_topics") else []
                topics_lower = [t.lower() for t in topics]
                all_text = f"{repo.full_name} {desc_lower} {' '.join(topics_lower)}"

                # ── Score relevance ────────────────────────────────────
                score = 0.0
                indian_hits = sum(1 for kw in INDIAN_KEYWORDS if kw in all_text)
                score += min(indian_hits * 0.15, 0.6)
                if repo.stargazers_count >= 100:
                    score += 0.1
                if repo.stargazers_count >= 500:
                    score += 0.1
                if (repo.language or "").lower() == "python":
                    score += 0.1
                if "strategy" in all_text or "algo" in all_text:
                    score += 0.1

                score = min(score, 1.0)
                indian_compatible = indian_hits >= 2

                candidates.append(
                    CandidateStrategy(
                        repo_url=repo.html_url,
                        repo_name=repo.full_name,
                        description=repo.description or "",
                        stars=repo.stargazers_count,
                        language=repo.language or "",
                        topics=topics,
                        relevance_score=round(score, 3),
                        indian_market_compatible=indian_compatible,
                        status=StrategyStatus.CANDIDATE,
                        discovered_at=datetime.now(timezone.utc),
                    )
                )
        except GithubException as exc:
            logger.error(f"GitHub API error: {exc}")
        return candidates


# ── Singleton ──────────────────────────────────────────────────────────────────

_scanner: GitHubStrategyScanner | None = None


def get_github_scanner() -> GitHubStrategyScanner:
    global _scanner
    if _scanner is None:
        _scanner = GitHubStrategyScanner()
    return _scanner
