import json
import html
import pathlib
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from schemas import (
    ActuatorCaptureAnalyzeResponse,
    ExternalActuatorCaptureRequest,
    ExternalActuatorCaptureResponse,
    GrafanaAlertWebhookRequest,
    TdaMcpActuatorCaptureRequest,
)
from services import (
    CAPTURE_HTTP_TIMEOUT_SEC,
    CAPTURE_OUT_DIR,
    TDA_DEFAULT_PIPELINE,
    TDA_TMP_DIR,
    _ensure_tda_prereqs,
    _maybe_extract_actuator_dump_text,
    _normalize_tda_pipeline_output,
    _normalize_text,
    _wrap_if_missing_hotspot_header,
    external_actuator_auth,
    external_actuator_auth_mode,
    fetch_actuator_threaddump,
    fetch_http_text,
    run_trace_command,
    safe_name,
    tda_mcp_run_pipeline,
    td_multi_chain,
    td_multi_parser,
)


ROUTER_PREFIX = ""
ROUTER_TAGS = ["actuator"]

router = APIRouter(prefix=ROUTER_PREFIX, tags=ROUTER_TAGS)

_RUN_DIR_TS_RE = re.compile(r"(\d{8}T\d{6}Z)$")
_TRACE_OPTIONS = {"ss", "netstat", "tcpdump"}


