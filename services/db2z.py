import re
from typing import List

from schemas import Db2zDdlIssue, Db2zDdlSuggestion


_DEFAULT_CURRENT_DATE_BAD = re.compile(r"\bDEFAULT\s+CURRENT_DATE\b", re.IGNORECASE)
_DEFAULT_CURRENT_TIMESTAMP_BAD = re.compile(r"\bDEFAULT\s+CURRENT_TIMESTAMP\b", re.IGNORECASE)


def quick_db2z_rules(ddls: List[str]):
    issues: List[Db2zDdlIssue] = []
    suggestions: List[Db2zDdlSuggestion] = []
    rewritten = list(ddls)

    for i, ddl in enumerate(ddls):
        original = ddl

        if _DEFAULT_CURRENT_DATE_BAD.search(ddl):
            issues.append(Db2zDdlIssue(
                rule_id="DB2Z_DEFAULT_CURRENT_DATE_FORMAT",
                severity="warn",
                message="Found DEFAULT CURRENT_DATE (underscore). DB2 uses 'CURRENT DATE' (space). Often indicates extraction/translation issue.",
                statement_index=i,
                evidence="...DEFAULT CURRENT_DATE...",
            ))
            after = _DEFAULT_CURRENT_DATE_BAD.sub("DEFAULT CURRENT DATE", ddl)
            suggestions.append(Db2zDdlSuggestion(
                title="Rewrite DEFAULT CURRENT_DATE to DEFAULT CURRENT DATE",
                statement_index=i,
                before=original,
                after=after,
                rationale="DB2 uses CURRENT DATE (space); underscore form is typical of other dialects or faulty extraction.",
            ))
            rewritten[i] = after
            ddl = after

        if _DEFAULT_CURRENT_TIMESTAMP_BAD.search(ddl):
            issues.append(Db2zDdlIssue(
                rule_id="DB2Z_DEFAULT_CURRENT_TIMESTAMP_FORMAT",
                severity="warn",
                message="Found DEFAULT CURRENT_TIMESTAMP (underscore). DB2 uses 'CURRENT TIMESTAMP' (space). Often indicates extraction/translation issue.",
                statement_index=i,
                evidence="...DEFAULT CURRENT_TIMESTAMP...",
            ))
            after = _DEFAULT_CURRENT_TIMESTAMP_BAD.sub("DEFAULT CURRENT TIMESTAMP", ddl)
            suggestions.append(Db2zDdlSuggestion(
                title="Rewrite DEFAULT CURRENT_TIMESTAMP to DEFAULT CURRENT TIMESTAMP",
                statement_index=i,
                before=original,
                after=after,
                rationale="DB2 uses CURRENT TIMESTAMP (space); underscore form is typical of other dialects or faulty extraction.",
            ))
            rewritten[i] = after

    return issues, suggestions, rewritten


def split_sql_statements(sql: str) -> List[str]:
    stmts: List[str] = []
    buf: List[str] = []
    in_sq = False
    in_dq = False
    prev = ""

    for ch in sql:
        if ch == "'" and not in_dq and prev != "\\":
            in_sq = not in_sq
        elif ch == '"' and not in_sq and prev != "\\":
            in_dq = not in_dq

        if ch == ";" and not in_sq and not in_dq:
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
        else:
            buf.append(ch)
        prev = ch

    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts
