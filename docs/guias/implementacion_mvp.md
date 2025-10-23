# Scraper Microservice — Codex Implementation Guide (MVP)

**Owner:** Daniel  
**Executor:** Codex  
**Goal:** Implement a production‑grade *Scraper API* + async worker que realiza **login interactivo**, **navegación hasta localizar y descargar PDFs**, **extracción de información relevante** y **normalización a JSON estructurado**. El almacenamiento definitivo se definirá más adelante, así que nos apoyaremos en servicios abstractos para operar en local sin depender de S3.

> ⚖️ Compliance: We do **not** evade reCAPTCHA. The user resolves it manually in a headful browser window. Only scrape with permission and respect ToS/robots. Store secrets safely.

---

## 0) High‑Level Requirements
- **Interface:** REST API (FastAPI) consumida por app Spring.
- **Async nature:** API encola jobs en Redis; workers ejecutan pipeline multi-etapa.
- **Session model:** Cada ejecución realiza login (usuario/clave) con Playwright headful; las cookies sólo viven para ese job (TTL corto).
- **Estado:** Redis se usa para sesiones y progreso; los PDFs/JSON quedan en storage/repositorios abstractos (filesystem/SQLite en MVP).
- **Per‑site scrapers:** Cada sitio expone un plugin con pasos de login, navegación y extracción dedicada.
- **Output:** JSON estructurado derivado de PDFs descargados; los ETL posteriores construirán tablas/productos a partir de ese JSON.

---

## 1) System Architecture
```
[Spring App] --(X-API-Key)--> [FastAPI Scraper API]
                                   |
                                   | enqueues
                                   v
                             [Redis Queue]
                                   |
                                   v
                              [RQ Worker]
                                   |
        ┌───────────────────────────┴───────────────────────────┐
        |        Site Plugin + Pipeline Stages (secuenciales)  |
        | Login → Navegación → Descarga PDF → Extracción → JSON|
        └──────────────────────────────────────────────────────┘

Storage:
- Redis: job status, session cookies (short TTL), progreso por etapa
- Local dev files: ./data/sessions, ./data/results, ./data/logs
- PDFs: ./data/pdfs (a través de StorageProvider local)
- Metadata/JSON: repositorio local (SQLite o archivos) vía interfaz abstracta
```

### Job Lifecycle
1. `POST /jobs` crea un job (site_id, params, credenciales **o** cookies previas) y encola la primera etapa del pipeline (`login`). Estado inicial `PENDING`.
2. `Stage: login` abre Playwright headful para que el usuario se autentique **o** reutiliza cookies exportadas (por ejemplo con `scripts/manual_login.py`); las cookies activas se guardan en Redis (`session:{token}`) con TTL 1h.
3. `Stage: navegación` ocupa el plugin del sitio para llegar a la sección de documentos y devuelve una lista de PDFs con metadata (URL, nombre, tipo, rango fechas).
4. `Stage: descarga` consume cada URL, descarga el PDF usando cookies, lo persiste vía `StorageProvider` local (`./data/pdfs/{job_id}/`) y registra el artefacto en la `MetadataRepository`.
5. `Stage: extracción` lee cada PDF desde storage, aplica el extractor correspondiente (`pdfplumber`, `camelot`, etc.), normaliza a JSON y guarda los registros en la misma `MetadataRepository` y en `./data/results/{job_id}.json` para depuración.
6. `GET /jobs/{job_id}` devuelve estado + etapa actual; `GET /jobs/{job_id}/artifacts` lista PDFs almacenados; `GET /jobs/{job_id}/extractions` expone el JSON generado.

---

