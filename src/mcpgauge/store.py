"""SQLModel table models and thin CRUD helpers for MCPGauge."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Session, SQLModel, create_engine, select, text


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    suite_name: str
    created_at: datetime = Field(default_factory=_now_utc)
    total_cases: int = 0
    passed_cases: int = 0


class CaseResult(SQLModel, table=True):
    __tablename__ = "case_results"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    run_id: str = Field(foreign_key="runs.id")
    case_id: str
    status: str  # "passed" | "failed" | "error"
    prompt: str
    final_response: str = ""
    error: Optional[str] = None


class ToolCall(SQLModel, table=True):
    __tablename__ = "tool_calls"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    case_result_id: str = Field(foreign_key="case_results.id")
    turn: int
    tool_name: str
    arguments_json: str
    result_json: str
    is_error: bool = False
    duration_ms: int = 0


class Judgment(SQLModel, table=True):
    __tablename__ = "judgments"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    case_result_id: str = Field(foreign_key="case_results.id")
    criterion_name: str
    passed: bool
    reasoning: str


def get_engine(db_path: str):
    """Return a SQLAlchemy engine for the given SQLite path (use ':memory:' for tests)."""
    if db_path == ":memory:":
        return create_engine(
            "sqlite://",
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )


def init_db(engine) -> None:
    """Create all tables if they don't exist."""
    SQLModel.metadata.create_all(engine)


def save_run(engine, run: Run) -> None:
    with Session(engine, expire_on_commit=False) as session:
        session.add(run)
        session.commit()


def save_case_result(engine, cr: CaseResult) -> None:
    with Session(engine, expire_on_commit=False) as session:
        session.add(cr)
        session.commit()


def save_tool_call(engine, tc: ToolCall) -> None:
    with Session(engine, expire_on_commit=False) as session:
        session.add(tc)
        session.commit()


def save_judgment(engine, j: Judgment) -> None:
    with Session(engine, expire_on_commit=False) as session:
        session.add(j)
        session.commit()


def list_runs(engine) -> list[Run]:
    """Return all runs ordered by created_at DESC."""
    with Session(engine) as session:
        statement = select(Run).order_by(Run.created_at.desc())
        return list(session.exec(statement).all())


def get_run(engine, run_id: str) -> Optional[Run]:
    with Session(engine) as session:
        return session.get(Run, run_id)


def get_case_results(engine, run_id: str) -> list[CaseResult]:
    with Session(engine) as session:
        statement = select(CaseResult).where(CaseResult.run_id == run_id)
        return list(session.exec(statement).all())


def get_tool_calls(engine, case_result_id: str) -> list[ToolCall]:
    with Session(engine) as session:
        statement = select(ToolCall).where(ToolCall.case_result_id == case_result_id)
        return list(session.exec(statement).all())


def get_judgments(engine, case_result_id: str) -> list[Judgment]:
    with Session(engine) as session:
        statement = select(Judgment).where(Judgment.case_result_id == case_result_id)
        return list(session.exec(statement).all())
