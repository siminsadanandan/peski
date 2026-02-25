from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from schemas import Db2zDdlValidationResponse
from settings import (
    DB2Z_LLM_MODEL,
    DB2Z_LLM_PROVIDER,
    DB2Z_LLM_TEMP,
    DB2Z_OLLAMA_BASE_URL,
    DB2Z_OPENAI_API_KEY,
)


if DB2Z_LLM_PROVIDER == "openai":
    llm = ChatOpenAI(
        model=DB2Z_LLM_MODEL,
        temperature=DB2Z_LLM_TEMP,
        api_key=DB2Z_OPENAI_API_KEY,
    )
else:
    llm = ChatOpenAI(
        model=DB2Z_LLM_MODEL,
        temperature=DB2Z_LLM_TEMP,
        base_url=DB2Z_OLLAMA_BASE_URL,
        api_key=DB2Z_OPENAI_API_KEY,
    )


DB2Z_SYSTEM = """You are a senior DB2 migration engineer.
Validate DDL statements for DB2 for z/OS compatibility and suggest required DDL migrations.
Focus on DB2 LUW -> DB2 z/OS differences and common extraction issues.

Rules:
- Only use the provided input DDL; do not invent objects.
- Be precise and actionable: show before/after rewrites when possible.
- If unsure, mark severity as "warn" and state assumptions.
Return STRICT JSON matching the schema.
"""
DB2Z_HUMAN = """
INPUT:
- Source dialect: {source}
- DDL count: {ddl_count}
- DDL statements:
{ddls_block}
"""

db2z_parser = JsonOutputParser(pydantic_object=Db2zDdlValidationResponse)
db2z_prompt = ChatPromptTemplate.from_messages([
    ("system", DB2Z_SYSTEM),
    ("human", DB2Z_HUMAN + "\n{format_instructions}"),
])
db2z_chain = db2z_prompt | llm | db2z_parser
