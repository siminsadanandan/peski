# API Reference

## Cross-cutting notes

- Upload limits:
  - `thread-llm` single file endpoints: 2MB per file.
  - `tda-mcp` multi-file endpoint: ~5MB total across all files.
  - `db2z` file endpoint: ~5MB.
- Actuator auth modes: `none`, `basic`, `bearer`, `header`.
- TDA endpoints require TDA MCP prerequisites configured in runtime environment.

## gc

### POST `/v1/gc/recommendations`
Purpose: Analyze JVM GC metrics and return tuning recommendations.

Request body: `GcMetrics` JSON.

Example:
```bash
curl -X POST http://localhost:8080/v1/gc/recommendations \
  -H 'Content-Type: application/json' \
  -d '{"jvm":"OpenJDK 21","gc":"G1GC","heap_mb":4096}'
```

Success response: `GcAdvice` JSON (`summary`, `actions`, `flags_to_try`, optional `alternatives`).

Errors: `422` validation error, `502` downstream analysis failure.

## db2z

### POST `/v1/db2z/ddl/validate`
Purpose: Validate DDL statements for DB2 z/OS compatibility from JSON.

Request body: `Db2zDdlValidationRequest`.

Example:
```bash
curl -X POST http://localhost:8080/v1/db2z/ddl/validate \
  -H 'Content-Type: application/json' \
  -d '{"ddls":["CREATE TABLE T1 (ID BIGINT NOT NULL PRIMARY KEY);"],"source":"db2luw","include_rewritten":true}'
```

Success response: `Db2zDdlValidationResponse`.

Errors: `422` validation error, `502` downstream analysis failure.

### POST `/v1/db2z/ddl/validate-file`
Purpose: Validate DDL statements from uploaded SQL file.

Request: `multipart/form-data`
- `file`: SQL file
- `source` (query): source dialect hint
- `include_rewritten` (query): include rewritten statements
- `llm_batch_size` (query): analysis batch size

Example:
```bash
curl -X POST 'http://localhost:8080/v1/db2z/ddl/validate-file?source=db2luw&include_rewritten=true&llm_batch_size=20' \
  -F 'file=@schema.sql'
```

Success response: `Db2zDdlValidationResponse`.

Errors: `400` no DDL found, `413` file too large, `422` validation error.

## thread-llm

### POST `/v1/jvm/threaddump/analyze`
Purpose: Analyze one raw thread dump from JSON.

Request body: `ThreadDumpRequest`.

Example:
```bash
curl -X POST http://localhost:8080/v1/jvm/threaddump/analyze \
  -H 'Content-Type: application/json' \
  -d '{"dump":"...thread dump text...","app_hint":"orders","top_n":15}'
```

Success response: `ThreadDumpAnalysis`.

Errors: `413` dump too large, `422` validation error, `502` downstream analysis failure.

### POST `/v1/jvm/threaddump/analyze-file`
Purpose: Analyze one uploaded thread dump file.

Request: `multipart/form-data`
- `file`: thread dump file
- `app_hint`: optional context
- `time_utc`: optional timestamp metadata
- `top_n`: number of prioritized findings

Example:
```bash
curl -X POST http://localhost:8080/v1/jvm/threaddump/analyze-file \
  -F 'file=@dump1.log' \
  -F 'app_hint=orders' \
  -F 'top_n=15'
```

Success response: `ThreadDumpAnalysis`.

Errors: `413` file too large, `422` validation error, `502` downstream analysis failure.

### POST `/v1/jvm/threaddump/analyze-multi-file`
Purpose: Compare two or more uploaded thread dumps.

Request: `multipart/form-data`
- `files`: two or more dump files
- `app_hint`: optional context
- `times_utc`: comma-separated timestamps aligned to files
- `top_n`: number of prioritized findings

Example:
```bash
curl -X POST http://localhost:8080/v1/jvm/threaddump/analyze-multi-file \
  -F 'files=@dump1.log' \
  -F 'files=@dump2.log' \
  -F 'times_utc=2026-02-26T08:00:00Z,2026-02-26T08:00:30Z'
```

Success response: `MultiThreadDumpAnalysis`.

Errors: `400` fewer than 2 files, `413` file too large, `422` validation error.

## tda-mcp

### GET `/v1/tda/mcp/tools`
Purpose: List available TDA MCP tools.