def _safe_write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(content, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", errors="replace")


def _file_preview_text(path: pathlib.Path, max_chars: int = 50000) -> str:
    content = path.read_text(encoding="utf-8", errors="replace")
    if len(content) > max_chars:
        return content[:max_chars] + f"\n\n... [truncated, showing first {max_chars} chars]"
    return content


def _render_run_report_html(run_dir: pathlib.Path) -> str:
    files = sorted([p for p in run_dir.iterdir() if p.is_file()], key=lambda p: p.name)
    dump_files = [p for p in files if re.fullmatch(r"dump\d+\.json", p.name)]
    conv_files = [p for p in files if re.fullmatch(r"dump\d+\.log", p.name)]
    prom_files = [p for p in files if re.fullmatch(r"dump\d+\.prom\.txt", p.name)]
    trace_files = [p for p in files if re.fullmatch(r"dump\d+\.(ss|netstat|tcpdump)\.txt", p.name)]
    error_files = [p for p in files if p.name.endswith(".error.txt")]
    mcp_files = [p for p in files if p.name in {"tda_input_combined.log", "tda_analysis_raw.json", "tda_analysis.txt"}]
    llm_files = [p for p in files if p.name in {"analysis_llm.json", "analysis_llm_error.txt", "analysis_llm_payload.txt"}]

    def _section(title: str, items: List[pathlib.Path]) -> str:
        title_html = html.escape(title)
        count = len(items)
        if not items:
            return (
                "<details class='sec'>"
                f"<summary><span class='caret'></span><span>{title_html} (0)</span></summary>"
                "<div class='sec-body'><p>No files.</p></div>"
                "</details>"
            )
        body = []
        for p in items:
            preview = html.escape(_file_preview_text(p))
            body.append(
                "<article>"
                f"<h3>{html.escape(p.name)}</h3>"
                f"<p class='meta'>size={p.stat().st_size} bytes</p>"
                f"<pre>{preview}</pre>"
                "</article>"
            )
        return (
            "<details class='sec'>"
            f"<summary><span class='caret'></span><span>{title_html} ({count})</span></summary>"
            f"<div class='sec-body'>{''.join(body)}</div>"
            "</details>"
        )

    generated_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    all_files = "".join(f"<li>{html.escape(p.name)}</li>" for p in files) or "<li>No files found</li>"
    return (
        "<!doctype html>"
        "<html><head><meta charset='utf-8'/>"
        f"<title>Performance Incident Diagnostics Bundle - {html.escape(run_dir.name)}</title>"
        "<style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f6f8fb;color:#0f172a;"
        "margin:0;padding:24px;line-height:1.4}"
        ".wrap{max-width:1200px;margin:0 auto}"
        "h1{margin:0 0 8px;font-size:28px}.muted{color:#475569;margin:0 0 20px}"
        ".sec{background:#fff;border:1px solid #dbe3ee;border-radius:10px;padding:0;margin:0 0 14px;overflow:hidden}"
        ".sec>summary{list-style:none;cursor:pointer;padding:12px 16px;font-weight:600;font-size:17px;"
        "display:flex;align-items:center;gap:8px;background:#f8fafc;border-bottom:1px solid #e2e8f0}"
        ".sec>summary::-webkit-details-marker{display:none}"
        ".caret{display:inline-block;width:0;height:0;border-top:6px solid transparent;border-bottom:6px solid transparent;"
        "border-left:8px solid #334155;transition:transform .15s ease}"
        ".sec[open] .caret{transform:rotate(90deg)}"
        ".sec-body{padding:12px 16px}"
        "h3{margin:10px 0 6px;font-size:15px}"
        "pre{white-space:pre-wrap;word-break:break-word;background:#f8fafc;border:1px solid #e2e8f0;"
        "padding:10px;border-radius:8px;max-height:340px;overflow:auto}"
        ".meta{color:#334155;font-size:12px;margin:0 0 6px}"
        "ul{margin:8px 0 0 18px}"
        "</style></head><body><div class='wrap'>"
        f"<h1>Performance Incident Diagnostics Bundle: {html.escape(run_dir.name)}</h1>"
        f"<p class='muted'>Directory: {html.escape(str(run_dir))} | Generated: {generated_utc}</p>"
        "<details class='sec' open><summary><span class='caret'></span><span>File Index</span></summary><div class='sec-body'><ul>"
        f"{all_files}"
        "</ul></div></details>"
        f"{_section('Thread Dump Raw Files', dump_files)}"
        f"{_section('Thread Dump Converted Files', conv_files)}"
        f"{_section('Prometheus Snapshots', prom_files)}"
        f"{_section('Additional Trace Outputs', trace_files)}"
        f"{_section('MCP Outputs', mcp_files)}"
        f"{_section('LLM Outputs', llm_files)}"
        f"{_section('Error Files', error_files)}"
        "</div></body></html>"
    )


def _run_llm_analysis_and_persist(
    run_dir: pathlib.Path,
    llm_dumps: List[str],
    app_hint: str,
    top_n: int,
    llm_max_chars: Optional[int] = None,
) -> tuple[Optional[dict], bool, Optional[str]]:
    try:
        dumps_block = "\n\n===== NEXT DUMP =====\n\n".join([f"### dump[{i}]\n{d}" for i, d in enumerate(llm_dumps)])
        if isinstance(llm_max_chars, int) and llm_max_chars > 0 and len(dumps_block) > llm_max_chars:
            dumps_block = dumps_block[:llm_max_chars]
        _safe_write_text(run_dir / "analysis_llm_payload.txt", dumps_block)
        llm_out = td_multi_chain.invoke({
            "app_hint": app_hint,
            "times_utc": [],
            "top_n": int(top_n),
            "dump_count": len(llm_dumps),
            "dumps_block": dumps_block,
            "format_instructions": td_multi_parser.get_format_instructions(),
        })
        if hasattr(llm_out, "model_dump"):
            llm_analysis = llm_out.model_dump()
        elif hasattr(llm_out, "dict"):
            llm_analysis = llm_out.dict()
        else:
            llm_analysis = llm_out
        _safe_write_text(run_dir / "analysis_llm.json", json.dumps(llm_analysis, indent=2))
        return llm_analysis, True, None
    except Exception as e:
        llm_analysis_error = str(e)
        _safe_write_text(run_dir / "analysis_llm_error.txt", llm_analysis_error)
        return None, False, llm_analysis_error


def _parse_trace_options(raw: str) -> List[str]:
    if not raw:
        return []
    out: List[str] = []
    for part in raw.split(","):
        opt = part.strip().lower()
        if not opt:
            continue
        if opt not in _TRACE_OPTIONS:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported additional_trace_options value '{opt}'. Supported: ss,netstat,tcpdump",
            )
        if opt not in out:
            out.append(opt)
    return out


def _collect_trace_outputs_for_dump(
    run_dir: pathlib.Path,
    dump_index: int,
    trace_options: List[str],
    trace_timeout_sec: int,
    tcpdump_packet_count: int,
    trace_parallel: bool,
    trace_executor_mode: str,
    trace_target_pid: Optional[int],
    trace_target_netns_path: Optional[str],
    target_process_name: Optional[str],
    target_namespace: Optional[str],
    target_pod: Optional[str],
    target_app: Optional[str],
) -> List[str]:
    out_files: List[str] = []
    if not trace_options:
        return out_files

    def _run_one(opt: str) -> str:
        trace_path = run_dir / f"dump{dump_index}.{opt}.txt"
        err_path = run_dir / f"dump{dump_index}.{opt}.error.txt"
        if trace_path.exists():
            return trace_path.name
        if err_path.exists():
            return err_path.name
        try:
            trace_out = run_trace_command(
                opt,
                timeout_sec=trace_timeout_sec,
                tcpdump_packet_count=tcpdump_packet_count,
                executor_mode=trace_executor_mode,
                target_pid=trace_target_pid,
                target_netns_path=trace_target_netns_path,
                target_process_name=target_process_name,
                target_namespace=target_namespace,
                target_pod=target_pod,
                target_app=target_app,
            )
            _safe_write_text(trace_path, trace_out)
            return trace_path.name
        except Exception as e:
            _safe_write_text(err_path, str(e))
            return err_path.name

    if trace_parallel and len(trace_options) > 1:
        with ThreadPoolExecutor(max_workers=min(len(trace_options), 4)) as pool:
            futures = [pool.submit(_run_one, opt) for opt in trace_options]
            for fut in as_completed(futures):
                out_files.append(fut.result())
    else:
        for opt in trace_options:
            out_files.append(_run_one(opt))
    return out_files


def _pick_or_create_run_dir(base_dir: pathlib.Path, prefix: str, dump_count: int) -> pathlib.Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    candidates: List[pathlib.Path] = []
    for p in base_dir.glob(f"{prefix}_*"):
        if p.is_dir() and _RUN_DIR_TS_RE.search(p.name):
            candidates.append(p)

    candidates.sort(reverse=True)
    for p in candidates:
        if len(list(p.glob("dump*.json"))) < dump_count:
            return p

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = base_dir / f"{prefix}_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _labels_from_grafana(grafana: GrafanaAlertWebhookRequest) -> dict:
    labels: dict = {}
    if isinstance(grafana.groupLabels, dict):
        labels.update(grafana.groupLabels)
    if isinstance(grafana.commonLabels, dict):
        labels.update(grafana.commonLabels)
    if isinstance(grafana.alerts, list) and grafana.alerts:
        first = grafana.alerts[0]
        if isinstance(first, dict) and isinstance(first.get("labels"), dict):
            labels.update(first["labels"])
    return labels


def _first_label(labels: dict, keys: List[str]) -> str:
    for k in keys:
        v = labels.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _normalize_tda_capture_request(payload: dict) -> TdaMcpActuatorCaptureRequest:
    direct = payload
    parse_error = None

    try:
        return TdaMcpActuatorCaptureRequest(**direct)
    except Exception as e:
        parse_error = str(e)

    grafana = GrafanaAlertWebhookRequest(**payload)
    message_payload = grafana.message
    if not message_payload:
        raise HTTPException(
            status_code=422,
            detail=(
                "Payload must either match TdaMcpActuatorCaptureRequest directly or include a JSON string in 'message'. "
                f"Direct parse error: {parse_error}"
            ),
        )

    try:
        extracted = json.loads(message_payload)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Grafana message is not valid JSON: {e}")

    if not isinstance(extracted, dict):
        raise HTTPException(status_code=422, detail="Grafana message JSON must be an object.")

    labels = _labels_from_grafana(grafana)
    if labels.get("alertname") and not extracted.get("alertname"):
        extracted["alertname"] = labels["alertname"]
    if labels.get("instance") and not extracted.get("instance"):
        extracted["instance"] = labels["instance"]
    if not extracted.get("target_namespace"):
        ns = _first_label(labels, ["namespace", "kubernetes_namespace", "k8s_namespace"])
        if ns:
            extracted["target_namespace"] = ns
    if not extracted.get("target_pod"):
        pod = _first_label(labels, ["pod", "pod_name", "kubernetes_pod_name"])
        if pod:
            extracted["target_pod"] = pod
    if not extracted.get("target_app"):
        app = _first_label(labels, ["app", "app_kubernetes_io_name", "k8s_app", "workload"])
        if app:
            extracted["target_app"] = app

    try:
        return TdaMcpActuatorCaptureRequest(**extracted)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid capture payload inside Grafana message: {e}")


