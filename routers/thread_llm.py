from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from schemas import MultiThreadDumpAnalysis, ThreadDumpAnalysis, ThreadDumpRequest
from services import td_chain, td_multi_chain, td_multi_parser, td_parser


ROUTER_PREFIX = ""
ROUTER_TAGS = ["thread-llm"]

router = APIRouter(prefix=ROUTER_PREFIX, tags=ROUTER_TAGS)


@router.post("/v1/jvm/threaddump/analyze", response_model=ThreadDumpAnalysis)
def analyze_thread_dump(req: ThreadDumpRequest) -> ThreadDumpAnalysis:
    if len(req.dump) > 300_000:
        raise HTTPException(status_code=413, detail="Thread dump too large. Upload a file endpoint or trim.")
    return td_chain.invoke({
        "dump": req.dump,
        "app_hint": req.app_hint or "",
        "time_utc": req.time_utc or "",
        "top_n": req.top_n,
        "format_instructions": td_parser.get_format_instructions(),
    })


@router.post("/v1/jvm/threaddump/analyze-file", response_model=ThreadDumpAnalysis)
async def analyze_thread_dump_file(
    file: UploadFile = File(...),
    app_hint: str = Form(""),
    time_utc: str = Form(""),
    top_n: int = Form(15),
) -> ThreadDumpAnalysis:
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Thread dump file too large for this endpoint (2MB).")

    try:
        dump_text = content.decode("utf-8")
    except UnicodeDecodeError:
        dump_text = content.decode("latin-1")

    return td_chain.invoke({
        "dump": dump_text,
        "app_hint": app_hint or "",
        "time_utc": time_utc or "",
        "top_n": int(top_n),
        "format_instructions": td_parser.get_format_instructions(),
    })


@router.post("/v1/jvm/threaddump/analyze-multi-file", response_model=MultiThreadDumpAnalysis)
async def analyze_thread_dump_multi_file(
    files: List[UploadFile] = File(...),
    app_hint: str = Form(""),
    times_utc: str = Form(""),
    top_n: int = Form(15),
) -> MultiThreadDumpAnalysis:
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Upload at least 2 thread dump files.")

    parsed_times: List[str] = []
    if times_utc.strip():
        parsed_times = [t.strip() for t in times_utc.split(",") if t.strip()]

    dumps: List[str] = []
    for f in files:
        content = await f.read()
        if len(content) > 2 * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"Thread dump '{f.filename}' too large (2MB limit).")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
        dumps.append(text)

    dumps_block = "\n\n===== NEXT DUMP =====\n\n".join(
        [f"### dump[{idx}] file={files[idx].filename}\n{d}" for idx, d in enumerate(dumps)]
    )

    return td_multi_chain.invoke({
        "app_hint": app_hint or "",
        "times_utc": parsed_times,
        "top_n": int(top_n),
        "dump_count": len(dumps),
        "dumps_block": dumps_block,
        "format_instructions": td_multi_parser.get_format_instructions(),
    })
