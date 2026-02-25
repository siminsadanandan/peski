import asyncio
import json
import os
import pathlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from settings import TDA_JAR_PATH, TDA_JAVA_BIN, TDA_MCP_TIMEOUT_SEC, TDA_TMP_DIR


TDA_DEFAULT_PIPELINE = [
    "get_summary",
    "check_deadlocks",
    "find_long_running",
    "get_zombie_threads",
    "analyze_virtual_threads",
]

_HOTSPOT_HEADER_RE = re.compile(r"^\s*Full thread dump\s+Java HotSpot", re.MULTILINE)
_END_OF_DUMP_RE = re.compile(r"(?im)^\s*<EndOfDump>\s*$")


def _ensure_tda_prereqs():
    if not os.path.exists(TDA_JAR_PATH):
        raise HTTPException(status_code=500, detail=f"TDA_JAR_PATH not found: {TDA_JAR_PATH}")
    pathlib.Path(TDA_TMP_DIR).mkdir(parents=True, exist_ok=True)


def _normalize_bytes(b: bytes) -> bytes:
    b = b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if b.startswith(b"\xef\xbb\xbf"):
        b = b[3:]
    b = b.replace(b"\x00", b"")
    return b


def _normalize_text(s: str) -> str:
    b = _normalize_bytes(s.encode("utf-8", errors="replace"))
    return b.decode("utf-8", errors="replace")


def _ensure_end_of_dump(text: str) -> str:
    t = text.strip()
    if not _END_OF_DUMP_RE.search(t):
        t = t + "\n\n<EndOfDump>\n"
    return t + "\n"


def _inject_boundary(text: str, label: str) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    prefix = (
        f"{now}\n"
        f"Full thread dump Java HotSpot(TM) 64-Bit Server VM: (segment {label})\n"
    )
    body = text.strip()
    return _ensure_end_of_dump(prefix + body)


def _wrap_if_missing_hotspot_header(text: str, label: str, wrap: bool = True) -> str:
    body = text.strip()
    if _HOTSPOT_HEADER_RE.search(body):
        return _ensure_end_of_dump(body)
    if not wrap:
        return _ensure_end_of_dump(body)
    return _inject_boundary(body, label=label)


