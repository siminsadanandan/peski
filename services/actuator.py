import subprocess
from typing import Dict, Optional, Tuple

import requests
from fastapi import HTTPException
from settings import CAPTURE_HTTP_TIMEOUT_SEC, CAPTURE_OUT_DIR



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


def run_trace_command(option: str, timeout_sec: int = 8, tcpdump_packet_count: int = 50) -> str:
    opt = (option or "").strip().lower()
    commands = {
        "ss": ["ss", "-pant"],
        "netstat": ["netstat", "-an"],
        "tcpdump": ["tcpdump", "-nn", "-i", "any", "-c", str(int(tcpdump_packet_count))],
    }
    if opt not in commands:
        raise RuntimeError(f"Unsupported trace option: {option}")

    try:
        proc = subprocess.run(
            commands[opt],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"Command not found for option '{opt}': {e}")
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout or "") + ("\n" + e.stderr if e.stderr else "")
        raise RuntimeError(f"Command timed out for option '{opt}'. Partial output:\n{partial}")

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed for option '{opt}' (exit={proc.returncode}): {err or out}")
    return out or err
