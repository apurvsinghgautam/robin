"""Investigation API endpoints."""
import asyncio
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...db.models import Investigation, Message
from ...models.investigation import (
    InvestigationCreate,
    InvestigationResponse,
    InvestigationDetail,
    InvestigationSummary,
    InvestigationStatus,
    FollowUpRequest,
    ListInvestigationsResponse,
)
from ...models.graph import GraphData
from ...services.agent_service import (
    AgentService,
    get_agent,
    set_agent,
    remove_agent,
)
from ...services.graph_service import GraphService
from ...sse.stream import SSEStreamManager
from ...config import get_settings

router = APIRouter(prefix="/investigations", tags=["investigations"])
settings = get_settings()


@router.post("", response_model=InvestigationResponse)
async def create_investigation(
    request: InvestigationCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Start a new investigation.

    Returns investigation ID and stream URL for SSE connection.
    """
    investigation_id = uuid4()

    # Create database record
    investigation = Investigation(
        id=investigation_id,
        initial_query=request.query,
        model=request.model or settings.default_model,
        status=InvestigationStatus.PENDING,
    )
    db.add(investigation)
    await db.commit()

    # Create SSE stream manager
    stream_manager = SSEStreamManager(str(investigation_id))

    # Create and cache agent service
    agent = AgentService(
        investigation_id=investigation_id,
        stream_manager=stream_manager,
        model=request.model,
    )
    set_agent(investigation_id, agent)

    # Start investigation in background
    asyncio.create_task(
        _run_investigation(investigation_id, request.query, db)
    )

    return InvestigationResponse(
        id=investigation_id,
        stream_url=f"{settings.api_prefix}/investigations/{investigation_id}/stream",
        status=InvestigationStatus.PENDING,
    )


async def _run_investigation(
    investigation_id: UUID,
    query: str,
    db: AsyncSession,
) -> None:
    """Background task to run investigation."""
    agent = get_agent(investigation_id)
    if not agent:
        return

    try:
        # Update status to running
        stmt = select(Investigation).where(Investigation.id == investigation_id)
        result = await db.execute(stmt)
        investigation = result.scalar_one_or_none()
        if investigation:
            investigation.status = InvestigationStatus.RUNNING
            await db.commit()

        # Add user message
        user_message = Message(
            investigation_id=investigation_id,
            role="user",
            content=query,
        )
        db.add(user_message)
        await db.commit()

        # Run investigation
        start_time = datetime.now()
        result = await agent.investigate(query)
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        # Update investigation with results
        investigation.status = InvestigationStatus.COMPLETED
        investigation.full_response = result.text
        investigation.session_id = result.session_id
        investigation.num_turns = result.num_turns
        investigation.duration_ms = duration_ms
        investigation.tools_used = agent.tools_used
        investigation.completed_at = end_time

        # Add assistant message
        assistant_message = Message(
            investigation_id=investigation_id,
            role="assistant",
            content=result.text,
            tool_calls=agent.tools_used,
        )
        db.add(assistant_message)
        await db.commit()

    except Exception as e:
        # Update status to failed
        stmt = select(Investigation).where(Investigation.id == investigation_id)
        result = await db.execute(stmt)
        investigation = result.scalar_one_or_none()
        if investigation:
            investigation.status = InvestigationStatus.FAILED
            await db.commit()

        await agent.stream.emit_error(str(e))

    finally:
        # Keep agent in cache for follow-ups
        pass


@router.get("/{investigation_id}/stream")
async def stream_investigation(investigation_id: UUID):
    """
    SSE endpoint for streaming investigation results.

    Connect to this endpoint after creating an investigation to receive
    real-time updates: text chunks, tool executions, and completion.
    """
    agent = get_agent(investigation_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Investigation not found")

    return StreamingResponse(
        agent.stream.stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{investigation_id}/follow-up", response_model=InvestigationResponse)
async def send_follow_up(
    investigation_id: UUID,
    request: FollowUpRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a follow-up query in the same investigation session.

    The agent retains context from the original investigation.
    """
    agent = get_agent(investigation_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Investigation session not found")

    # Reset stream for new response
    agent.stream = SSEStreamManager(str(investigation_id))

    # Add user message
    user_message = Message(
        investigation_id=investigation_id,
        role="user",
        content=request.query,
    )
    db.add(user_message)
    await db.commit()

    # Start follow-up in background
    asyncio.create_task(
        _run_follow_up(investigation_id, request.query, db)
    )

    return InvestigationResponse(
        id=investigation_id,
        stream_url=f"{settings.api_prefix}/investigations/{investigation_id}/stream",
        status=InvestigationStatus.RUNNING,
    )


async def _run_follow_up(
    investigation_id: UUID,
    query: str,
    db: AsyncSession,
) -> None:
    """Background task to run follow-up."""
    agent = get_agent(investigation_id)
    if not agent:
        return

    try:
        result = await agent.follow_up(query)

        # Add assistant message
        assistant_message = Message(
            investigation_id=investigation_id,
            role="assistant",
            content=result.text,
            tool_calls=agent.tools_used,
        )
        db.add(assistant_message)

        # Update investigation response
        stmt = select(Investigation).where(Investigation.id == investigation_id)
        db_result = await db.execute(stmt)
        investigation = db_result.scalar_one_or_none()
        if investigation:
            investigation.full_response = (
                (investigation.full_response or "") + "\n\n---\n\n" + result.text
            )
            investigation.tools_used = (
                investigation.tools_used or []
            ) + agent.tools_used

        await db.commit()

    except Exception as e:
        await agent.stream.emit_error(str(e))


@router.get("", response_model=ListInvestigationsResponse)
async def list_investigations(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    page_size: int = Query(None, ge=1, le=100),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List investigations with pagination and optional search."""
    # Support both 'limit' and 'page_size' parameter names
    effective_limit = page_size if page_size is not None else limit
    offset = (page - 1) * effective_limit

    # Build base query for filtering
    base_query = select(Investigation)
    if search:
        base_query = base_query.where(Investigation.initial_query.ilike(f"%{search}%"))

    # Get total count
    count_stmt = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Get paginated results
    stmt = base_query.order_by(desc(Investigation.created_at)).offset(offset).limit(effective_limit)
    result = await db.execute(stmt)
    investigations = result.scalars().all()

    return ListInvestigationsResponse(
        investigations=[
            InvestigationSummary(
                id=inv.id,
                initial_query=inv.initial_query,
                status=inv.status,
                model=inv.model,
                num_turns=inv.num_turns,
                duration_ms=inv.duration_ms,
                created_at=inv.created_at,
                completed_at=inv.completed_at,
            )
            for inv in investigations
        ],
        total=total,
        page=page,
        page_size=effective_limit,
    )


@router.get("/{investigation_id}", response_model=InvestigationDetail)
async def get_investigation(
    investigation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get full investigation details."""
    stmt = select(Investigation).where(Investigation.id == investigation_id)
    result = await db.execute(stmt)
    investigation = result.scalar_one_or_none()

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    return InvestigationDetail.model_validate(investigation)


@router.delete("/{investigation_id}")
async def delete_investigation(
    investigation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete an investigation."""
    stmt = select(Investigation).where(Investigation.id == investigation_id)
    result = await db.execute(stmt)
    investigation = result.scalar_one_or_none()

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    await db.delete(investigation)
    await db.commit()

    # Remove from agent cache
    remove_agent(investigation_id)

    return {"status": "deleted", "id": str(investigation_id)}


@router.get("/{investigation_id}/graph", response_model=GraphData)
async def get_investigation_graph(
    investigation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get graph data for an investigation."""
    stmt = select(Investigation).where(Investigation.id == investigation_id)
    result = await db.execute(stmt)
    investigation = result.scalar_one_or_none()

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    graph_service = GraphService()
    graph_data = graph_service.extract_from_investigation(
        investigation_id=investigation_id,
        result_text=investigation.full_response or "",
        subagent_results=investigation.subagent_results or [],
    )

    return graph_data