## 2) API Contract (OpenAPI excerpt)
```yaml
openapi: 3.0.3
info: { title: Scraper Service, version: 0.2.0 }
servers: [ { url: http://localhost:8080 } ]
components:
  securitySchemes:
    ApiKeyAuth: { type: apiKey, in: header, name: X-API-Key }
  schemas:
    CreateJobRequest:
      type: object
      required: [client_id, site_id, params]
      properties:
        client_id: { type: string }
        site_id:    { type: string, example: "isapre-x" }
        params:     { type: object, description: filtros del sitio (fechas, etc.) }
        credentials:
          description: Opcional; se usa Playwright headful para login si se provee.
          type: object
          required: [username, password]
          properties:
            username: { type: string }
            password: { type: string }
        auth:
          description: Alternativa al login interactivo; permite reusar cookies exportadas manualmente.
          type: object
          properties:
            cookies: { type: array, items: { type: object } }
            cookies_file: { type: string, description: ruta en el filesystem accesible por el worker }
        stages:
          type: array
          items: { type: string, enum: [login, discover, download, extract] }
      oneOf:
        - required: [credentials]
        - required: [auth]
    CreateJobResponse:
      type: object
      properties:
        job_id: { type: string }
        status: { type: string, enum: [PENDING, RUNNING, FAILED, DONE] }
    JobStatus:
      type: object
      properties:
        job_id: { type: string }
        status: { type: string, enum: [PENDING, RUNNING, FAILED, DONE] }
        stage:  { type: string, enum: [login, discover, download, extract] }
        progress: { type: number, format: float }
        message:  { type: string }
        started_at:  { type: string, format: date-time }
        finished_at: { type: string, format: date-time, nullable: true }
    Artifact:
      type: object
      properties:
        artifact_id: { type: string }
        filename: { type: string }
        storage_uri: { type: string }
        size_bytes: { type: integer }
        metadata: { type: object }
    ExtractionRecord:
      type: object
      properties:
        artifact_id: { type: string }
        data: { type: object }
        normalized_at: { type: string, format: date-time }
security: [ { ApiKeyAuth: [] } ]
paths:
  /jobs:
    post:
      summary: Crea un job y dispara el pipeline
      security: [ { ApiKeyAuth: [] } ]
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/CreateJobRequest' }
      responses:
        "202": { description: Accepted, content: { application/json: { schema: { $ref: '#/components/schemas/CreateJobResponse' } } } }
  /jobs/{job_id}:
    get:
      summary: Estado y metadata del job
      security: [ { ApiKeyAuth: [] } ]
      parameters: [ { in: path, name: job_id, required: true, schema: { type: string } } ]
      responses:
        "200": { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/JobStatus' } } } }
  /jobs/{job_id}/artifacts:
    get:
      summary: Lista PDFs descargados para el job
      security: [ { ApiKeyAuth: [] } ]
      parameters: [ { in: path, name: job_id, required: true, schema: { type: string } } ]
      responses:
        "200": { description: OK, content: { application/json: { schema: { type: array, items: { $ref: '#/components/schemas/Artifact' } } } } }
  /jobs/{job_id}/extractions:
    get:
      summary: Devuelve JSON normalizado generado a partir de los PDFs
      security: [ { ApiKeyAuth: [] } ]
      parameters: [ { in: path, name: job_id, required: true, schema: { type: string } } ]
      responses:
        "200": { description: OK, content: { application/json: { schema: { type: array, items: { $ref: '#/components/schemas/ExtractionRecord' } } } } }
```

---

## 3) Repo Structure
```
scraper-service/
├─ app/
│  ├─ main.py                # FastAPI app, routes, auth middleware
│  ├─ deps.py                # DI helpers (redis, settings)
│  ├─ models.py              # pydantic models (requests/responses)
│  ├─ jobs.py                # enqueue helpers, status tracking
│  ├─ security.py            # API-key middleware, cookie encryption helpers
│  ├─ config.py              # settings (.env) via pydantic-settings
│  ├─ controllers/
│  │  ├─ login.py           # /login-session (Playwright headful)
│  │  ├─ jobs.py            # /start-job, /job-status, /results, /flush
│  ├─ scraping/
│  │  ├─ base.py            # ScraperBase plugin interface
│  │  ├─ isapre_x.py        # First site plugin (to implement)
│  │  └─ utils.py           # parse helpers, regex normalizers
│  └─ workers/
│     ├─ worker.py          # RQ worker entrypoint
│     └─ tasks.py           # scrape_job(task)
├─ data/                    # dev outputs (gitignored)
│  ├─ sessions/
│  ├─ results/
│  └─ logs/
├─ tests/
│  ├─ test_api.py
│  ├─ test_tasks.py
│  └─ test_normalize.py
├─ docker-compose.yml
├─ Dockerfile
├─ requirements.txt
├─ .env.example
├─ .gitignore
└─ README.md
```

---

## 4) Environment & Secrets
- **.env.example**
```
API_KEY=replace-me
REDIS_URL=redis://redis:6379/0
RESULT_TTL_SECONDS=172800   # 48h
SESSION_TTL_SECONDS=3600    # 1h
LOG_LEVEL=INFO
HEADFUL_LOGIN=true          # open real browser for captcha
```
- **Secrets**: Use env vars locally; in Railway/Upstash set environment variables. Never commit real secrets.
- **.gitignore**: include `data/` and any cookie/result dumps.

---

