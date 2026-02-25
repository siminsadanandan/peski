from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

from schemas import (
    Db2zDdlIssue,
    Db2zDdlSuggestion,
    Db2zDdlValidationRequest,
    Db2zDdlValidationResponse,
)
from services import db2z_chain, db2z_parser, enforce_5mb, quick_db2z_rules, split_sql_statements


ROUTER_PREFIX = ""
ROUTER_TAGS = ["db2z"]

router = APIRouter(prefix=ROUTER_PREFIX, tags=ROUTER_TAGS)


@router.post("/v1/db2z/ddl/validate", response_model=Db2zDdlValidationResponse)
def validate_db2z_ddl(req: Db2zDdlValidationRequest) -> Db2zDdlValidationResponse:
    issues1, suggestions1, rewritten = quick_db2z_rules(req.ddls)
    ddls_for_llm = rewritten if req.include_rewritten else req.ddls
    ddls_block = "\n\n".join([f"-- stmt[{idx}]\n{stmt}" for idx, stmt in enumerate(ddls_for_llm)])

    llm_out = db2z_chain.invoke({
        "source": req.source,
        "ddl_count": len(ddls_for_llm),
        "ddls_block": ddls_block,
        "format_instructions": db2z_parser.get_format_instructions(),
    })
    llm_result = Db2zDdlValidationResponse(**llm_out)

    merged_issues = list(issues1)
    seen = {(x.rule_id, x.statement_index, x.message) for x in merged_issues}
    for x in llm_result.issues or []:
        key = (x.rule_id, x.statement_index, x.message)
        if key not in seen:
            merged_issues.append(x)
            seen.add(key)

    merged_suggestions = list(suggestions1) + (llm_result.suggestions or [])
    summary = llm_result.summary or f"Validated {len(req.ddls)} statement(s) for DB2 z/OS compatibility."

    return Db2zDdlValidationResponse(
        summary=summary,
        issues=merged_issues,
        suggestions=merged_suggestions,
        rewritten_ddls=(rewritten if req.include_rewritten else None),
    )


@router.post("/v1/db2z/ddl/validate-file", response_model=Db2zDdlValidationResponse)
async def validate_db2z_ddl_file(
    file: UploadFile = File(...),
    source: str = "db2luw",
    include_rewritten: bool = True,
    llm_batch_size: int = 20,
) -> Db2zDdlValidationResponse:
    content = await file.read()
    enforce_5mb(content)

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    ddls = split_sql_statements(text)
    if not ddls:
        raise HTTPException(status_code=400, detail="No DDL statements found in file.")

    issues1, suggestions1, rewritten = quick_db2z_rules(ddls)
    ddls_for_llm = rewritten if include_rewritten else ddls

    merged_llm_issues: List[Db2zDdlIssue] = []
    merged_llm_suggestions: List[Db2zDdlSuggestion] = []

    offset = 0
    for batch in [ddls_for_llm[i:i + llm_batch_size] for i in range(0, len(ddls_for_llm), llm_batch_size)]:
        ddls_block = "\n\n".join([f"-- stmt[{offset + idx}]\n{stmt}" for idx, stmt in enumerate(batch)])
        llm_out = db2z_chain.invoke({
            "source": source,
            "ddl_count": len(batch),
            "ddls_block": ddls_block,
            "format_instructions": db2z_parser.get_format_instructions(),
        })
        r = Db2zDdlValidationResponse(**llm_out)
        merged_llm_issues.extend(r.issues or [])
        merged_llm_suggestions.extend(r.suggestions or [])
        offset += len(batch)

    merged_issues = list(issues1)
    seen = {(x.rule_id, x.statement_index, x.message) for x in merged_issues}
    for x in merged_llm_issues:
        key = (x.rule_id, x.statement_index, x.message)
        if key not in seen:
            merged_issues.append(x)
            seen.add(key)

    merged_suggestions = list(suggestions1) + merged_llm_suggestions

    return Db2zDdlValidationResponse(
        summary=f"Validated {len(ddls)} statement(s) from '{file.filename}' for DB2 z/OS compatibility.",
        issues=merged_issues,
        suggestions=merged_suggestions,
        rewritten_ddls=(rewritten if include_rewritten else None),
    )
