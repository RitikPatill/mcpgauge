from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Criterion(BaseModel):
    name: str
    description: str
    required: bool = True


class Rubric(BaseModel):
    criteria: list[Criterion]


class Case(BaseModel):
    id: str
    prompt: str
    expected_tools: list[str] = []
    rubric: Rubric
    golden_output: str | None = None
    max_turns: int = Field(default=10, ge=1, le=50)


class Suite(BaseModel):
    name: str
    description: str = ""
    transport: Literal["stdio", "sse"] = "stdio"
    server_command: list[str] | None = None
    server_url: str | None = None
    cases: list[Case] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_transport_config(self) -> "Suite":
        if self.transport == "stdio" and not self.server_command:
            raise ValueError("server_command is required when transport is 'stdio'")
        if self.transport == "sse" and not self.server_url:
            raise ValueError("server_url is required when transport is 'sse'")
        return self
