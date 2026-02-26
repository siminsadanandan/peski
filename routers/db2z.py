from typing import List

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile

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


@router.post(
    "/v1/db2z/ddl/validate",
    response_model=Db2zDdlValidationResponse,
    summary="Validate DB2 z/OS DDL from JSON",
    description="Validate one or more DDL statements from a JSON body and return issues and suggestions for DB2 z/OS compatibility.",
    response_description="Validation summary with issues, suggestions, and optionally rewritten DDL statements.",
    responses={
        200: {"description": "DDL validation completed successfully."},
        422: {"description": "Validation error in the request payload."},
        502: {"description": "Downstream analysis dependency failed."},
    },
)
def validate_db2z_ddl(
    req: Db2zDdlValidationRequest = Body(..., description="DDL validation payload."),
) -> Db2zDdlValidationResponse:
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


@router.post(
    "/v1/db2z/ddl/validate-file",
    response_model=Db2zDdlValidationResponse,
    summary="Validate DB2 z/OS DDL from file upload",
    description="Upload a SQL file, split it into DDL statements, and validate compatibility with DB2 z/OS.",
    response_description="Validation summary for uploaded DDL content.",
    responses={
        200: {"description": "DDL file validated successfully."},
        400: {"description": "No DDL statements were found in the uploaded file."},
        413: {"description": "Uploaded file exceeds size limit."},
        422: {"description": "Validation error in multipart/form-data parameters."},
        502: {"description": "Downstream analysis dependency failed."},
    },
)
async def validate_db2z_ddl_file(
    file: UploadFile = File(..., description="SQL file containing DDL statements to validate."),
    source: str = Query("db2luw", description="Source dialect hint (for example: db2luw)."),
    include_rewritten: bool = Query(True, description="Include rewritten DDL candidates in the response."),
    llm_batch_size: int = Query(20, ge=1, le=200, description="Batch size for LLM validation across many statements."),
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
