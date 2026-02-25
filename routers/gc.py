from fastapi import APIRouter

from schemas import GcAdvice, GcMetrics
from services import gc_chain, gc_parser


ROUTER_PREFIX = ""
ROUTER_TAGS = ["gc"]

router = APIRouter(prefix=ROUTER_PREFIX, tags=ROUTER_TAGS)


@router.post("/v1/gc/recommendations", response_model=GcAdvice)
def recommend(metrics: GcMetrics) -> GcAdvice:
    inputs = {k: (v.dict() if hasattr(v, "dict") else v) for k, v in metrics.dict().items()}
    return gc_chain.invoke({**inputs, "format_instructions": gc_parser.get_format_instructions()})
