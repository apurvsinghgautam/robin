"""SQLAlchemy ORM models."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Integer,
    JSON,
    ForeignKey,
    Enum,
    Boolean,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .database import Base
from ..models.investigation import InvestigationStatus


class Investigation(Base):
    """Investigation database model."""
    __tablename__ = "investigations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )
    initial_query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[InvestigationStatus] = mapped_column(
        Enum(InvestigationStatus),
        default=InvestigationStatus.PENDING,
    )

    # Results
    full_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tools_used: Mapped[list] = mapped_column(JSON, default=list)
    subagent_results: Mapped[list] = mapped_column(JSON, default=list)

    # Metadata
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    num_turns: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        back_populates="investigation",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["Report"]] = relationship(back_populates="investigation")
    graph_nodes: Mapped[list["GraphNodeDB"]] = relationship(
        back_populates="investigation",
        cascade="all, delete-orphan",
    )


class Message(Base):
    """Chat message model."""
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id"),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    investigation: Mapped["Investigation"] = relationship(back_populates="messages")


class Report(Base):
    """Report database model."""
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    investigation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id"),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sections: Mapped[list] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    investigation: Mapped[Optional["Investigation"]] = relationship(
        back_populates="reports"
    )


class GraphNodeDB(Base):
    """Graph node database model."""
    __tablename__ = "graph_nodes"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id"),
        nullable=False,
    )

    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[str] = mapped_column(String(20), default="medium")

    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    investigation: Mapped["Investigation"] = relationship(back_populates="graph_nodes")


class GraphEdgeDB(Base):
    """Graph edge database model."""
    __tablename__ = "graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_node_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("graph_nodes.id"),
        nullable=False,
    )
    target_node_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("graph_nodes.id"),
        nullable=False,
    )

    edge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    weight: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
