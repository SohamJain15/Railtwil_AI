from datetime import datetime
from uuid import uuid4
from sqlalchemy import DateTime, Integer, String, Float, Boolean, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
try:
    from geoalchemy2 import Geometry
except ImportError:
    Geometry = None

class Base(DeclarativeBase): pass
class SourceMixin:
    source_name: Mapped[str] = mapped_column(String(120), default="unknown")
    source_type: Mapped[str] = mapped_column(String(40), default="synthetic")
    source_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_quality: Mapped[float] = mapped_column(Float, default=1)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    scenario_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
class Station(SourceMixin, Base):
    __tablename__ = "stations"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    station_code: Mapped[str] = mapped_column(String(20)); name: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float); longitude: Mapped[float] = mapped_column(Float)
    zone: Mapped[str] = mapped_column(String(80)); station_type: Mapped[str] = mapped_column(String(40))
class GenericRecord(Base):
    __tablename__ = "simulation_records"
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: str(uuid4()))
    record_type: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