## 5) Docker Compose (dev)
```yaml
version: "3.9"
services:
  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
    ports: ["8080:8080"]
    env_file: .env
    depends_on: [redis]
    volumes: ["./:/workspace"]

  worker:
    build: .
    command: rq worker scraper-queue
    env_file: .env
    depends_on: [redis]
    volumes: ["./:/workspace"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

**Notes**
- For Playwright headful login in containers, local dev might run the login command outside Docker or use X11/WSL. For MVP, run `/login-session` locally on a dev machine (not in CI) to open a visible browser.

---

## 6) Core Stubs (to implement)

### 6.1 `app/scraping/base.py`
```python
from typing import Any, Dict, Iterable, List

class ScraperBase:
    site_id: str

    def login_via_context(self, page, username: str, password: str) -> None:
        """Navigate login page (fields, submit). User will solve CAPTCHA manually in the visible browser."""
        raise NotImplementedError

    def discover_documents(self, page, params: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        """Luego del login, recorre la UI y devuelve diccionarios con info de cada PDF (url, nombre, tipo, metadata)."""
        raise NotImplementedError

    def extract(self, pdf_path: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Procesa un PDF ya descargado y devuelve registros normalizados."""
        raise NotImplementedError

    def postprocess(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transformaciones adicionales (regex, mappings). Opcional."""
        return records
```

### 6.2 `app/workers/tasks.py`
```python
from typing import Dict
from redis import Redis
from .pipeline import PipelineCoordinator

def enqueue_pipeline(job_id: str, payload: Dict, redis: Redis):
    """
    Construye un PipelineCoordinator y despacha la primera etapa.
    Cada Stage actualizará el estado en Redis y registrará metadata en la Repository.
    """
    coordinator = PipelineCoordinator(job_id=job_id, redis=redis, payload=payload)
    coordinator.start()
```

### 6.3 `app/controllers/jobs.py` (outline)
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from uuid import uuid4
from app.deps import get_redis, get_queue, get_repository
from app.repositories import JobRepository

router = APIRouter()

class CreateJobBody(BaseModel):
    client_id: str
    site_id: str
    params: dict = {}
    stages: list[str] | None = None

@router.post("/jobs", status_code=202)
def create_job(body: CreateJobBody, redis=Depends(get_redis), q=Depends(get_queue), repo: JobRepository = Depends(get_repository)):
    job_id = str(uuid4())
    payload = body.model_dump()
    repo.register_job(job_id=job_id, payload=payload)
    redis.set(f"job:{job_id}:status", JobRepository.initial_status())
    q.enqueue("app.workers.tasks.enqueue_pipeline", job_id, payload)
    return {"job_id": job_id, "status": "PENDING"}

@router.get("/jobs/{job_id}")
def job_status(job_id: str, redis=Depends(get_redis), repo: JobRepository = Depends(get_repository)):
    status = redis.get(f"job:{job_id}:status")
    if not status:
        raise HTTPException(404, "Unknown job")
    details = repo.get_job(job_id)
    return {**status, **details}

@router.get("/jobs/{job_id}/artifacts")
def list_artifacts(job_id: str, repo: JobRepository = Depends(get_repository)):
    return repo.list_artifacts(job_id)

@router.get("/jobs/{job_id}/extractions")
def list_extractions(job_id: str, repo: JobRepository = Depends(get_repository)):
    return repo.list_extractions(job_id)
```

---

## 7) Redis Keys & TTL
- `session:{session_token}` → cookies JSON (TTL **1h**)
- `job:{job_id}:status` → `{status, stage, progress, message, started_at?, finished_at?}`
- `job:{job_id}:stage:{stage_name}` → eventos/progreso detallado de cada etapa (TTL configurable)
- `pipeline:locks:{job_id}` → opcional para evitar etapas duplicadas

---

## 8) Normalization Guide (example)
- Input raw fragments (HTML tables → dicts) → apply regex for:
  - **RUT**: `(?P<rut>\d{1,2}\.\d{3}\.\d{3}-[\dkK])`
  - **Money**: remove thousand separators, convert `1.234.567` → `1234567` (watch locale)
  - **Dates**: map `dd-mm-yyyy` → ISO `yyyy-mm-dd`
  - **Estado**: map labels (e.g., `Pagado`, `Pendiente`, `Rechazado`) → enum
- Output final `Record`: `{ fecha, numero_bono, rut_paciente, monto, estado, raw? }`

---

## 9) Security
- **Auth**: Header `X-API-Key` (single tenant per platform). Rotate keys via env.
- **HTTPS**: enforce in deployments.
- **Secrets**: env vars (Railway/Upstash). Never commit credentials.
- **Data at rest**: Optional AES encrypt cookies before Redis if required.
- **Access control**: Only the Spring backend calls this API (no direct user calls).

---

## 10) Local Dev & Runbook
**Prereqs:** Python 3.11, Docker, Playwright instalado localmente (navegador visible).

```bash
# 1) Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install
python -m playwright install-deps  # según SO

# 2) Start infra
docker compose up -d redis

# 3) Run API
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# 4) Run worker
rq worker scraper-queue

# 5) Flow
curl -H 'X-API-Key: $API_KEY' -X POST http://localhost:8080/jobs \
  -d '{"client_id":"c1","site_id":"isapre-x","params":{"from":"2024-01-01"}}'
# → returns { job_id }

curl -H 'X-API-Key: $API_KEY' http://localhost:8080/jobs/{job_id}
curl -H 'X-API-Key: $API_KEY' http://localhost:8080/jobs/{job_id}/artifacts
curl -H 'X-API-Key: $API_KEY' http://localhost:8080/jobs/{job_id}/extractions
```

### Login manual via Playwright (opcional)
```bash
python scripts/manual_login.py  # abre Chromium headful
# -> autentícate, resuelve reCAPTCHA, vuelve a la terminal y presiona Enter
# -> se genera data/sessions/latest_cookies.json
```
Usa el JSON resultante como parte del payload del job:
```json
{
  "client_id": "c1",
  "site_id": "isapre-x",
  "params": { "from": "2024-01-01" },
  "auth": { "cookies_file": "data/sessions/latest_cookies.json" }
}
```

---

## 11) Testing & QA
- **Unit tests:**
  - normalizadores (regex → RUT, fechas, montos)
  - helpers de estado Redis y coordinator
  - storage provider local (escritura/lectura, hash)
- **Pipeline (mock):**
  - `discover_documents()` con HTML de ejemplo que devuelve URLs controladas
  - stage de descarga usando storage fake para validar metadata guardada
  - extractor procesando PDFs en `tests/fixtures/pdfs` y produciendo JSON esperado
- **Manual:**
  - job end-to-end sobre el sitio real: confirmar descarga en `./data/pdfs/{job_id}` y JSON disponible vía API/Repositorio.

**Accept Criteria**
- Pipeline ejecuta login → navegación → descarga → extracción sin errores tras el login manual.
- PDFs quedan guardados localmente con metadata accesible en `/jobs/{id}/artifacts`.
- JSON normalizado disponible en `/jobs/{id}/extractions`.
- Redis solo guarda sesiones y estado/progreso con TTL definidos.
- No secrets en repo; `data/` gitignored.

---

## 12) First Site Plugin: `isapre_x`
**Inputs needed from Daniel** (pueden llegar después):
- `LOGIN_URL`, `DASHBOARD_URL`, pasos de navegación hasta llegar al módulo de PDFs.
- Selectores: `username`, `password`, `submit`, indicadores de sesión, menús, filtros, tabla/lista de documentos.
- Patrones ASPX relevantes: ids de formularios, manejo de `__VIEWSTATE`, `__EVENTVALIDATION`, triggers de `__doPostBack`, paneles con actualizaciones parciales.
- Patrones de nombre o tipos de PDF que necesitamos descargar.
- Reglas de extracción (tablas, campos clave, regex para totales, etc.).
- HTMLs y PDFs de ejemplo (anonimizados) para armar fixtures.

---

## 13) Roadmap (Milestones / PRs)
1) Scaffold API mínimo (FastAPI, Redis, RQ, settings, auth) + servicios abstractos (StorageProvider, MetadataRepository).  
2) Pipeline coordinator + stages stub (login/navegar/descargar/extraction) con reporting en Redis.  
3) Implementar login headful y navegación real para descubrir PDFs (`isapre_x`).  
4) Descarga real (httpx) y almacenamiento local de PDFs + metadata.  
5) Extractor inicial que convierta PDFs a JSON estructurado + normalización.  
6) Endpoints de consulta (`/jobs`, `/artifacts`, `/extractions`) y tests (unit, pipeline mock, integración).  
7) Documentación/runbook, manejo de reintentos/timeouts y preparación para conectar futuros repositorios/almacenamientos.

---

## 14) Notes & Constraints
- Headful Playwright typically requires desktop environment. For dev, run on a machine with GUI; for prod, consider a separate “auth station” or remote login step.
- Keep selectors in plugin config to isolate site changes.
- Añadir backoff/delays en etapas de navegación y descarga para no saturar el sitio.
- Sitios ASPX suelen depender de formularios con `__VIEWSTATE` y postbacks; preferir automatización Playwright y capturar network calls antes de intentar replicar requests manualmente.
- Frameworks tipo Scrapy/Scrapli son útiles, pero aquí priorizamos Playwright headful porque necesitamos login interactivo y cargar controles ASPX; se pueden integrar más adelante para crawling adicional si aportan valor.

---

*End of Guide — Ready for Codex to implement.*