Example:
```bash
curl http://localhost:8080/v1/tda/mcp/tools
```

Success response: array of `TdaMcpTool`.

Errors: `502` dependency failure.

### POST `/v1/jvm/threaddump/analyze-tda-mcp`
Purpose: Analyze single dump text using TDA MCP pipeline.

Request body: `TdaMcpAnalyzeTextRequest`.

Example:
```bash
curl -X POST http://localhost:8080/v1/jvm/threaddump/analyze-tda-mcp \
  -H 'Content-Type: application/json' \
  -d '{"dump":"...thread dump text...","label":"capture-1","run_virtual":true}'
```

Success response: `TdaMcpAnalyzeFileResponse`.

Errors: `400` empty dump, `413` exceeds `max_chars`, `422` validation error, `502` dependency failure.

### POST `/v1/jvm/threaddump/analyze-tda-mcp-log`
Purpose: Analyze existing server-side log path with TDA MCP.

Request: `multipart/form-data`
- `path`: absolute log path inside runtime environment
- `run_virtual`: include virtual thread analysis

Example:
```bash
curl -X POST http://localhost:8080/v1/jvm/threaddump/analyze-tda-mcp-log \
  -F 'path=/var/log/threaddumps/dump.log' \
  -F 'run_virtual=true'
```

Success response: `TdaMcpAnalyzeFileResponse`.

Errors: `422` validation error, `502` dependency failure.

### POST `/v1/jvm/threaddump/analyze-tda-mcp-file`
Purpose: Analyze one uploaded dump file via TDA MCP.

Request: `multipart/form-data`
- `file`: dump file
- `run_virtual`: include virtual thread analysis

Example:
```bash
curl -X POST http://localhost:8080/v1/jvm/threaddump/analyze-tda-mcp-file \
  -F 'file=@dump.log' \
  -F 'run_virtual=true'
```

Success response: `TdaMcpAnalyzeFileResponse`.

Errors: `413` file too large, `422` validation error, `502` dependency failure.

### POST `/v1/jvm/threaddump/analyze-tda-mcp-multi-file`
Purpose: Analyze two or more uploaded dumps via combined TDA MCP pipeline.

Request: `multipart/form-data`
- `files`: two or more dump files
- `run_virtual`: include virtual thread analysis

Example:
```bash
curl -X POST http://localhost:8080/v1/jvm/threaddump/analyze-tda-mcp-multi-file \
  -F 'files=@dump1.log' \
  -F 'files=@dump2.log' \
  -F 'run_virtual=true'
```

Success response: `TdaMcpAnalyzeMultiFileResponse`.

Errors: `400` fewer than 2 files, `413` total upload too large, `500` boundary injection guard failure, `422` validation error, `502` dependency failure.

## actuator

### POST `/v1/alerts/actuator/threaddump/capture`
Purpose: Fetch thread dumps from Spring actuator and optionally run analysis.

Request body: `ExternalActuatorCaptureRequest`.

Example:
```bash
curl -X POST http://localhost:8080/v1/alerts/actuator/threaddump/capture \
  -H 'Content-Type: application/json' \
  -d '{"actuator_url":"https://example-host/actuator/threaddump","dump_count":3,"interval_sec":5,"auth_mode":"none"}'
```

Success response: `ExternalActuatorCaptureResponse`.

Errors: `422` validation error, `502` actuator fetch failure.

### POST `/v1/alerts/actuator/threaddump/capture-tda-mcp`
Purpose: Capture actuator dumps and run TDA MCP analysis.

Request body:
- Direct `TdaMcpActuatorCaptureRequest` JSON, or
- Grafana-style webhook containing JSON string in `message`.

Example (direct):
```bash
curl -X POST http://localhost:8080/v1/alerts/actuator/threaddump/capture-tda-mcp \
  -H 'Content-Type: application/json' \
  -d '{"actuator_url":"https://example-host/actuator/threaddump","dump_count":3,"interval_sec":5,"auth_mode":"none","run_virtual":true}'
```

Success response: `TdaMcpActuatorCaptureResponse`.

Errors: `422` invalid payload/normalization error, `500` boundary guard failure, `502` actuator or TDA MCP dependency failure.

## health

### GET `/v1/health`
Purpose: Liveness endpoint.

Example:
```bash
curl http://localhost:8080/v1/health
```

Success response:
```json
{"status":"ok"}
```
