import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InteractionRecord(Base):
    __tablename__ = "interaction_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    simulation_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.id"), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    initiator_agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agent_records.id"), nullable=True)
    target_agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agent_records.id"), nullable=True)
    interaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
