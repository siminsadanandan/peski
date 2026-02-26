from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from routers.actuator import router as actuator_router
from routers.db2z import router as db2z_router
from routers.gc import router as gc_router
from routers.tda import router as tda_router
from routers.thread_llm import router as thread_llm_router


app = FastAPI(
    title="peski",
    version="2.2.1",
    description="Operational analysis API for JVM thread dumps, GC tuning, DB2 z/OS DDL checks, and actuator/TDA capture workflows.",
    openapi_tags=[
        {"name": "gc", "description": "GC metrics analysis and recommendations."},
        {"name": "db2z", "description": "DB2 z/OS DDL compatibility validation endpoints."},
        {"name": "thread-llm", "description": "LLM-based JVM thread dump analysis endpoints."},
        {"name": "tda-mcp", "description": "TDA MCP-based thread dump analysis endpoints."},
        {"name": "actuator", "description": "Actuator capture and alert-driven analysis endpoints."},
    ],
)

app.include_router(gc_router)
app.include_router(db2z_router)
app.include_router(thread_llm_router)
app.include_router(tda_router)
app.include_router(actuator_router)


_SCHEMA_PATCHES = {
    "ExternalActuatorCaptureRequest": {
        "actuator_url": {
            "description": "Full actuator thread dump endpoint URL.",
            "example": "https://example-host/actuator/threaddump",
        },
        "auth_mode": {"description": "Authentication mode: none|basic|bearer|header.", "example": "none"},
        "top_n": {"description": "Number of top hotspots to include during optional auto analysis.", "example": 15},
    },
    "TdaMcpActuatorCaptureRequest": {
        "actuator_url": {
            "description": "Full actuator thread dump endpoint URL.",
            "example": "https://example-host/actuator/threaddump",
        },
        "auth_mode": {"description": "Authentication mode: none|basic|bearer|header.", "example": "none"},
        "run_virtual": {"description": "Whether virtual-thread analysis should run.", "example": True},
        "wrap_if_missing_header": {"description": "Wrap non-HotSpot dump text with a synthetic header.", "example": True},
    },
    "ExternalActuatorCaptureResponse": {
        "analysis_error": {
            "description": "Analysis failure reason when auto-analysis could not complete.",
            "example": "Model invocation timed out",
        }
    },
    "TdaMcpActuatorCaptureResponse": {
        "normalized_text": {"description": "Human-readable normalized TDA analysis summary."},
        "tda_raw": {"description": "Raw tool output payload from TDA MCP pipeline."},
    },
}


def _apply_schema_patches(openapi_schema: dict) -> None:
    components = openapi_schema.get("components", {}).get("schemas", {})
    for schema_name, props in _SCHEMA_PATCHES.items():
        schema = components.get(schema_name)
        if not schema:
            continue
        properties = schema.get("properties", {})
        for prop_name, patch in props.items():
            if prop_name in properties:
                properties[prop_name].update(patch)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    _apply_schema_patches(schema)
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get(
    "/v1/health",
    summary="Get service health",
    description="Simple liveness endpoint for health checks and monitoring probes.",
    response_description="Service health status payload.",
    responses={200: {"description": "Service is reachable and healthy."}},
    tags=["health"],
)
def health():
    return {"status": "ok"}
