import os


def _env_with_fallback(primary: str, fallback: str, default: str) -> str:
    return os.getenv(primary, os.getenv(fallback, default))


def _env_float_with_fallback(primary: str, fallback: str, default: float) -> float:
    return float(_env_with_fallback(primary, fallback, str(default)))


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _env_provider_with_fallback(primary: str, fallback: str, default: str) -> str:
    value = _env_with_fallback(primary, fallback, default).strip().lower()
    if value not in {"ollama", "openai"}:
        return default
    return value


DEFAULT_OLLAMA_BASE_URL = "http://10.2.104.81:11434/v1"
DEFAULT_OLLAMA_MODEL = "qwen2.5-coder:7b-instruct"
DEFAULT_LLM_TEMP = 0.1
DEFAULT_LLM_PROVIDER = "ollama"
DEFAULT_OPENAI_API_KEY = "ollama"


GC_LLM_TEMP = _env_float_with_fallback("GC_LLM_TEMP", "LLM_TEMP", DEFAULT_LLM_TEMP)
GC_LLM_PROVIDER = _env_provider_with_fallback("GC_LLM_PROVIDER", "LLM_PROVIDER", DEFAULT_LLM_PROVIDER)
GC_LLM_MODEL = _env_with_fallback("GC_LLM_MODEL", "GC_OLLAMA_MODEL", _env_with_fallback("LLM_MODEL", "OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL))
GC_OLLAMA_BASE_URL = _env_with_fallback("GC_OLLAMA_BASE_URL", "OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
GC_OLLAMA_MODEL = _env_with_fallback("GC_OLLAMA_MODEL", "OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
GC_OPENAI_API_KEY = _env_with_fallback("GC_OPENAI_API_KEY", "OPENAI_API_KEY", DEFAULT_OPENAI_API_KEY)


DB2Z_LLM_TEMP = _env_float_with_fallback("DB2Z_LLM_TEMP", "LLM_TEMP", DEFAULT_LLM_TEMP)
DB2Z_LLM_PROVIDER = _env_provider_with_fallback("DB2Z_LLM_PROVIDER", "LLM_PROVIDER", DEFAULT_LLM_PROVIDER)
DB2Z_LLM_MODEL = _env_with_fallback("DB2Z_LLM_MODEL", "DB2Z_OLLAMA_MODEL", _env_with_fallback("LLM_MODEL", "OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL))
DB2Z_OLLAMA_BASE_URL = _env_with_fallback("DB2Z_OLLAMA_BASE_URL", "OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
DB2Z_OLLAMA_MODEL = _env_with_fallback("DB2Z_OLLAMA_MODEL", "OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
DB2Z_OPENAI_API_KEY = _env_with_fallback("DB2Z_OPENAI_API_KEY", "OPENAI_API_KEY", DEFAULT_OPENAI_API_KEY)


TD_LLM_TEMP = _env_float_with_fallback("TD_LLM_TEMP", "LLM_TEMP", DEFAULT_LLM_TEMP)
TD_LLM_PROVIDER = _env_provider_with_fallback("TD_LLM_PROVIDER", "LLM_PROVIDER", DEFAULT_LLM_PROVIDER)
TD_LLM_MODEL = _env_with_fallback("TD_LLM_MODEL", "TD_OLLAMA_MODEL", _env_with_fallback("LLM_MODEL", "OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL))
TD_OLLAMA_BASE_URL = _env_with_fallback("TD_OLLAMA_BASE_URL", "OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
TD_OLLAMA_MODEL = _env_with_fallback("TD_OLLAMA_MODEL", "OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
TD_OPENAI_API_KEY = _env_with_fallback("TD_OPENAI_API_KEY", "OPENAI_API_KEY", DEFAULT_OPENAI_API_KEY)


TDA_JAR_PATH = _env_str("TDA_JAR_PATH", "/opt/tda/tda.jar")
TDA_JAVA_BIN = _env_str("TDA_JAVA_BIN", "java")
TDA_MCP_TIMEOUT_SEC = _env_int("TDA_MCP_TIMEOUT_SEC", 60)
TDA_TMP_DIR = _env_str("TDA_TMP_DIR", "/tmp/tda_inputs")


CAPTURE_OUT_DIR = _env_str("CAPTURE_OUT_DIR", "/var/log/threaddumps")
CAPTURE_HTTP_TIMEOUT_SEC = _env_int("CAPTURE_HTTP_TIMEOUT_SEC", 10)
TRACE_NSENTER_ENABLED = _env_bool("TRACE_NSENTER_ENABLED", False)
TRACE_HOST_PID_DISCOVERY_ENABLED = _env_bool("TRACE_HOST_PID_DISCOVERY_ENABLED", False)
