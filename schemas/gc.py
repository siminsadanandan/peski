from typing import List, Optional

from pydantic import BaseModel, Field


class ContainerLimits(BaseModel):
    cpu: Optional[str] = None
    memory_mb: Optional[int] = None


class Evidence(BaseModel):
    tables: Optional[List[str]] = None
    notes: Optional[str] = None


class GcMetrics(BaseModel):
    jvm: str = Field(..., description="JVM distribution/version identifier.", examples=["OpenJDK 21"])
    gc: str = Field(..., description="Garbage collector name.", examples=["G1GC"])
    heap_mb: int = Field(..., description="Configured max heap size in MB.", examples=[4096])
    young_mb: Optional[int] = None
    pause_p95_ms: Optional[float] = None
    pause_p99_ms: Optional[float] = None
    throughput_util_pct: Optional[float] = None
    alloc_rate_mb_s: Optional[float] = None
    humongous_pct: Optional[float] = None
    to_space_exhaustions: Optional[int] = None
    mixed_gc_ratio: Optional[float] = None
    full_gc_count: Optional[int] = None
    cpu_cores: Optional[int] = None
    container_limits: Optional[ContainerLimits] = None
    flags: Optional[List[str]] = Field(default=None, description="Current JVM flag list.", examples=[["-XX:+UseG1GC"]])
    workload_hint: Optional[str] = Field(default=None, description="Short workload context for recommendations.")
    evidence: Optional[Evidence] = None


class Action(BaseModel):
    title: str
    severity: str
    steps: List[str]
    rationale: str


class Alternative(BaseModel):
    option: str
    when: Optional[str] = None
    notes: Optional[str] = None


class GcAdvice(BaseModel):
    summary: str
    actions: List[Action]
    flags_to_try: List[str]
    alternatives: Optional[List[Alternative]] = None
    rollback: Optional[str] = None
    notes: Optional[str] = None
