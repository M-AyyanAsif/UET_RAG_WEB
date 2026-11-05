import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def newid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=newid)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=newid)
    knowledge_base_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_bases.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=newid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(36), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=newid)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_bases.id"))
    title: Mapped[str] = mapped_column(String(180), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=newid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    sources_json: Mapped[str] = mapped_column(Text, default="[]")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class QueryMetric(Base):
    __tablename__ = "query_metrics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=newid)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(36), index=True)
    latency_ms: Mapped[int] = mapped_column(Integer)
    retrieved_count: Mapped[int] = mapped_column(Integer)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=newid)
    actor_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(90))
    detail: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
