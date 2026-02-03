"""Investigation-related Pydantic models."""
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class InvestigationStatus(str, Enum):
    """Investigation status enum."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class InvestigationCreate(BaseModel):
    """Request to create a new investigation."""
    query: str = Field(..., min_length=1, description="Investigation query")
    model: Optional[str] = Field(None, description="Model override")


class FollowUpRequest(BaseModel):
    """Request to send a follow-up query."""
    query: str = Field(..., min_length=1, description="Follow-up query")


class ToolExecution(BaseModel):
    """Record of a tool execution."""
    id: Optional[str] = None
    tool: Optional[str] = None
    name: Optional[str] = None  # Alternative field name for tool
    input: Optional[dict[str, Any]] = None
    output: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    status: str = "completed"

    @model_validator(mode='before')
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        """Normalize tool/name field and ensure id exists."""
        if isinstance(data, dict):
            # Use 'name' as 'tool' if 'tool' is not present
            if 'tool' not in data and 'name' in data:
                data['tool'] = data['name']
            # Generate id if not present
            if 'id' not in data:
                import uuid
                data['id'] = str(uuid.uuid4())
        return data


class SubAgentResultModel(BaseModel):
    """Result from a sub-agent."""
    agent_type: str
    analysis: str
    success: bool
    error: Optional[str] = None


class InvestigationResponse(BaseModel):
    """Response after creating an investigation."""
    id: UUID
    stream_url: str
    status: InvestigationStatus = InvestigationStatus.PENDING


class InvestigationSummary(BaseModel):
    """Summary for investigation list."""
    id: UUID
    initial_query: str
    status: InvestigationStatus
    model: str
    num_turns: Optional[int] = None
    duration_ms: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class ListInvestigationsResponse(BaseModel):
    """Paginated response for investigation list."""
    investigations: list[InvestigationSummary]
    total: int
    page: int
    page_size: int


class InvestigationDetail(BaseModel):
    """Full investigation details."""
    id: UUID
    session_id: Optional[str] = None
    initial_query: str
    status: InvestigationStatus
    full_response: Optional[str] = None
    tools_used: list[ToolExecution] = []
    subagent_results: list[SubAgentResultModel] = []
    model: str
    num_turns: Optional[int] = None
    duration_ms: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MessageModel(BaseModel):
    """Chat message model."""
    id: UUID
    role: str
    content: str
    tool_calls: Optional[list[dict]] = None
    created_at: datetime


# SSE Event Models

class SSEEventData(BaseModel):
    """Base class for SSE event data."""
    pass


class TextEventData(SSEEventData):
    """Text chunk event data."""
    content: str


class ToolStartEventData(SSEEventData):
    """Tool start event data."""
    id: str
    tool: str
    input: dict[str, Any]


class ToolEndEventData(SSEEventData):
    """Tool end event data."""
    id: str
    tool: str
    duration_ms: int
    output: Optional[str] = None


class SubAgentStartEventData(SSEEventData):
    """Sub-agent start event data."""
    agent_type: str


class SubAgentEndEventData(SSEEventData):
    """Sub-agent end event data."""
    agent_type: str
    analysis: str
    success: bool
    error: Optional[str] = None


class CompleteEventData(SSEEventData):
    """Investigation complete event data."""
    text: str
    session_id: Optional[str] = None
    duration_ms: Optional[int] = None
    num_turns: Optional[int] = None


class ErrorEventData(SSEEventData):
    """Error event data."""
    message: str
    code: str = "INVESTIGATION_ERROR"


class SSEEvent(BaseModel):
    """Server-Sent Event wrapper."""
    type: str
    data: dict[str, Any]
