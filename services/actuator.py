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


def fetch_actuator_threaddump(url: str, auth: Optional[Tuple[str, str]], headers: Dict[str, str], timeout_sec: int = 10) -> str:
    r = requests.get(url, auth=auth, headers=headers, timeout=timeout_sec)
    r.raise_for_status()
    return r.text
