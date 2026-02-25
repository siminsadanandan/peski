from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ThreadDumpRequest(BaseModel):
    dump: str = Field(..., description="Raw JVM thread dump text")
    app_hint: Optional[str] = None
    time_utc: Optional[str] = Field(default=None, description="Metadata only")
    top_n: int = Field(default=15, ge=5, le=50)


class ThreadGroup(BaseModel):
    name: str
    count: int
    top_states: List[str]
    notes: Optional[str] = None


class ThreadHotspot(BaseModel):
    title: str
    severity: str
    evidence: List[str]
    impact: str
    likely_cause: str
    suggested_checks: List[str]


class ThreadDumpAnalysis(BaseModel):
    summary: str
    key_findings: List[str]
    thread_state_counts: Dict[str, int]
    top_thread_groups: List[ThreadGroup]
    hotspots: List[ThreadHotspot]
    recommended_actions: List[str]
    notes: Optional[str] = None


class MultiThreadDumpAnalysis(BaseModel):
    summary: str
    dump_count: int
    key_findings: List[str]
    persistent_threads: List[str]
    suspected_deadlocks: List[str]
    likely_cpu_spin_threads: List[str]
    likely_lock_contention: List[str]
    state_changes: Dict[str, List[str]]
    recommended_actions: List[str]
    notes: Optional[str] = None
