# peski

FastAPI service with cross-platform local setup scripts.

## Prerequisites

- Python 3.9+
- Internet access for `pip install`

## macOS / Linux

```bash
./scripts/setup.sh
./scripts/run.sh
```

If `./scripts/setup.sh` is not executable:

```bash
chmod +x scripts/*.sh
./scripts/setup.sh
```

VS Code interpreter:

- `.venv-macos/bin/python`

## Windows (PowerShell)

```powershell
.\scripts\setup.ps1
.\scripts\run.ps1
```

If script execution is blocked:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup.ps1
```

VS Code interpreter:

- `.venv-win\Scripts\python.exe`

## API Routes

Full route documentation is in [docs/API.md](docs/API.md).

- health
  - `GET /v1/health`
- gc
  - `POST /v1/gc/recommendations`
- db2z
  - `POST /v1/db2z/ddl/validate`
  - `POST /v1/db2z/ddl/validate-file`
- thread-llm
  - `POST /v1/jvm/threaddump/analyze`
  - `POST /v1/jvm/threaddump/analyze-file`
  - `POST /v1/jvm/threaddump/analyze-multi-file`
- tda-mcp
  - `GET /v1/tda/mcp/tools`
  - `POST /v1/jvm/threaddump/analyze-tda-mcp`
  - `POST /v1/jvm/threaddump/analyze-tda-mcp-log`
  - `POST /v1/jvm/threaddump/analyze-tda-mcp-file`
  - `POST /v1/jvm/threaddump/analyze-tda-mcp-multi-file`
- actuator
  - `POST /v1/alerts/actuator/threaddump/capture`
  - `POST /v1/alerts/actuator/threaddump/capture-tda-mcp`

## Troubleshooting import errors

If `from fastapi import FastAPI` still fails:

1. Ensure you selected the project platform-specific interpreter in your IDE.
2. Recreate the environment with the platform setup script.
3. Confirm installation:

```bash
.venv-macos/bin/python -c "import fastapi; print(fastapi.__version__)"
```

On Windows:

```powershell
.\.venv-win\Scripts\python.exe -c "import fastapi; print(fastapi.__version__)"
```