def _maybe_extract_actuator_dump_text(body: str) -> str:
    s = (body or "").strip()
    if not s:
        return ""
    if not (s.startswith("{") or s.startswith("[")):
        return body

    try:
        obj = json.loads(s)
    except Exception:
        return body

    if isinstance(obj, dict) and "threads" not in obj:
        td = obj.get("threadDump")
        if isinstance(td, dict) and isinstance(td.get("threads"), list):
            obj = td

    if not (isinstance(obj, dict) and isinstance(obj.get("threads"), list)):
        return body

    threads = obj["threads"]

    def lock_hex_from_thread(t: dict) -> Optional[str]:
        ln = t.get("lockName")
        if isinstance(ln, str):
            m = re.search(r"@([0-9a-fA-F]+)\b", ln)
            if m:
                return "0x" + m.group(1).lower()
        li = t.get("lockInfo")
        if isinstance(li, dict):
            ihc = li.get("identityHashCode")
            if isinstance(ihc, int) and ihc >= 0:
                return "0x%08x" % ihc
        return None

    out: List[str] = []
    out.append('Full thread dump Java HotSpot(TM) 64-Bit Server VM (from actuator):')

    for t in threads:
        if not isinstance(t, dict):
            continue

        name = t.get("threadName") or "unknown"
        tid = t.get("threadId")
        state = t.get("threadState") or ""
        daemon = bool(t.get("daemon", False))
        prio = t.get("priority")

        in_native = t.get("inNative")
        suspended = t.get("suspended")

        hdr = f'"{name}"'
        if tid is not None:
            hdr += f" #{tid}"
        if daemon:
            hdr += " daemon"
        if prio is not None:
            hdr += f" prio={prio}"
        if state:
            hdr += f" state={state}"
        if in_native is not None or suspended is not None:
            hdr += f" (inNative={in_native} suspended={suspended})"
        out.append("\n" + hdr)

        bc = t.get("blockedCount")
        bt = t.get("blockedTime")
        wc = t.get("waitedCount")
        wt = t.get("waitedTime")
        if any(v is not None for v in [bc, bt, wc, wt]):
            out.append(f"    (blockedCount={bc} blockedTime={bt} waitedCount={wc} waitedTime={wt})")

        st = t.get("stackTrace") or []
        if isinstance(st, list):
            for fr in st[:4000]:
                if not isinstance(fr, dict):
                    out.append(f"    at {fr}")
                    continue
                c = fr.get("className") or ""
                m = fr.get("methodName") or ""
                fn = fr.get("fileName") or ""
                ln = fr.get("lineNumber")
                native = bool(fr.get("nativeMethod", False))

                if c and m:
                    if native:
                        out.append(f"    at {c}.{m}(Native Method)")
                    else:
                        if ln is None:
                            out.append(f"    at {c}.{m}({fn})")
                        else:
                            out.append(f"    at {c}.{m}({fn}:{ln})")
                else:
                    out.append(f"    at {json.dumps(fr, ensure_ascii=False)}")

        lock_hex = lock_hex_from_thread(t)
        lock_info = t.get("lockInfo") if isinstance(t.get("lockInfo"), dict) else None
        lock_cls = lock_info.get("className") if lock_info else None

        if state in ("WAITING", "TIMED_WAITING") and lock_hex and lock_cls:
            out.append(f"    - waiting on <{lock_hex}> (a {lock_cls})")

        owner_id = t.get("lockOwnerId")
        if state == "BLOCKED" and lock_hex and lock_cls:
            out.append(f"    - waiting to lock <{lock_hex}> (a {lock_cls})")
            if isinstance(owner_id, int) and owner_id >= 0:
                out.append(f"    - lock owner thread id: {owner_id}")

        syncs = t.get("lockedSynchronizers") or []
        if isinstance(syncs, list) and syncs:
            out.append("    Locked ownable synchronizers:")
            for sy in syncs[:200]:
                if isinstance(sy, dict):
                    scls = sy.get("className")
                    ihc = sy.get("identityHashCode")
                    hx = ("0x%08x" % ihc) if isinstance(ihc, int) and ihc >= 0 else None
                    if hx and scls:
                        out.append(f"      - <{hx}> (a {scls})")
                    else:
                        out.append(f"      - {json.dumps(sy, ensure_ascii=False)}")
                else:
                    out.append(f"      - {sy}")

        mons = t.get("lockedMonitors") or []
        if isinstance(mons, list) and mons:
            for mon in mons[:200]:
                if isinstance(mon, dict):
                    li = mon.get("lockInfo") if isinstance(mon.get("lockInfo"), dict) else None
                    mcls = li.get("className") if li else None
                    ihc = li.get("identityHashCode") if li else None
                    hx = ("0x%08x" % ihc) if isinstance(ihc, int) and ihc >= 0 else None
                    if hx and mcls:
                        out.append(f"    - locked <{hx}> (a {mcls})")
                else:
                    out.append(f"    - locked {mon}")

    return "\n".join(out) + "\n"


async def _proc_readline(proc: asyncio.subprocess.Process, timeout: int) -> str:
    line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
    if not line:
        return ""
    return line.decode("utf-8", errors="replace").rstrip("\n")


async def _proc_writeline(proc: asyncio.subprocess.Process, obj: dict, timeout: int):
    data = (json.dumps(obj) + "\n").encode("utf-8")
    assert proc.stdin is not None
    proc.stdin.write(data)
    await asyncio.wait_for(proc.stdin.drain(), timeout=timeout)


async def _read_stderr_snip(proc: asyncio.subprocess.Process, max_bytes: int = 8000) -> str:
    try:
        if proc.stderr is None:
            return ""
        data = await asyncio.wait_for(proc.stderr.read(max_bytes), timeout=1)
        return data.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


async def _mcp_expect_id(proc, expect_id: int, timeout: int) -> dict:
    while True:
        line = await _proc_readline(proc, timeout=timeout)
        if not line:
            stderr = await _read_stderr_snip(proc)
            raise RuntimeError(f"TDA MCP: no response for id={expect_id}. stderr={stderr}")
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if msg.get("id") == expect_id:
            if "error" in msg:
                raise RuntimeError(f"TDA MCP error for id={expect_id}: {msg['error']}")
            return msg.get("result") or {}