@router.post(
    "/v1/alerts/actuator/threaddump/capture",
    response_model=ExternalActuatorCaptureResponse,
    summary="Capture thread dumps from actuator",
    description="Fetch multiple thread dumps from an actuator endpoint, store raw dumps, and optionally run LLM analysis.",
    response_description="Capture metadata including saved files and optional analysis status.",
    responses={
        200: {"description": "Thread dumps captured successfully."},
        422: {"description": "Validation error in the request payload."},
        502: {"description": "Failed to fetch dumps from actuator or downstream dependency failed."},
    },
)
def capture_external_actuator_threaddumps(req: ExternalActuatorCaptureRequest) -> ExternalActuatorCaptureResponse:
    base_dir = pathlib.Path(CAPTURE_OUT_DIR)
    alertname = safe_name(req.alertname or "alert")
    app_hint = safe_name(req.app_hint or "app")
    instance = safe_name(req.instance or "instance")
    run_dir = _pick_or_create_run_dir(base_dir, f"{alertname}_{app_hint}_{instance}", req.dump_count)

    auth, headers = external_actuator_auth(req)

    files: List[str] = []
    prom_files: List[str] = []
    for i in range(req.dump_count):
        fn = run_dir / f"dump{i+1}.json"
        if not fn.exists():
            try:
                body = fetch_actuator_threaddump(req.actuator_url, auth=auth, headers=headers, timeout_sec=CAPTURE_HTTP_TIMEOUT_SEC)
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Failed to fetch actuator threaddump from {req.actuator_url}: {e}")
            _safe_write_text(fn, body)
        files.append(str(fn))

        if req.prom_url:
            prom_path = run_dir / f"dump{i+1}.prom.txt"
            if not prom_path.exists():
                try:
                    prom_body = fetch_http_text(req.prom_url, auth=auth, headers=headers, timeout_sec=CAPTURE_HTTP_TIMEOUT_SEC)
                except Exception as e:
                    raise HTTPException(status_code=502, detail=f"Failed to fetch Prometheus metrics from {req.prom_url}: {e}")
                _safe_write_text(prom_path, prom_body)
            prom_files.append(str(prom_path))

        if i < req.dump_count - 1:
            time.sleep(req.interval_sec)

    analysis_saved = False
    analysis_error = None
    if req.auto_analyze:
        try:
            dumps = [pathlib.Path(p).read_text(encoding="utf-8", errors="replace") for p in files]
            dumps_block = "\n\n===== NEXT DUMP =====\n\n".join([f"### dump[{i}]\n{d}" for i, d in enumerate(dumps)])
            out = td_multi_chain.invoke({
                "app_hint": req.app_hint or "",
                "times_utc": [],
                "top_n": int(req.top_n),
                "dump_count": len(dumps),
                "dumps_block": dumps_block,
                "format_instructions": td_multi_parser.get_format_instructions(),
            })
            _safe_write_text(run_dir / "analysis.json", json.dumps(out, indent=2))
            analysis_saved = True
        except Exception as e:
            analysis_error = str(e)
            _safe_write_text(run_dir / "analysis_error.txt", analysis_error)

    return ExternalActuatorCaptureResponse(
        status="captured",
        saved_dir=str(run_dir),
        actuator_url=req.actuator_url,
        files=[pathlib.Path(p).name for p in files],
        prom_files=[pathlib.Path(p).name for p in prom_files],
        dump_count=req.dump_count,
        interval_sec=req.interval_sec,
        analysis_saved=analysis_saved,
        analysis_error=analysis_error,
    )


@router.post(
    "/v1/alerts/actuator/threaddump/capture-analyze",
    response_model=ActuatorCaptureAnalyzeResponse,
    summary="Capture actuator dumps and analyze",
    description=(
        "Accepts either a direct capture payload or a Grafana webhook payload containing JSON in `message`, "
        "captures actuator dumps, then processes them with MCP, LLM, or both based on processing_mode."
    ),
    response_description="Capture metadata with optional MCP and/or LLM analysis outputs.",
    responses={
        200: {"description": "Thread dumps captured and processed successfully."},
        202: {"description": "Thread dumps captured; LLM analysis accepted for background processing."},
        422: {"description": "Request payload is invalid or cannot be normalized."},
        500: {"description": "Internal boundary marker guard failed while composing input."},
        502: {"description": "Actuator fetch or downstream dependency failed."},
    },
)
async def capture_actuator_threaddumps_tda_mcp(
    request: Request,
    background_tasks: BackgroundTasks,
    response: Response,
) -> ActuatorCaptureAnalyzeResponse:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    req = _normalize_tda_capture_request(payload)

    _ensure_tda_prereqs()
    base_dir = pathlib.Path(CAPTURE_OUT_DIR)
    alertname = safe_name(req.alertname or "alert")
    app_hint = safe_name(req.app_hint or "app")
    instance = safe_name(req.instance or "instance")
    run_dir = _pick_or_create_run_dir(base_dir, f"{alertname}_{app_hint}_{instance}", req.dump_count)

    auth, headers = external_actuator_auth_mode(req.auth_mode, req.user, req.password, req.token, req.authorization_header)

    processing_mode = req.processing_mode
    run_mcp = processing_mode in {"mcp", "both"}
    run_llm = processing_mode in {"llm", "both"}
    llm_execution_mode = req.llm_execution_mode
    llm_run_background = run_llm and llm_execution_mode == "background"
    trace_options = _parse_trace_options(req.additional_trace_options or "")

    raw_files: List[str] = []
    converted_files: List[str] = []
    prom_files: List[str] = []
    trace_files: List[str] = []
    segments: List[str] = []
    llm_dumps: List[str] = []

    for i in range(req.dump_count):
        raw_path = run_dir / f"dump{i+1}.json"
        conv_path = run_dir / f"dump{i+1}.log"

        if raw_path.exists():
            body = raw_path.read_text(encoding="utf-8", errors="replace")
        elif conv_path.exists():
            body = conv_path.read_text(encoding="utf-8", errors="replace")
            _safe_write_text(raw_path, body)
        else:
            try:
                body = fetch_actuator_threaddump(req.actuator_url, auth=auth, headers=headers, timeout_sec=CAPTURE_HTTP_TIMEOUT_SEC)
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Failed to fetch actuator threaddump from {req.actuator_url}: {e}")
            _safe_write_text(raw_path, body)
        raw_files.append(raw_path.name)

        if run_llm:
            llm_dumps.append(body)

        if req.prom_url:
            prom_path = run_dir / f"dump{i+1}.prom.txt"
            if not prom_path.exists():
                try:
                    prom_body = fetch_http_text(req.prom_url, auth=auth, headers=headers, timeout_sec=CAPTURE_HTTP_TIMEOUT_SEC)
                except Exception as e:
                    raise HTTPException(status_code=502, detail=f"Failed to fetch Prometheus metrics from {req.prom_url}: {e}")
                _safe_write_text(prom_path, prom_body)
            prom_files.append(prom_path.name)

        trace_files.extend(
            _collect_trace_outputs_for_dump(
                run_dir=run_dir,
                dump_index=i + 1,
                trace_options=trace_options,
                trace_timeout_sec=req.trace_timeout_sec,
                tcpdump_packet_count=req.tcpdump_packet_count,
                trace_parallel=req.trace_parallel,
                trace_executor_mode=req.trace_executor_mode,
                trace_target_pid=req.trace_target_pid,
                trace_target_netns_path=req.trace_target_netns_path,
                target_process_name=req.target_process_name,
                target_namespace=req.target_namespace,
                target_pod=req.target_pod,
                target_app=req.target_app,
            )
        )

        if run_mcp:
            if conv_path.exists():
                seg = conv_path.read_text(encoding="utf-8", errors="replace")
            else:
                extracted = _maybe_extract_actuator_dump_text(body)
                extracted = _normalize_text(extracted)
                seg = _wrap_if_missing_hotspot_header(
                    extracted,
                    label=f"{i+1}:{raw_path.name}",
                    wrap=req.wrap_if_missing_header,
                )
                _safe_write_text(conv_path, seg)

            converted_files.append(conv_path.name)
            segments.append(seg)

        if i < req.dump_count - 1:
            time.sleep(req.interval_sec)

    mcp_saved_as = None
    mcp_tool_names = None
    normalized = None
    tda_raw = None
    llm_analysis = None
    llm_analysis_saved = False
    llm_analysis_queued = False
    llm_analysis_error = None
    notes: List[str] = []

    if run_mcp:
        combined = "\n".join(segments)
        injected = len(re.findall(r"(?m)^\s*<EndOfDump>\s*$", combined))
        if injected < req.dump_count:
            raise HTTPException(status_code=500, detail=f"Internal error: expected >= {req.dump_count} <EndOfDump> markers, got {injected}")

        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        tda_in_path = pathlib.Path(TDA_TMP_DIR) / f"{ts}_actuator_{req.dump_count}.log"
        _safe_write_text(tda_in_path, combined)
        mcp_saved_as = str(tda_in_path)

        tools = list(TDA_DEFAULT_PIPELINE)
        if not req.run_virtual and "analyze_virtual_threads" in tools:
            tools.remove("analyze_virtual_threads")

        try:
            tda_raw = await tda_mcp_run_pipeline(str(tda_in_path), tools)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"TDA MCP invocation failed: {e}")

        normalized = _normalize_tda_pipeline_output(tda_raw)
        mcp_tool_names = tda_raw.get("tool_names")
        notes.append(
            f"MCP pipeline completed for {req.dump_count} dump(s); tools={tools}."
        )
        try:
            _safe_write_text(run_dir / "tda_input_combined.log", combined)
            _safe_write_text(run_dir / "tda_analysis_raw.json", json.dumps(tda_raw, indent=2))
            _safe_write_text(run_dir / "tda_analysis.txt", normalized)
        except Exception:
            pass

    if run_llm:
        if llm_run_background:
            background_tasks.add_task(
                _run_llm_analysis_and_persist,
                run_dir=run_dir,
                llm_dumps=llm_dumps,
                app_hint=req.app_hint or "",
                top_n=int(req.top_n),
                llm_max_chars=req.llm_max_chars,
            )
            llm_analysis_queued = True
            notes.append("LLM analysis queued in background.")
            response.status_code = 202
        else:
            llm_analysis, llm_analysis_saved, llm_analysis_error = _run_llm_analysis_and_persist(
                run_dir=run_dir,
                llm_dumps=llm_dumps,
                app_hint=req.app_hint or "",
                top_n=int(req.top_n),
                llm_max_chars=req.llm_max_chars,
            )
            if llm_analysis_saved:
                notes.append("LLM multi-dump analysis completed.")
            else:
                notes.append("LLM analysis failed.")

    return ActuatorCaptureAnalyzeResponse(
        status="captured+processing" if llm_analysis_queued else "captured+processed",
        saved_dir=str(run_dir),
        actuator_url=req.actuator_url,
        files=raw_files,
        converted_files=converted_files,
        prom_files=prom_files,
        trace_files=trace_files,
        dump_count=req.dump_count,
        interval_sec=req.interval_sec,
        processing_mode=processing_mode,
        mcp_saved_as=mcp_saved_as,
        mcp_tool_names=mcp_tool_names,
        normalized_text=normalized,
        tda_raw=tda_raw,
        llm_analysis=llm_analysis,
        llm_analysis_saved=llm_analysis_saved,
        llm_analysis_queued=llm_analysis_queued,
        llm_analysis_error=llm_analysis_error,
        notes=" ".join(notes) if notes else None,
    )


@router.get(
    "/v1/alerts/actuator/runs/{run_id}/report",
    response_class=HTMLResponse,
    summary="Render run report as HTML",
    description="Loads one capture run directory from local storage and renders an HTML report with all run artifacts.",
    response_description="HTML report for a single run directory.",
    responses={
        200: {"description": "Run report generated successfully."},
        404: {"description": "Run directory not found."},
        422: {"description": "Invalid run id."},
    },
)
def get_actuator_run_report(run_id: str) -> HTMLResponse:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id):
        raise HTTPException(status_code=422, detail="Invalid run_id format.")

    base_dir = pathlib.Path(CAPTURE_OUT_DIR).resolve()
    run_dir = (base_dir / run_id).resolve()
    if run_dir.parent != base_dir:
        raise HTTPException(status_code=422, detail="Invalid run_id path.")
    if not run_dir.exists() or not run_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    return HTMLResponse(content=_render_run_report_html(run_dir))
