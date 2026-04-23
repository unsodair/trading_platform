"""
Discovery API routes — GitHub strategy search, candidates management.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.discovery.github_scanner import get_github_scanner
from app.models.schemas import CandidateStrategy

router = APIRouter(prefix="/api/discovery", tags=["Discovery"])


@router.post("/search")
async def search_strategies(
    queries: list[str] | None = None,
    max_per_query: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """
    Search GitHub for trading algorithm repositories.
    Results are stored as CANDIDATE only — never auto-activated.
    """
    scanner = get_github_scanner()
    candidates = await scanner.search(queries=queries, max_results_per_query=max_per_query)
    saved = await scanner.persist_candidates(candidates, db)
    return {
        "found": len(candidates),
        "new_saved": saved,
        "candidates": [c.model_dump() for c in candidates[:20]],
    }


@router.get("/candidates", response_model=list[CandidateStrategy])
async def list_candidates(db: AsyncSession = Depends(get_db)):
    """List all discovered candidate strategies."""
    scanner = get_github_scanner()
    return await scanner.get_all_candidates(db)


@router.post("/candidates/{repo_name}/review")
async def review_candidate(
    repo_name: str,
    notes: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Mark a candidate strategy as reviewed with notes."""
    from sqlalchemy import select, update
    from app.models.db_models import DiscoveredStrategy
    from app.models.schemas import StrategyStatus

    await db.execute(
        update(DiscoveredStrategy)
        .where(DiscoveredStrategy.repo_name == repo_name)
        .values(status=StrategyStatus.REVIEWED.value, review_notes=notes)
    )
    await db.commit()
    return {"status": "reviewed", "repo": repo_name}


@router.post("/candidates/{repo_name}/approve")
async def approve_candidate(repo_name: str, db: AsyncSession = Depends(get_db)):
    """
    Approve a candidate for conversion to internal plugin format.
    NOTE: This does NOT execute any external code — it only changes status.
    Manual conversion to plugin format is still required.
    """
    from sqlalchemy import update
    from app.models.db_models import DiscoveredStrategy
    from app.models.schemas import StrategyStatus

    await db.execute(
        update(DiscoveredStrategy)
        .where(DiscoveredStrategy.repo_name == repo_name)
        .values(status=StrategyStatus.APPROVED.value)
    )
    await db.commit()
    return {
        "status": "approved",
        "repo": repo_name,
        "note": "Approved for manual conversion. No code has been executed.",
    }
