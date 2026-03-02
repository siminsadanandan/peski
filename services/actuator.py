import subprocess
from typing import Dict, Optional, Tuple

import requests
from fastapi import HTTPException
from settings import (
    CAPTURE_HTTP_TIMEOUT_SEC,
    CAPTURE_OUT_DIR,
    TRACE_HOST_PID_DISCOVERY_ENABLED,
    TRACE_NSENTER_ENABLED,
)



def external_actuator_auth_mode(auth_mode: str,
                                user: Optional[str],
                                password: Optional[str],
                                token: Optional[str],
                                authorization_header: Optional[str]) -> Tuple[Optional[Tuple[str, str]], Dict[str, str]]:
    if auth_mode == "header":
        if not authorization_header:
            raise HTTPException(status_code=400, detail="auth_mode=header requires authorization_header")
        return None, {"Authorization": authorization_header}
    if auth_mode == "basic":
        if not user:
            raise HTTPException(status_code=400, detail="auth_mode=basic requires user/password")
        return (user, password or ""), {}
    if auth_mode == "bearer":
        if not token:
            raise HTTPException(status_code=400, detail="auth_mode=bearer requires token")
        return None, {"Authorization": f"Bearer {token}"}
    return None, {}


def external_actuator_auth(req) -> Tuple[Optional[Tuple[str, str]], Dict[str, str]]:
    return external_actuator_auth_mode(req.auth_mode, req.user, req.password, req.token, req.authorization_header)


def fetch_http_text(url: str, auth: Optional[Tuple[str, str]], headers: Dict[str, str], timeout_sec: int = 10) -> str:
    r = requests.get(url, auth=auth, headers=headers, timeout=timeout_sec)
    r.raise_for_status()
    return r.text


def fetch_actuator_threaddump(url: str, auth: Optional[Tuple[str, str]], headers: Dict[str, str], timeout_sec: int = 10) -> str:
    return fetch_http_text(url, auth=auth, headers=headers, timeout_sec=timeout_sec)


def _build_trace_cmd(option: str, tcpdump_packet_count: int) -> list:
    opt = (option or "").strip().lower()
    commands = {
        "ss": ["ss", "-pant"],
        "netstat": ["netstat", "-an"],
        "tcpdump": ["tcpdump", "-nn", "-i", "any", "-c", str(int(tcpdump_packet_count))],
    }
    if opt not in commands:
        raise RuntimeError(f"Unsupported trace option: {option}")
    return commands[opt]


def _discover_host_pid(
    target_process_name: Optional[str],
    target_namespace: Optional[str],
    target_pod: Optional[str],
    target_app: Optional[str],
) -> int:
    if not TRACE_HOST_PID_DISCOVERY_ENABLED:
        raise RuntimeError("Host PID discovery is disabled. Enable TRACE_HOST_PID_DISCOVERY_ENABLED=true.")
    if not target_process_name:
        raise RuntimeError("Host PID discovery requires target_process_name.")

    proc = subprocess.run(
        ["ps", "-eo", "pid,args"],
        check=False,
        capture_output=True,
        text=True,
        timeout=8,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Unable to list processes for PID discovery: {proc.stderr or proc.stdout}")

    process_token = target_process_name.lower()
    extra_tokens = [x.lower() for x in [target_namespace, target_pod, target_app] if isinstance(x, str) and x.strip()]
    pids = []
    for line in (proc.stdout or "").splitlines()[1:]:
        s = line.strip()
        if not s:
            continue
        parts = s.split(None, 1)
        if len(parts) < 2:
            continue
        pid_str, cmd = parts[0], parts[1]
        cmd_l = cmd.lower()
        if process_token not in cmd_l:
            continue
        if extra_tokens and not all(tok in cmd_l for tok in extra_tokens):
            continue
        try:
            pids.append(int(pid_str))
        except ValueError:
            continue

    if not pids:
        raise RuntimeError("No matching PID found for requested target metadata.")
    if len(pids) > 1:
        raise RuntimeError(f"Ambiguous PID discovery: {len(pids)} matches found; provide trace_target_pid explicitly.")
    return pids[0]


def _build_nsenter_prefix(
    target_pid: Optional[int],
    target_netns_path: Optional[str],
    target_process_name: Optional[str],
    target_namespace: Optional[str],
    target_pod: Optional[str],
    target_app: Optional[str],
) -> list:
    if not TRACE_NSENTER_ENABLED:
        raise RuntimeError("nsenter mode is disabled. Enable TRACE_NSENTER_ENABLED=true.")
    if target_netns_path:
        return ["nsenter", f"--net={target_netns_path}", "--"]

    pid = target_pid
    if pid is None:
        pid = _discover_host_pid(
            target_process_name=target_process_name,
            target_namespace=target_namespace,
            target_pod=target_pod,
            target_app=target_app,
        )
    return ["nsenter", "--target", str(pid), "--net", "--"]


def run_trace_command(
    option: str,
    timeout_sec: int = 8,
    tcpdump_packet_count: int = 50,
    executor_mode: str = "local",
    target_pid: Optional[int] = None,
    target_netns_path: Optional[str] = None,
    target_process_name: Optional[str] = None,
    target_namespace: Optional[str] = None,
    target_pod: Optional[str] = None,
    target_app: Optional[str] = None,
) -> str:
    cmd = _build_trace_cmd(option, tcpdump_packet_count=tcpdump_packet_count)
    mode = (executor_mode or "local").strip().lower()
    if mode == "nsenter":
        prefix = _build_nsenter_prefix(
            target_pid=target_pid,
            target_netns_path=target_netns_path,
            target_process_name=target_process_name,
            target_namespace=target_namespace,
            target_pod=target_pod,
            target_app=target_app,
        )
        cmd = prefix + cmd
    elif mode != "local":
        raise RuntimeError(f"Unsupported trace executor_mode: {executor_mode}")

    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"Command not found for option '{option}': {e}")
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout or "") + ("\n" + e.stderr if e.stderr else "")
        raise RuntimeError(f"Command timed out for option '{option}'. Partial output:\n{partial}")

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed for option '{option}' (exit={proc.returncode}): {err or out}")
    return out or err
