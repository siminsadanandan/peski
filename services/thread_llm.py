from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from schemas import (
    MultiThreadDumpAnalysis,
    ThreadDumpAnalysis,
)
from settings import (
  TD_LLM_MODEL,
  TD_LLM_PROVIDER,
  TD_LLM_TEMP,
  TD_OLLAMA_BASE_URL,
  TD_OPENAI_API_KEY,
)


if TD_LLM_PROVIDER == "openai":
  llm = ChatOpenAI(
    model=TD_LLM_MODEL,
    temperature=TD_LLM_TEMP,
    api_key=TD_OPENAI_API_KEY,
  )
else:
  llm = ChatOpenAI(
    model=TD_LLM_MODEL,
    temperature=TD_LLM_TEMP,
    base_url=TD_OLLAMA_BASE_URL,
    api_key=TD_OPENAI_API_KEY,
  )


TD_SYSTEM = """You are a senior JVM performance engineer specializing in thread dump analysis.
You will be given a raw JVM thread dump.

Task:
- Summarize overall health and key symptoms.
- Estimate thread state distribution and highlight hotspots:
  deadlocks, lock contention, blocked IO, CPU spin, pool starvation.
- Call out suspicious thread groups: GC threads, ForkJoinPool, common pools, Netty, Tomcat,
  Kafka, JDBC pools, etc.
- Provide concrete next actions: what to capture next (another dump, JFR, async-profiler),
  which metrics to check, and quick mitigations.

Rules:
- Do NOT invent stack traces or thread names; only reference what is present.
- If the dump is incomplete/trimmed, say so and mark findings as tentative.
Return STRICT JSON matching the schema.
"""
TD_HUMAN = """
CONTEXT:
- App hint: {app_hint}
- Dump time (UTC): {time_utc}
- Return top N: {top_n}

THREAD DUMP (raw):
{dump}

{format_instructions}
"""

td_parser = JsonOutputParser(pydantic_object=ThreadDumpAnalysis)
td_prompt = ChatPromptTemplate.from_messages([("system", TD_SYSTEM), ("human", TD_HUMAN)])
td_chain = td_prompt | llm | td_parser


TD_MULTI_SYSTEM = """You are a senior JVM performance engineer specializing in multi-dump thread dump analysis.
You will be given MULTIPLE sequential JVM thread dumps.

Task:
- Identify persistent threads (same name/state/stack repeating across dumps).
- Detect likely deadlocks, lock contention hotspots, and CPU-spin/livelock patterns.
- Identify whether stacks are changing (progress) vs identical (stuck).
- Summarize state changes (RUNNABLE->BLOCKED etc.) for important threads/groups.
- Provide concrete next actions.

Rules:
- Do NOT invent thread names or stacks; only reference evidence present in dumps.
Return STRICT JSON matching the schema.
"""
TD_MULTI_HUMAN = """
CONTEXT:
- App hint: {app_hint}
- Dump times (UTC): {times_utc}
- Return top N: {top_n}
- Dump count: {dump_count}

THREAD DUMPS (sequential):
{dumps_block}

{format_instructions}
"""

td_multi_parser = JsonOutputParser(pydantic_object=MultiThreadDumpAnalysis)
td_multi_prompt = ChatPromptTemplate.from_messages([("system", TD_MULTI_SYSTEM), ("human", TD_MULTI_HUMAN)])
td_multi_chain = td_multi_prompt | llm | td_multi_parser
