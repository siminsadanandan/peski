from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ThreadDumpRequest(BaseModel):
    dump: str = Field(
        ...,
        description="Raw JVM thread dump text.",
        examples=['"main" #1 prio=5 os_prio=0 tid=0x00007f...'],
    )
    app_hint: Optional[str] = Field(default=None, description="Optional application name/context hint.")
    time_utc: Optional[str] = Field(default=None, description="Optional dump timestamp metadata (UTC).", examples=["2026-02-26T08:00:00Z"])
    top_n: int = Field(default=15, ge=5, le=50, description="How many top hotspots/groups to emphasize in output.")


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


class ThreadIssue(BaseModel):
    title: str
    severity: Literal["Critical", "High", "Medium", "Low"]
    confidence: Literal["High", "Medium", "Low"]
    affected_threads: Optional[int] = None
    potential_impact: str
    evidence: List[str] = Field(default_factory=list)
    likely_cause: Optional[str] = None


class ThreadRecommendationPlan(BaseModel):
    immediate_actions: List[str] = Field(default_factory=list)
    short_term_improvements: List[str] = Field(default_factory=list)
    long_term_changes: List[str] = Field(default_factory=list)


class CriticalThreadDetail(BaseModel):
    thread_name: str
    state: Optional[str] = None
    why_significant: str
    stack_snippet: Optional[str] = None
    related_threads: List[str] = Field(default_factory=list)
    investigate_areas: List[str] = Field(default_factory=list)


class ThreadDumpAnalysis(BaseModel):
    summary: str
    key_findings: List[str]
    thread_state_counts: Dict[str, int]
    top_thread_groups: List[ThreadGroup]
    hotspots: List[ThreadHotspot]
    recommended_actions: List[str]
    health_assessment: Optional[Literal["Healthy", "Degraded", "Critical"]] = None
    thread_state_percentages: Optional[Dict[str, float]] = None
    issues: List[ThreadIssue] = Field(default_factory=list)
    recommendation_plan: Optional[ThreadRecommendationPlan] = None
    critical_threads: List[CriticalThreadDetail] = Field(default_factory=list)
    system_context: List[str] = Field(default_factory=list)
    narrative_markdown: Optional[str] = None
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
    health_assessment: Optional[Literal["Healthy", "Degraded", "Critical"]] = None
    issues: List[ThreadIssue] = Field(default_factory=list)
    recommendation_plan: Optional[ThreadRecommendationPlan] = None
    critical_threads: List[CriticalThreadDetail] = Field(default_factory=list)
    system_context: List[str] = Field(default_factory=list)
    narrative_markdown: Optional[str] = None
    notes: Optional[str] = None
