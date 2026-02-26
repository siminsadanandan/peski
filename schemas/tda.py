from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TdaMcpTool(BaseModel):
    name: str
    description: Optional[str] = None
    inputSchema: Optional[Dict[str, Any]] = None


class TdaMcpAnalyzeFileResponse(BaseModel):
    status: str
    saved_as: str
    tool_names: List[str]
    tda_raw: Dict[str, Any] = Field(..., description="Raw output map returned by the TDA MCP pipeline.")
    normalized_text: str = Field(..., description="Human-readable normalized analysis text.")
    notes: Optional[str] = Field(default=None, description="Additional processing details.")


class TdaMcpAnalyzeMultiFileResponse(BaseModel):
    status: str
    saved_as: str
    input_files: List[str]
    tool_names: List[str]
    tda_raw: Dict[str, Any] = Field(..., description="Raw output map returned by the TDA MCP pipeline.")
    normalized_text: str = Field(..., description="Human-readable normalized analysis text.")
    notes: Optional[str] = Field(default=None, description="Additional processing details.")


class TdaMcpAnalyzeTextRequest(BaseModel):
    dump: str = Field(
        ...,
        description="Raw JVM thread dump text (single dump).",
        examples=['"main" #1 prio=5 os_prio=0 tid=0x00007f...'],
    )
    label: Optional[str] = Field(default="dump", description="Label used in injected boundary header.", examples=["capture-1"])
    run_virtual: bool = Field(default=True, description="Run analyze_virtual_threads tool.")
    wrap_if_missing_header: bool = Field(default=True, description="If dump lacks HotSpot header, wrap with one.")
    max_chars: int = Field(default=1_000_000, ge=10_000, le=2_000_000, description="Maximum allowed dump length.")
