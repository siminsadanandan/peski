import pathlib
import re
from datetime import datetime
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from schemas import (
    TdaMcpAnalyzeFileResponse,
    TdaMcpAnalyzeMultiFileResponse,
    TdaMcpAnalyzeTextRequest,
    TdaMcpTool,
)
from services import (
    TDA_DEFAULT_PIPELINE,
    TDA_TMP_DIR,
    _ensure_tda_prereqs,
    _inject_boundary,
    _normalize_bytes,
    _normalize_tda_pipeline_output,
    _normalize_text,
    _wrap_if_missing_hotspot_header,
    enforce_5mb,
    safe_name,
    tda_mcp_list_tools,
    tda_mcp_run_pipeline,
)


ROUTER_PREFIX = ""
ROUTER_TAGS = ["tda-mcp"]

router = APIRouter(prefix=ROUTER_PREFIX, tags=ROUTER_TAGS)


@router.get("/v1/tda/mcp/tools", response_model=List[TdaMcpTool])
async def tda_tools() -> List[TdaMcpTool]:
    _ensure_tda_prereqs()
    try:
        tools = await tda_mcp_list_tools()
        out: List[TdaMcpTool] = []
        for t in tools:
            if not isinstance(t, dict) or not t.get("name"):
                continue
            out.append(TdaMcpTool(
                name=str(t.get("name")),
                description=t.get("description"),
                inputSchema=t.get("inputSchema"),
            ))
        return out
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to list TDA MCP tools: {e}")


@router.post("/v1/jvm/threaddump/analyze-tda-mcp", response_model=TdaMcpAnalyzeFileResponse)
async def analyze_tda_mcp_text(req: TdaMcpAnalyzeTextRequest) -> TdaMcpAnalyzeFileResponse:
    _ensure_tda_prereqs()

    if not req.dump or not req.dump.strip():
        raise HTTPException(status_code=400, detail="dump is empty.")
    if len(req.dump) > req.max_chars:
        raise HTTPException(status_code=413, detail=f"dump too large. max_chars={req.max_chars}")

    tools = list(TDA_DEFAULT_PIPELINE)
    if not req.run_virtual and "analyze_virtual_threads" in tools:
        tools.remove("analyze_virtual_threads")

    raw = _normalize_text(req.dump)
    label = safe_name(req.label or "dump")
    combined = _wrap_if_missing_hotspot_header(raw, label=label, wrap=req.wrap_if_missing_header)

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_path = pathlib.Path(TDA_TMP_DIR) / f"{ts}_inline_{label}.log"
    out_path.write_text(combined, encoding="utf-8", errors="replace")

    try:
        out = await tda_mcp_run_pipeline(str(out_path), tools)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TDA MCP invocation failed: {e}")

    normalized = _normalize_tda_pipeline_output(out)

    return TdaMcpAnalyzeFileResponse(
        status="ok",
        saved_as=str(out_path),
        tool_names=out["tool_names"],
        tda_raw=out,
        normalized_text=normalized,
        notes=f"Inline dump saved and normalized. Ensured <EndOfDump>. parse_log then pipeline={tools}.",
    )


@router.post("/v1/jvm/threaddump/analyze-tda-mcp-log", response_model=TdaMcpAnalyzeFileResponse)
async def analyze_tda_mcp_log(
    path: str = Form(..., description="Absolute path to a log file inside this container/VM"),
    run_virtual: bool = Form(True),
) -> TdaMcpAnalyzeFileResponse:
    _ensure_tda_prereqs()

    tools = list(TDA_DEFAULT_PIPELINE)
    if not run_virtual and "analyze_virtual_threads" in tools:
        tools.remove("analyze_virtual_threads")

    try:
        out = await tda_mcp_run_pipeline(path, tools)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TDA MCP invocation failed: {e}")

    normalized = _normalize_tda_pipeline_output(out)

    return TdaMcpAnalyzeFileResponse(
        status="ok",
        saved_as=out["log_path"],
        tool_names=out["tool_names"],
        tda_raw=out,
        normalized_text=normalized,
        notes="parse_log(path) executed first; then pipeline tools.",
    )


@router.post("/v1/jvm/threaddump/analyze-tda-mcp-file", response_model=TdaMcpAnalyzeFileResponse)
async def analyze_tda_mcp_file(
    file: UploadFile = File(...),
    run_virtual: bool = Form(True),
) -> TdaMcpAnalyzeFileResponse:
    _ensure_tda_prereqs()

    content = await file.read()
    enforce_5mb(content)
    content = _normalize_bytes(content)

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_fn = safe_name(file.filename or "dump.log")
    out_path = pathlib.Path(TDA_TMP_DIR) / f"{ts}_{safe_fn}"
    out_path.write_bytes(content)

    tools = list(TDA_DEFAULT_PIPELINE)
    if not run_virtual and "analyze_virtual_threads" in tools:
        tools.remove("analyze_virtual_threads")

    try:
        out = await tda_mcp_run_pipeline(str(out_path), tools)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TDA MCP invocation failed: {e}")

    normalized = _normalize_tda_pipeline_output(out)

    return TdaMcpAnalyzeFileResponse(
        status="ok",
        saved_as=str(out_path),
        tool_names=out["tool_names"],
        tda_raw=out,
        normalized_text=normalized,
        notes=f"Uploaded '{file.filename}'. parse_log ran then pipeline={tools}.",
    )


@router.post("/v1/jvm/threaddump/analyze-tda-mcp-multi-file", response_model=TdaMcpAnalyzeMultiFileResponse)
async def analyze_tda_mcp_multi_file(
    files: List[UploadFile] = File(...),
    run_virtual: bool = Form(True),
) -> TdaMcpAnalyzeMultiFileResponse:
    _ensure_tda_prereqs()

    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Upload at least 2 thread dump files.")

    total = 0
    parts: List[str] = []
    input_names: List[str] = []

    for idx, f in enumerate(files):
        b = await f.read()
        total += len(b)
        if total > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Total upload too large. Max is ~5MB across all files.")
        b = _normalize_bytes(b)
        try:
            text = b.decode("utf-8")
        except UnicodeDecodeError:
            text = b.decode("latin-1")
        label = f"{idx+1}:{f.filename or 'dump'}"
        parts.append(_inject_boundary(text, label=label))
        input_names.append(f.filename or f"file{idx+1}")

    combined = "\n".join(parts)

    injected = len(re.findall(r"(?m)^\s*<EndOfDump>\s*$", combined))
    if injected < len(files):
        raise HTTPException(status_code=500, detail="Internal error: failed to inject <EndOfDump> boundaries.")

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_path = pathlib.Path(TDA_TMP_DIR) / f"{ts}_combined_{len(files)}.log"
    out_path.write_text(combined, encoding="utf-8", errors="replace")

    tools = list(TDA_DEFAULT_PIPELINE)
    if not run_virtual and "analyze_virtual_threads" in tools:
        tools.remove("analyze_virtual_threads")

    try:
        out = await tda_mcp_run_pipeline(str(out_path), tools)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TDA MCP invocation failed: {e}")

    normalized = _normalize_tda_pipeline_output(out)

    return TdaMcpAnalyzeMultiFileResponse(
        status="ok",
        saved_as=str(out_path),
        input_files=input_names,
        tool_names=out["tool_names"],
        tda_raw=out,
        normalized_text=normalized,
        notes=f"Concatenated {len(files)} files with <EndOfDump> boundaries (count={injected}). parse_log then pipeline={tools}.",
    )
