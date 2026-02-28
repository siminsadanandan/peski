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

    additional_trace_options: Optional[str] = Field(
        default=None,
        description="Optional comma-separated diagnostics to capture per dump: ss,netstat,tcpdump.",
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
