from typing import List

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile

from schemas import MultiThreadDumpAnalysis, ThreadDumpAnalysis, ThreadDumpRequest
from services import td_chain, td_multi_chain, td_multi_parser, td_parser


ROUTER_PREFIX = ""
ROUTER_TAGS = ["thread-llm"]

router = APIRouter(prefix=ROUTER_PREFIX, tags=ROUTER_TAGS)


@router.post(
    "/v1/jvm/threaddump/analyze",
    response_model=ThreadDumpAnalysis,
    summary="Analyze a single thread dump",
    description="Analyze one raw JVM thread dump from JSON input and return structured findings and recommendations.",
    response_description="Structured analysis for a single thread dump.",
    responses={
        200: {"description": "Thread dump analyzed successfully."},
        413: {"description": "Thread dump text exceeds endpoint limit."},
        422: {"description": "Validation error in the request payload."},
        502: {"description": "Downstream analysis dependency failed."},
    },
)
def analyze_thread_dump(
    req: ThreadDumpRequest = Body(..., description="Single thread dump analysis request."),
) -> ThreadDumpAnalysis:
    if len(req.dump) > 300_000:
        raise HTTPException(status_code=413, detail="Thread dump too large. Upload a file endpoint or trim.")
    return td_chain.invoke({
        "dump": req.dump,
        "app_hint": req.app_hint or "",
        "time_utc": req.time_utc or "",
        "top_n": req.top_n,
        "format_instructions": td_parser.get_format_instructions(),
    })


@router.post(
    "/v1/jvm/threaddump/analyze-file",
    response_model=ThreadDumpAnalysis,
    summary="Analyze a single thread dump file",
    description="Upload one thread dump file and return structured analysis from its decoded content.",
    response_description="Structured analysis for the uploaded thread dump.",
    responses={
        200: {"description": "Thread dump file analyzed successfully."},
        413: {"description": "Uploaded file exceeds endpoint size limit."},
        422: {"description": "Validation error in multipart/form-data parameters."},
        502: {"description": "Downstream analysis dependency failed."},
    },
)
async def analyze_thread_dump_file(
    file: UploadFile = File(..., description="Thread dump text file (UTF-8 or Latin-1)."),
    app_hint: str = Form("", description="Application hint used in analysis context."),
    time_utc: str = Form("", description="Optional dump timestamp metadata (UTC string)."),
    top_n: int = Form(15, ge=5, le=50, description="Number of top hotspots/groups to prioritize."),
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


@router.post(
    "/v1/jvm/threaddump/analyze-multi-file",
    response_model=MultiThreadDumpAnalysis,
    summary="Analyze multiple thread dump files",
    description="Upload two or more thread dump files and perform comparative analysis across captures.",
    response_description="Structured multi-dump analysis showing persistent and changing behaviors.",
    responses={
        200: {"description": "Multiple thread dumps analyzed successfully."},
        400: {"description": "At least two files are required."},
        413: {"description": "One of the uploaded files exceeds endpoint size limit."},
        422: {"description": "Validation error in multipart/form-data parameters."},
        502: {"description": "Downstream analysis dependency failed."},
    },
)
async def analyze_thread_dump_multi_file(
    files: List[UploadFile] = File(..., description="Two or more thread dump files."),
    app_hint: str = Form("", description="Application hint used in analysis context."),
    times_utc: str = Form("", description="Comma-separated UTC timestamps aligned with file order."),
    top_n: int = Form(15, ge=5, le=50, description="Number of top hotspots/groups to prioritize."),
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