async def tda_mcp_list_tools() -> List[dict]:
    _ensure_tda_prereqs()
    cmd = [TDA_JAVA_BIN, "-Djava.awt.headless=true", "-jar", TDA_JAR_PATH, "--mcp"]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        init_id = 1
        await _proc_writeline(proc, {
            "jsonrpc": "2.0",
            "id": init_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "fastapi-tda-client", "version": "1.0"},
                "capabilities": {},
            },
        }, timeout=TDA_MCP_TIMEOUT_SEC)
        _ = await _mcp_expect_id(proc, init_id, timeout=TDA_MCP_TIMEOUT_SEC)

        list_id = 2
        await _proc_writeline(proc, {"jsonrpc": "2.0", "id": list_id, "method": "tools/list", "params": {}}, timeout=TDA_MCP_TIMEOUT_SEC)
        result = await _mcp_expect_id(proc, list_id, timeout=TDA_MCP_TIMEOUT_SEC)
        return result.get("tools") or []
    finally:
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except Exception:
            pass


async def tda_mcp_run_pipeline(log_path_abs: str, tools_to_run: List[str]) -> Dict[str, Any]:
    _ensure_tda_prereqs()
    if not os.path.isabs(log_path_abs):
        raise RuntimeError(f"log_path must be absolute; got: {log_path_abs}")
    if not os.path.exists(log_path_abs):
        raise RuntimeError(f"log_path does not exist: {log_path_abs}")

    cmd = [TDA_JAVA_BIN, "-Djava.awt.headless=true", "-jar", TDA_JAR_PATH, "--mcp"]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    results: Dict[str, Any] = {}
    try:
        init_id = 1
        await _proc_writeline(proc, {
            "jsonrpc": "2.0",
            "id": init_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "fastapi-tda-client", "version": "1.0"},
                "capabilities": {},
            },
        }, timeout=TDA_MCP_TIMEOUT_SEC)
        _ = await _mcp_expect_id(proc, init_id, timeout=TDA_MCP_TIMEOUT_SEC)

        list_id = 2
        await _proc_writeline(proc, {"jsonrpc": "2.0", "id": list_id, "method": "tools/list", "params": {}}, timeout=TDA_MCP_TIMEOUT_SEC)
        list_res = await _mcp_expect_id(proc, list_id, timeout=TDA_MCP_TIMEOUT_SEC)
        tools = list_res.get("tools") or []
        tool_names = [t.get("name") for t in tools if isinstance(t, dict) and t.get("name")]

        if "parse_log" not in tool_names:
            raise RuntimeError(f"TDA MCP does not expose parse_log. tools={tool_names}")

        parse_id = 3
        await _proc_writeline(proc, {
            "jsonrpc": "2.0",
            "id": parse_id,
            "method": "tools/call",
            "params": {"name": "parse_log", "arguments": {"path": log_path_abs}},
        }, timeout=TDA_MCP_TIMEOUT_SEC)
        results["parse_log"] = await _mcp_expect_id(proc, parse_id, timeout=TDA_MCP_TIMEOUT_SEC)

        next_id = 10
        for nm in tools_to_run:
            if nm not in tool_names:
                results[nm] = {"error": f"tool not found in server: {nm}"}
                continue
            await _proc_writeline(proc, {
                "jsonrpc": "2.0",
                "id": next_id,
                "method": "tools/call",
                "params": {"name": nm, "arguments": {}},
            }, timeout=TDA_MCP_TIMEOUT_SEC)
            results[nm] = await _mcp_expect_id(proc, next_id, timeout=TDA_MCP_TIMEOUT_SEC)
            next_id += 1

        return {
            "tool_names": tool_names,
            "log_path": log_path_abs,
            "results": results,
        }

    finally:
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except Exception:
            pass


def _extract_text_blocks(mcp_result: Any) -> str:
    if not isinstance(mcp_result, dict):
        return str(mcp_result)
    content = mcp_result.get("content")
    parts: List[str] = []
    if isinstance(content, list):
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text" and c.get("text") is not None:
                parts.append(str(c["text"]))
    if parts:
        return "\n".join(parts).strip()
    try:
        return json.dumps(mcp_result, indent=2)[:8000]
    except Exception:
        return str(mcp_result)[:8000]


def _clean_json_escapes(s: str) -> str:
    try:
        return bytes(s, "utf-8").decode("unicode_escape")
    except Exception:
        return s


def _normalize_tda_pipeline_output(pipeline_out: Dict[str, Any]) -> str:
    res = pipeline_out.get("results") or {}
    lines: List[str] = []
    for k in ["get_summary", "check_deadlocks", "find_long_running", "get_zombie_threads", "analyze_virtual_threads"]:
        if k in res:
            txt = _clean_json_escapes(_extract_text_blocks(res[k]))
            if txt:
                lines.append(f"### {k}\n{txt}")
    if not lines:
        lines.append("No text blocks extracted from TDA MCP results. Check tda_raw for details.")
    return "\n\n".join(lines)
