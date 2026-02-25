import json
import pathlib
import re
import time
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Request

from schemas import (
    ExternalActuatorCaptureRequest,
    ExternalActuatorCaptureResponse,
    GrafanaAlertWebhookRequest,
    TdaMcpActuatorCaptureRequest,
    TdaMcpActuatorCaptureResponse,
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
    safe_name,
    tda_mcp_run_pipeline,
    td_multi_chain,
    td_multi_parser,
)


ROUTER_PREFIX = ""
ROUTER_TAGS = ["actuator"]

router = APIRouter(prefix=ROUTER_PREFIX, tags=ROUTER_TAGS)


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

    try:
        return TdaMcpActuatorCaptureRequest(**extracted)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid capture payload inside Grafana message: {e}")


@router.post("/v1/alerts/actuator/threaddump/capture", response_model=ExternalActuatorCaptureResponse)
def capture_external_actuator_threaddumps(req: ExternalActuatorCaptureRequest) -> ExternalActuatorCaptureResponse:
    pathlib.Path(CAPTURE_OUT_DIR).mkdir(parents=True, exist_ok=True)

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    alertname = safe_name(req.alertname or "alert")
    app_hint = safe_name(req.app_hint or "app")
    instance = safe_name(req.instance or "instance")
    run_dir = pathlib.Path(CAPTURE_OUT_DIR) / f"{alertname}_{app_hint}_{instance}_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    auth, headers = external_actuator_auth(req)

    files: List[str] = []
    for i in range(req.dump_count):
        try:
            body = fetch_actuator_threaddump(req.actuator_url, auth=auth, headers=headers, timeout_sec=CAPTURE_HTTP_TIMEOUT_SEC)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch actuator threaddump from {req.actuator_url}: {e}")

        fn = run_dir / f"dump{i+1}.json"
        fn.write_text(body, encoding="utf-8", errors="replace")
        files.append(str(fn))

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
            (run_dir / "analysis.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
            analysis_saved = True
        except Exception as e:
            analysis_error = str(e)
            (run_dir / "analysis_error.txt").write_text(analysis_error, encoding="utf-8")

    return ExternalActuatorCaptureResponse(
        status="captured",
        saved_dir=str(run_dir),
        actuator_url=req.actuator_url,
        files=[pathlib.Path(p).name for p in files],
        dump_count=req.dump_count,
        interval_sec=req.interval_sec,
        analysis_saved=analysis_saved,
        analysis_error=analysis_error,
    )


@router.post("/v1/alerts/actuator/threaddump/capture-tda-mcp", response_model=TdaMcpActuatorCaptureResponse)
async def capture_actuator_threaddumps_tda_mcp(request: Request) -> TdaMcpActuatorCaptureResponse:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    req = _normalize_tda_capture_request(payload)

    _ensure_tda_prereqs()
    pathlib.Path(CAPTURE_OUT_DIR).mkdir(parents=True, exist_ok=True)

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    alertname = safe_name(req.alertname or "alert")
    app_hint = safe_name(req.app_hint or "app")
    instance = safe_name(req.instance or "instance")
    run_dir = pathlib.Path(CAPTURE_OUT_DIR) / f"{alertname}_{app_hint}_{instance}_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    auth, headers = external_actuator_auth_mode(req.auth_mode, req.user, req.password, req.token, req.authorization_header)

    raw_files: List[str] = []
    converted_files: List[str] = []
    segments: List[str] = []

    for i in range(req.dump_count):
        try:
            body = fetch_actuator_threaddump(req.actuator_url, auth=auth, headers=headers, timeout_sec=CAPTURE_HTTP_TIMEOUT_SEC)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch actuator threaddump from {req.actuator_url}: {e}")

        raw_path = run_dir / f"dump{i+1}.json"
        raw_path.write_text(body, encoding="utf-8", errors="replace")
        raw_files.append(raw_path.name)

        extracted = _maybe_extract_actuator_dump_text(body)
        extracted = _normalize_text(extracted)
        seg = _wrap_if_missing_hotspot_header(
            extracted,
            label=f"{i+1}:{raw_path.name}",
            wrap=req.wrap_if_missing_header,
        )

        conv_path = run_dir / f"dump{i+1}.log"
        conv_path.write_text(seg, encoding="utf-8", errors="replace")
        converted_files.append(conv_path.name)

        segments.append(seg)

        if i < req.dump_count - 1:
            time.sleep(req.interval_sec)

    combined = "\n".join(segments)
    injected = len(re.findall(r"(?m)^\s*<EndOfDump>\s*$", combined))
    if injected < req.dump_count:
        raise HTTPException(status_code=500, detail=f"Internal error: expected >= {req.dump_count} <EndOfDump> markers, got {injected}")

    tda_in_path = pathlib.Path(TDA_TMP_DIR) / f"{ts}_actuator_{req.dump_count}.log"
    tda_in_path.write_text(combined, encoding="utf-8", errors="replace")

    tools = list(TDA_DEFAULT_PIPELINE)
    if not req.run_virtual and "analyze_virtual_threads" in tools:
        tools.remove("analyze_virtual_threads")

    try:
        out = await tda_mcp_run_pipeline(str(tda_in_path), tools)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TDA MCP invocation failed: {e}")

    normalized = _normalize_tda_pipeline_output(out)

    try:
        (run_dir / "tda_input_combined.log").write_text(combined, encoding="utf-8", errors="replace")
        (run_dir / "tda_analysis_raw.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        (run_dir / "tda_analysis.txt").write_text(normalized, encoding="utf-8")
    except Exception:
        pass

    return TdaMcpActuatorCaptureResponse(
        status="captured+analyzed",
        saved_dir=str(run_dir),
        actuator_url=req.actuator_url,
        files=raw_files,
        converted_files=converted_files,
        dump_count=req.dump_count,
        interval_sec=req.interval_sec,
        tda_saved_as=str(tda_in_path),
        tda_tool_names=out["tool_names"],
        normalized_text=normalized,
        tda_raw=out,
        notes=f"Fetched {req.dump_count} dump(s) from actuator, saved raw (.json) + converted (.log), injected <EndOfDump> (count={injected}). parse_log then pipeline={tools}.",
    )
