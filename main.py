from fastapi import FastAPI

from routers.actuator import router as actuator_router
from routers.db2z import router as db2z_router
from routers.gc import router as gc_router
from routers.tda import router as tda_router
from routers.thread_llm import router as thread_llm_router


app = FastAPI(title="peski", version="2.2.1")

app.include_router(gc_router)
app.include_router(db2z_router)
app.include_router(thread_llm_router)
app.include_router(tda_router)
app.include_router(actuator_router)


@app.get("/v1/health")
def health():
    return {"status": "ok"}
