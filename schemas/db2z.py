from typing import List, Optional

from pydantic import BaseModel, Field


class Db2zDdlValidationRequest(BaseModel):
    ddls: List[str] = Field(..., min_items=1)
    source: Optional[str] = Field(default="db2luw")
    include_rewritten: bool = Field(default=True)


class Db2zDdlIssue(BaseModel):
    rule_id: str
    severity: str
    message: str
    statement_index: int
    evidence: Optional[str] = None


class Db2zDdlSuggestion(BaseModel):
    title: str
    statement_index: int
    before: str
    after: str
    rationale: str


class Db2zDdlValidationResponse(BaseModel):
    summary: str
    issues: List[Db2zDdlIssue]
    suggestions: List[Db2zDdlSuggestion]
    rewritten_ddls: Optional[List[str]] = None
