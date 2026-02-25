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
    tda_raw: Dict[str, Any]
    normalized_text: str
    notes: Optional[str] = None


class TdaMcpAnalyzeMultiFileResponse(BaseModel):
    status: str
    saved_as: str
    input_files: List[str]
    tool_names: List[str]
    tda_raw: Dict[str, Any]
    normalized_text: str
    notes: Optional[str] = None


class TdaMcpAnalyzeTextRequest(BaseModel):
    dump: str = Field(..., description="Raw JVM thread dump text (single dump).")
    label: Optional[str] = Field(default="dump", description="Label used in injected boundary header.")
    run_virtual: bool = Field(default=True, description="Run analyze_virtual_threads tool.")
    wrap_if_missing_header: bool = Field(default=True, description="If dump lacks HotSpot header, wrap with one.")
    max_chars: int = Field(default=1_000_000, ge=10_000, le=2_000_000)
