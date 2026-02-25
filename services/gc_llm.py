from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from schemas import GcAdvice
from settings import (
    GC_LLM_MODEL,
    GC_LLM_PROVIDER,
    GC_LLM_TEMP,
    GC_OLLAMA_BASE_URL,
    GC_OPENAI_API_KEY,
)


if GC_LLM_PROVIDER == "openai":
    llm = ChatOpenAI(
        model=GC_LLM_MODEL,
        temperature=GC_LLM_TEMP,
        api_key=GC_OPENAI_API_KEY,
    )
else:
    llm = ChatOpenAI(
        model=GC_LLM_MODEL,
        temperature=GC_LLM_TEMP,
        base_url=GC_OLLAMA_BASE_URL,
        api_key=GC_OPENAI_API_KEY,
    )


GC_SYSTEM = """You are a senior JVM GC performance engineer.
Given structured GC metrics (not raw logs), produce precise, actionable tuning advice.
Be concrete. Prefer minimal flag changes with clear rollback.
Address G1, ZGC, and Shenandoah when relevant. Note container memory headroom needs.
NEVER fabricate numbers; use only provided inputs.
Return STRICT JSON matching the schema."""
GC_HUMAN = """
INPUT:
- JVM: {jvm}
- GC: {gc}
- Heap(MB): {heap_mb}
- Young(MB): {young_mb}
- p95(ms): {pause_p95_ms}, p99(ms): {pause_p99_ms}
- Throughput Util(%CPU busy GC-inclusive): {throughput_util_pct}
- Alloc Rate(MB/s): {alloc_rate_mb_s}
- Humongous(%): {humongous_pct}, To-space Exhaustions: {to_space_exhaustions}
- Mixed GC ratio: {mixed_gc_ratio}, Full GC count: {full_gc_count}
- CPU cores: {cpu_cores}
- Container limits: {container_limits}
- Flags: {flags}
- Workload hint: {workload_hint}
- Evidence notes: {evidence}
"""

gc_parser = JsonOutputParser(pydantic_object=GcAdvice)
gc_prompt = ChatPromptTemplate.from_messages([
    ("system", GC_SYSTEM),
    ("human", GC_HUMAN + "\n{format_instructions}"),
])
gc_chain = gc_prompt | llm | gc_parser
