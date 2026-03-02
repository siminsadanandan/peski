from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TdaMcpActuatorCaptureRequest(BaseModel):
    actuator_url: str
    prom_url: Optional[str] = Field(default=None, description="Optional Prometheus metrics endpoint to snapshot alongside each dump.")
    dump_count: int = Field(default=3, ge=2, le=10)
    interval_sec: int = Field(default=5, ge=1, le=120)

    auth_mode: str = Field(default="none", description="none|basic|bearer|header")
    user: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    authorization_header: Optional[str] = None

    app_hint: Optional[str] = None
    alertname: Optional[str] = None
    instance: Optional[str] = None
    target_namespace: Optional[str] = Field(default=None, description="Target Kubernetes namespace (from alert metadata).")
    target_pod: Optional[str] = Field(default=None, description="Target Kubernetes pod name (from alert metadata).")
    target_app: Optional[str] = Field(default=None, description="Target app/workload name (from alert metadata).")
    target_process_name: Optional[str] = Field(default=None, description="Optional process name hint used by external diagnostics tooling.")

    additional_trace_options: Optional[str] = Field(
        default=None,
        description="Optional comma-separated diagnostics to capture per dump: ss,netstat,tcpdump.",
    )
    trace_executor_mode: Literal["local", "nsenter"] = Field(
        default="local",
        description="Trace command execution mode: local (container namespace) or nsenter (target namespace).",
    )
    trace_target_pid: Optional[int] = Field(
        default=None,
        ge=1,
        description="Host PID used for nsenter target when trace_executor_mode=nsenter.",
    )
    trace_target_netns_path: Optional[str] = Field(
        default=None,
        description="Explicit net namespace path for nsenter (for example /proc/<pid>/ns/net).",
    )
    trace_timeout_sec: int = Field(
        default=8,
        ge=1,
        le=120,
        description="Per-trace command timeout in seconds.",
    )
    trace_parallel: bool = Field(
        default=False,
        description="Run additional trace commands in parallel for each dump index.",
    )
    tcpdump_packet_count: int = Field(
        default=50,
        ge=1,
        le=10000,
        description="Packet count limit when tcpdump is selected.",
    )
    processing_mode: Literal["mcp", "llm", "both"] = Field(
        default="mcp",
        description="Post-capture processing mode: mcp, llm, or both.",
    )
    llm_execution_mode: Literal["inline", "background"] = Field(
        default="inline",
        description="LLM execution mode for processing_mode values that include llm. background returns early and runs LLM asynchronously.",
    )
    top_n: int = Field(default=15, ge=5, le=50)
    run_virtual: bool = True
    wrap_if_missing_header: bool = True


class GrafanaAlertWebhookRequest(BaseModel):
    message: Optional[str] = None
    commonLabels: Optional[Dict[str, str]] = None
    groupLabels: Optional[Dict[str, str]] = None
    alerts: Optional[List[Dict[str, Any]]] = None


class TdaMcpActuatorCaptureResponse(BaseModel):
    status: str
    saved_dir: str
    actuator_url: str
    files: List[str]
    converted_files: List[str]
    dump_count: int
    interval_sec: int
    tda_saved_as: str
    tda_tool_names: List[str]
    normalized_text: str
    tda_raw: Dict[str, Any]
    notes: Optional[str] = None


class ActuatorCaptureAnalyzeResponse(BaseModel):
    status: str
    saved_dir: str
    actuator_url: str
    files: List[str]
    converted_files: List[str]
    prom_files: List[str]
    trace_files: List[str]
    dump_count: int
    interval_sec: int
    processing_mode: Literal["mcp", "llm", "both"]

    mcp_saved_as: Optional[str] = None
    mcp_tool_names: Optional[List[str]] = None
    normalized_text: Optional[str] = None
    tda_raw: Optional[Dict[str, Any]] = None

    llm_analysis: Optional[Dict[str, Any]] = None
    llm_analysis_saved: bool = False
    llm_analysis_queued: bool = False
    llm_analysis_error: Optional[str] = None

    notes: Optional[str] = None


class ExternalActuatorCaptureRequest(BaseModel):
    actuator_url: str
    prom_url: Optional[str] = Field(default=None, description="Optional Prometheus metrics endpoint to snapshot alongside each dump.")
    dump_count: int = Field(default=3, ge=2, le=10)
    interval_sec: int = Field(default=5, ge=1, le=120)

    auth_mode: str = Field(default="none", description="none|basic|bearer|header")
    user: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    authorization_header: Optional[str] = None

    app_hint: Optional[str] = None
    alertname: Optional[str] = None
    instance: Optional[str] = None

    auto_analyze: bool = True
    top_n: int = Field(default=15, ge=5, le=50)


class ExternalActuatorCaptureResponse(BaseModel):
    status: str
    saved_dir: str
    actuator_url: str
    files: List[str]
    prom_files: List[str]
    dump_count: int
    interval_sec: int
    analysis_saved: bool = False
    analysis_error: Optional[str] = None
