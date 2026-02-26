from fastapi import APIRouter

from schemas import GcAdvice, GcMetrics
from services import gc_chain, gc_parser


ROUTER_PREFIX = ""
ROUTER_TAGS = ["gc"]

router = APIRouter(prefix=ROUTER_PREFIX, tags=ROUTER_TAGS)


@router.post(
    "/v1/gc/recommendations",
    response_model=GcAdvice,
    summary="Generate GC recommendations",
    description="Analyze JVM/GC metrics and return prioritized tuning and operational recommendations.",
    response_description="Structured GC advice including actions, flags to try, and rollback notes.",
    responses={
        200: {"description": "GC advice generated successfully."},
        422: {"description": "Validation error in the GC metrics payload."},
        502: {"description": "Downstream analysis dependency failed."},
    },
)
def recommend(metrics: GcMetrics) -> GcAdvice:
    inputs = {k: (v.dict() if hasattr(v, "dict") else v) for k, v in metrics.dict().items()}
    return gc_chain.invoke({**inputs, "format_instructions": gc_parser.get_format_instructions()})
