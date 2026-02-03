"""Report API endpoints."""
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...db.models import Report, Investigation
from ...services.report_service import ReportService
from pydantic import BaseModel


router = APIRouter(prefix="/reports", tags=["reports"])


class ReportCreate(BaseModel):
    """Request to create a report."""
    investigation_id: UUID
    title: str


class ReportUpdate(BaseModel):
    """Request to update a report."""
    title: Optional[str] = None
    summary: Optional[str] = None
    sections: Optional[list[dict]] = None


class ReportResponse(BaseModel):
    """Report response model."""
    id: UUID
    investigation_id: Optional[UUID]
    title: str
    summary: Optional[str]
    sections: list[dict]

    class Config:
        from_attributes = True


@router.post("", response_model=ReportResponse)
async def create_report(
    request: ReportCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a report from an investigation."""
    # Get investigation
    stmt = select(Investigation).where(Investigation.id == request.investigation_id)
    result = await db.execute(stmt)
    investigation = result.scalar_one_or_none()

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    # Generate report structure
    report_service = ReportService()
    report_data = report_service.generate_from_investigation(
        investigation_id=investigation.id,
        title=request.title,
        query=investigation.initial_query,
        response=investigation.full_response or "",
        tools_used=investigation.tools_used or [],
        subagent_results=investigation.subagent_results or [],
    )

    # Create database record
    report = Report(
        id=uuid4(),
        investigation_id=investigation.id,
        title=report_data["title"],
        summary=report_data["summary"],
        sections=report_data["sections"],
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return ReportResponse.model_validate(report)


@router.get("", response_model=list[ReportResponse])
async def list_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List reports with pagination."""
    offset = (page - 1) * limit

    stmt = select(Report).order_by(desc(Report.created_at))

    if search:
        stmt = stmt.where(Report.title.ilike(f"%{search}%"))

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    reports = result.scalars().all()

    return [ReportResponse.model_validate(r) for r in reports]


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a report by ID."""
    stmt = select(Report).where(Report.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportResponse.model_validate(report)


@router.put("/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: UUID,
    request: ReportUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a report."""
    stmt = select(Report).where(Report.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if request.title is not None:
        report.title = request.title
    if request.summary is not None:
        report.summary = request.summary
    if request.sections is not None:
        report.sections = request.sections

    await db.commit()
    await db.refresh(report)

    return ReportResponse.model_validate(report)


@router.delete("/{report_id}")
async def delete_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a report."""
    stmt = select(Report).where(Report.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    await db.delete(report)
    await db.commit()

    return {"status": "deleted", "id": str(report_id)}


@router.get("/{report_id}/export")
async def export_report(
    report_id: UUID,
    format: str = Query("md", regex="^(md|html|json)$"),
    db: AsyncSession = Depends(get_db),
):
    """Export a report in the specified format."""
    stmt = select(Report).where(Report.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report_service = ReportService()
    report_data = {
        "title": report.title,
        "summary": report.summary,
        "sections": report.sections,
        "metadata": {
            "investigation_id": str(report.investigation_id) if report.investigation_id else None,
            "generated_at": report.created_at.isoformat() if report.created_at else None,
        },
    }

    if format == "md":
        content = report_service.export_markdown(report_data)
        return Response(
            content=content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="{report.title}.md"'
            },
        )
    elif format == "html":
        content = report_service.export_html(report_data)
        return Response(
            content=content,
            media_type="text/html",
            headers={
                "Content-Disposition": f'attachment; filename="{report.title}.html"'
            },
        )
    elif format == "json":
        return report_service.export_json(report_data)
