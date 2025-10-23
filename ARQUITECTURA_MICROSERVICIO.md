# Arquitectura del Microservicio de Scraping

## 📋 Tabla de Contenidos

1. [Visión General](#visión-general)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Diagramas de Secuencia](#diagramas-de-secuencia)
4. [Evolución: Navegador Remoto](#evolución-navegador-remoto)
5. [Stack Tecnológico](#stack-tecnológico)
6. [Opciones de Implementación](#opciones-de-implementación)
7. [API REST](#api-rest)
8. [Integración con Spring](#integración-con-spring)
9. [Despliegue en Railway](#despliegue-en-railway)
10. [Estructura de Archivos en SFTP](#estructura-de-archivos-en-sftp)
11. [Decisiones de Diseño](#decisiones-de-diseño)
12. [Plan de Migración](#plan-de-migración)

---

## 🎯 Visión General

El microservicio de scraping es un componente **independiente** que expone una API REST para automatizar el proceso de:

1. **Scraping** de PDFs desde Cruz Blanca
2. **Extracción** de datos estructurados (JSON)
3. **Generación** de reportes consolidados (CSV)

El microservicio opera en modo **"Fire and Forget"**:
- La aplicación Spring **gatilla** el proceso
- El microservicio **procesa en background**
- Los resultados se **guardan automáticamente en SFTP**
- Spring **lee los archivos** cuando los necesita

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│ APLICACIÓN SPRING (Cliente)                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Usuario: "Procesar Febrero 2025"                           │
│         │                                                    │
│         │ POST /api/v1/scraping/trigger                     │
│         │ {year: 2025, month: "FEBRERO", prestador: "..."} │
│         ▼                                                    │
│  RestTemplate.post(...)                                     │
│         │                                                    │
│         │ Response: 202 Accepted                            │
│         │ {job_id: "febrero_2025_xxx", message: "started"} │
│         ▼                                                    │
│  "Proceso iniciado, archivos disponibles en 5-10 min"      │
│                                                              │
│  ... (usuario espera 5-10 minutos) ...                     │
│                                                              │
│  Usuario: "Ver reporte Febrero"                            │
│         │                                                    │
│         ▼                                                    │
│  Lee desde SFTP o API:                                      │
│  GET /api/v1/files/febrero_2025/reports/consolidado.csv    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ HTTPS
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ MICROSERVICIO DE SCRAPING (Railway)                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ API REST (FastAPI)                                     │ │
│  │ - POST /trigger → Encola job, response inmediato      │ │
│  │ - GET /files/{path} → Download archivos (opcional)    │ │
│  │ - GET /completed → Lista jobs terminados (opcional)   │ │
│  └────────────────────────────────────────────────────────┘ │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Task Queue (Upstash Redis + RQ/Celery)                │ │
│  │ - Encola jobs                                          │ │
│  │ - Retry automático                                     │ │
│  │ - Persistencia                                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Background Workers                                     │ │
│  │                                                         │ │
│  │ Pipeline de 3 pasos:                                   │ │
│  │                                                         │ │
│  │ 1️⃣  SCRAPER (2-3 min)                                 │ │
│  │     - Playwright + Manual CAPTCHA                      │ │
│  │     - Descarga PDFs                                    │ │
│  │     - Guarda en SFTP: /pdfs/                          │ │
│  │                                                         │ │
│  │ 2️⃣  EXTRACTOR (1-2 min)                               │ │
│  │     - Lee PDFs desde SFTP                              │ │
│  │     - pdfplumber → JSON                                │ │
│  │     - Validación con schema                            │ │
│  │     - Guarda en SFTP: /json/                          │ │
│  │                                                         │ │
│  │ 3️⃣  REPORTER (30 seg)                                 │ │
│  │     - Lee JSONs desde SFTP                             │ │
│  │     - Genera CSV consolidado                           │ │
│  │     - Guarda en SFTP: /reports/                       │ │
│  │                                                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                         │                                    │
│                         ▼                                    │
│              Todos los archivos en SFTP                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ SFTP Protocol
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STORAGE (Digital Ocean SFTP)                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  /scraping_data/                                            │
│  ├── febrero_2025_1234567/                                  │
│  │   ├── pdfs/                                              │
│  │   │   ├── row_1_19_xxx.pdf                              │
│  │   │   ├── row_2_19_xxx.pdf                              │
│  │   │   └── ... (57 archivos)                             │
│  │   ├── json/                                              │
│  │   │   ├── row_1_19_xxx.json                             │
│  │   │   ├── row_2_19_xxx.json                             │
│  │   │   ├── ... (57 archivos)                             │
│  │   │   └── _reporte_extraccion.json                      │
│  │   ├── reports/                                           │
│  │   │   └── consolidado.csv                                │
│  │   └── metadata/                                          │
│  │       ├── job_info.json                                  │
│  │       └── scraping_metadata.csv                          │
│  ├── marzo_2025_1234568/                                    │
│  │   └── ...                                                │
│  └── abril_2025_1234569/                                    │
│      └── ...                                                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Diagramas de Secuencia

### Escenario A: Con Observabilidad (Polling de Estado)

En este escenario, Spring puede consultar el estado del proceso en tiempo real para mostrar progreso al usuario.

```
┌─────────┐     ┌─────────┐     ┌──────────────┐     ┌─────────┐     ┌─────────┐
│ Usuario │     │ Spring  │     │ Scraper API  │     │  Redis  │     │ Worker  │
└────┬────┘     └────┬────┘     └──────┬───────┘     └────┬────┘     └────┬────┘
     │               │                  │                  │               │
     │               │                  │                  │               │
     │ (1) Trigger   │                  │                  │               │
     │ "Procesar     │                  │                  │               │
     │  Febrero 2025"│                  │                  │               │
     ├──────────────►│                  │                  │               │
     │               │                  │                  │               │
     │               │ POST /api/v1/scraping/trigger      │               │
     │               │ {year, month, prestador}           │               │
     │               ├─────────────────►│                  │               │
     │               │                  │                  │               │
     │               │                  │ Enqueue job     │               │
     │               │                  ├─────────────────►│               │
     │               │                  │                  │               │
     │               │                  │ job_id created  │               │
     │               │                  │◄─────────────────┤               │
     │               │                  │                  │               │
     │               │ 202 Accepted     │                  │               │
     │               │ {job_id, status: "pending"}        │               │
     │               │◄─────────────────┤                  │               │
     │               │                  │                  │               │
     │ "Proceso      │                  │                  │               │
     │  iniciado...  │                  │                  │               │
     │  Job ID: XXX" │                  │                  │               │
     │◄──────────────┤                  │                  │               │
     │               │                  │                  │               │
     │               │                  │                  │ (2) Dequeue  │
     │               │                  │                  │◄──────────────┤
     │               │                  │                  │               │
     │               │                  │                  │               ├─┐
     │               │                  │                  │               │ │ (3) Scraping
     │               │                  │                  │               │ │ - Launch browser
     │               │                  │                  │               │ │ - Login (manual)
     │               │                  │                  │               │ │ - Download PDFs
     │               │                  │                  │               │◄┘
     │               │                  │                  │               │
     │               │                  │                  │ Update:      │
     │               │                  │                  │ "scraping"   │
     │               │                  │                  │◄──────────────┤
     │               │                  │                  │               │
     │               │ (4) Poll status  │                  │               │
     │               │ GET /api/v1/scraping/jobs/{job_id} │               │
     │               ├─────────────────►│                  │               │
     │               │                  │                  │               │
     │               │                  │ Get status       │               │
     │               │                  ├─────────────────►│               │
     │               │                  │                  │               │
     │               │                  │ {status, prog..} │               │
     │               │                  │◄─────────────────┤               │
     │               │                  │                  │               │
     │               │ 200 OK           │                  │               │
     │               │ {status: "scraping", progress: 30%}│               │
     │               │◄─────────────────┤                  │               │
     │               │                  │                  │               │
     │ (5) Show      │                  │                  │               │
     │ progress:     │                  │                  │               │
     │ "Descargando  │                  │                  │               │
     │  PDFs 30%"    │                  │                  │               │
     │◄──────────────┤                  │                  │               │
     │               │                  │                  │               │
     │               │                  │                  │               ├─┐
     │               │                  │                  │               │ │ (6) Upload PDFs
     │               │                  │                  │               │ │     to SFTP
     │               │                  │                  │               │◄┘
     │               │                  │                  │               │
     │               │                  │                  │ Update:      │
     │               │                  │                  │ "extracting" │
     │               │                  │                  │◄──────────────┤
     │               │                  │                  │               │
     │               │ (7) Poll status  │                  │               │
     │               ├─────────────────►│                  │               │
     │               │                  │ Get status       │               │
     │               │                  ├─────────────────►│               │
     │               │                  │ {status, prog..} │               │
     │               │                  │◄─────────────────┤               │
     │               │ {status: "extracting", progress: 60%}              │
     │               │◄─────────────────┤                  │               │
     │               │                  │                  │               │
     │ "Extrayendo   │                  │                  │               │
     │  datos 60%"   │                  │                  │               │
     │◄──────────────┤                  │                  │               │
     │               │                  │                  │               │
     │               │                  │                  │               ├─┐
     │               │                  │                  │               │ │ (8) Extract JSONs
     │               │                  │                  │               │ │     & Upload
     │               │                  │                  │               │◄┘
     │               │                  │                  │               │
     │               │                  │                  │ Update:      │
     │               │                  │                  │ "reporting"  │
     │               │                  │                  │◄──────────────┤
     │               │                  │                  │               │
     │               │                  │                  │               ├─┐
     │               │                  │                  │               │ │ (9) Generate CSV
     │               │                  │                  │               │ │     & Upload
     │               │                  │                  │               │◄┘
     │               │                  │                  │               │
     │               │                  │                  │ Update:      │
     │               │                  │                  │ "completed"  │
     │               │                  │                  │◄──────────────┤
     │               │                  │                  │               │
     │               │ (10) Poll status │                  │               │
     │               ├─────────────────►│                  │               │
     │               │                  │ Get status       │               │
     │               │                  ├─────────────────►│               │
     │               │                  │ {status: "comp"} │               │
     │               │                  │◄─────────────────┤               │
     │               │ {status: "completed", files: 57}    │               │
     │               │◄─────────────────┤                  │               │
     │               │                  │                  │               │
     │ "Proceso      │                  │                  │               │
     │  completado!  │                  │                  │               │
     │  Ver reporte" │                  │                  │               │
     │◄──────────────┤                  │                  │               │
     │               │                  │                  │               │
     │ (11) Click    │                  │                  │               │
     │ "Ver reporte" │                  │                  │               │
     ├──────────────►│                  │                  │               │
     │               │                  │                  │               │
     │               │ GET /api/v1/files/{job_id}/reports/consolidado.csv │
     │               ├─────────────────►│                  │               │
     │               │                  │                  │               │
     │               │                  ├─┐                │               │
     │               │                  │ │ Download       │               │
     │               │                  │ │ from SFTP      │               │
     │               │                  │◄┘                │               │
     │               │                  │                  │               │
     │               │ 200 OK [CSV]     │                  │               │
     │               │◄─────────────────┤                  │               │
     │               │                  │                  │               │
     │ [CSV File]    │                  │                  │               │
     │◄──────────────┤                  │                  │               │
     │               │                  │                  │               │
```

**Características:**
- ✅ Feedback en tiempo real al usuario
- ✅ Progress bar / spinner
- ✅ Detección de fallos inmediata
- ❌ Más complejo (polling cada 5s)
- ❌ Más requests HTTP

---

### Escenario B: Sin Observabilidad (Fire & Forget)

En este escenario (más simple), Spring solo gatilla el proceso y el usuario espera sin feedback.

```
┌─────────┐     ┌─────────┐     ┌──────────────┐     ┌─────────┐     ┌─────────┐
│ Usuario │     │ Spring  │     │ Scraper API  │     │  Redis  │     │ Worker  │
└────┬────┘     └────┬────┘     └──────┬───────┘     └────┬────┘     └────┬────┘
     │               │                  │                  │               │
     │               │                  │                  │               │
     │ (1) Trigger   │                  │                  │               │
     │ "Procesar     │                  │                  │               │
     │  Febrero 2025"│                  │                  │               │
     ├──────────────►│                  │                  │               │
     │               │                  │                  │               │
     │               │ POST /api/v1/scraping/trigger      │               │
     │               │ {year, month, prestador}           │               │
     │               ├─────────────────►│                  │               │
     │               │                  │                  │               │
     │               │                  │ Enqueue job     │               │
     │               │                  ├─────────────────►│               │
     │               │                  │                  │               │
     │               │                  │ job_id created  │               │
     │               │                  │◄─────────────────┤               │
     │               │                  │                  │               │
     │               │ 202 Accepted     │                  │               │
     │               │ {                │                  │               │
     │               │   job_id: "febrero_2025_xxx",      │               │
     │               │   message: "Proceso iniciado",     │               │
     │               │   estimated_time: "5-10 min",      │               │
     │               │   sftp_path: "/scraping_data/..."  │               │
     │               │ }                │                  │               │
     │               │◄─────────────────┤                  │               │
     │               │                  │                  │               │
     │ "Proceso      │                  │                  │               │
     │  iniciado.    │                  │                  │               │
     │  Los archivos │                  │                  │               │
     │  estarán      │                  │                  │               │
     │  disponibles  │                  │                  │               │
     │  en 5-10 min" │                  │                  │               │
     │◄──────────────┤                  │                  │               │
     │               │                  │                  │               │
     │   [FIN DE LA INTERACCIÓN]        │                  │               │
     │                                  │                  │               │
     │                                  │                  │               │
     │               │                  │                  │ (2) Dequeue  │
     │               │                  │                  │◄──────────────┤
     │               │                  │                  │               │
     │               │                  │                  │               ├─┐
     │               │                  │                  │               │ │ (3) SCRAPING
     │               │                  │                  │               │ │ - Launch Playwright
     │               │                  │                  │               │ │ - Login manual
     │               │                  │                  │               │ │ - Navegación
     │               │                  │                  │               │ │ - Download 57 PDFs
     │               │                  │                  │               │ │ - ~2-3 minutos
     │               │                  │                  │               │◄┘
     │               │                  │                  │               │
     │               │                  │                  │               ├─┐
     │               │                  │                  │               │ │ Upload to SFTP:
     │               │                  │                  │               │ │ /pdfs/*.pdf
     │               │                  │                  │               │◄┘
     │               │                  │                  │               │
     │               │                  │                  │               ├─┐
     │               │                  │                  │               │ │ (4) EXTRACTION
     │               │                  │                  │               │ │ - Read PDFs from SFTP
     │               │                  │                  │               │ │ - pdfplumber parse
     │               │                  │                  │               │ │ - Validate schema
     │               │                  │                  │               │ │ - Generate JSONs
     │               │                  │                  │               │ │ - ~1-2 minutos
     │               │                  │                  │               │◄┘
     │               │                  │                  │               │
     │               │                  │                  │               ├─┐
     │               │                  │                  │               │ │ Upload to SFTP:
     │               │                  │                  │               │ │ /json/*.json
     │               │                  │                  │               │◄┘
     │               │                  │                  │               │
     │               │                  │                  │               ├─┐
     │               │                  │                  │               │ │ (5) REPORTING
     │               │                  │                  │               │ │ - Read JSONs
     │               │                  │                  │               │ │ - Generate CSV
     │               │                  │                  │               │ │ - Consolidate data
     │               │                  │                  │               │ │ - ~30 segundos
     │               │                  │                  │               │◄┘
     │               │                  │                  │               │
     │               │                  │                  │               ├─┐
     │               │                  │                  │               │ │ Upload to SFTP:
     │               │                  │                  │               │ │ /reports/consolidado.csv
     │               │                  │                  │               │◄┘
     │               │                  │                  │               │
     │               │                  │                  │ Mark complete│
     │               │                  │                  │◄──────────────┤
     │               │                  │                  │               │
     │               │                  │                  │               │
     │   ... (5-10 minutos después) ...                   │               │
     │                                                     │               │
     │ (6) Usuario   │                  │                  │               │
     │ solicita      │                  │                  │               │
     │ "Ver reporte  │                  │                  │               │
     │  Febrero"     │                  │                  │               │
     ├──────────────►│                  │                  │               │
     │               │                  │                  │               │
     │               ├─┐                │                  │               │
     │               │ │ Read from SFTP │                  │               │
     │               │ │ /scraping_data/febrero_2025/     │               │
     │               │ │ reports/consolidado.csv          │               │
     │               │◄┘                │                  │               │
     │               │                  │                  │               │
     │ [CSV Data]    │                  │                  │               │
     │ + UI Table    │                  │                  │               │
     │◄──────────────┤                  │                  │               │
     │               │                  │                  │               │
```

**Características:**
- ✅ Máxima simplicidad
- ✅ Sin polling (menos requests)
- ✅ Menor carga en Redis
- ✅ Más escalable
- ❌ Sin feedback en tiempo real
- ❌ Usuario no sabe si falló hasta revisar SFTP

---

### Comparación de Escenarios

| Aspecto | Con Observabilidad | Sin Observabilidad |
|---------|-------------------|-------------------|
| **Complejidad** | Media | Baja |
| **Requests HTTP** | ~60-120 (polling cada 5s) | 2 (trigger + download) |
| **UX** | ⭐⭐⭐⭐⭐ (feedback en vivo) | ⭐⭐⭐ (espera ciega) |
| **Escalabilidad** | Media (más carga Redis) | Alta (stateless) |
| **Detección errores** | Inmediata | Diferida (al ver SFTP) |
| **Implementación** | API + Polling logic | Solo trigger |
| **Uso Redis** | Alto (updates frecuentes) | Bajo (solo queue) |

### Recomendación

**Fase 1 (MVP):** Implementar **Sin Observabilidad** (Escenario B)
- Más rápido de desarrollar
- Suficiente para usuarios técnicos
- Menos moving parts

**Fase 2 (Producción):** Agregar **Con Observabilidad** (Escenario A)
- Mejor UX
- Monitoreo de jobs
- Detección temprana de errores

---

## 🚀 Evolución: Navegador Remoto

### Visión a Futuro

La arquitectura actual (Fase 1) requiere que el usuario tenga Playwright instalado localmente y resuelva el CAPTCHA en su navegador local. La **arquitectura objetivo** elimina esta dependencia usando un **navegador remoto controlado por el backend**.

---

### Comparación: Estado Actual vs Estado Objetivo

| Aspecto | **Estado Actual (Fase 1)** | **Estado Objetivo (Fase 2+)** |
|---------|---------------------------|------------------------------|
| **Login/CAPTCHA** | Usuario abre navegador local | Usuario ve viewer del Chrome remoto |
| **Instalación** | Requiere Playwright local | Sin instalación en PC usuario |
| **Control** | Limitado | Backend tiene control total |
| **Sesión** | No se guarda | storageState reutilizable |
| **Headless** | No (requiere UI) | Sí (worker 100% headless) |
| **Escalabilidad** | 1 usuario a la vez | Múltiples sesiones paralelas |
| **Complejidad** | Baja | Media-Alta |
| **Infraestructura** | Solo Railway + Redis | + Navegador remoto (Browserless/self-host) |

---

### Arquitectura con Navegador Remoto

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ARQUITECTURA OBJETIVO - NAVEGADOR REMOTO                                │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ 1. USUARIO + SPRING                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Usuario                                                                 │
│     │                                                                    │
│     │ Clic "Procesar Febrero 2025"                                      │
│     ▼                                                                    │
│  Spring Backend                                                          │
│     │                                                                    │
│     │ POST /run                                                          │
│     │ {client_id, site_id, params}                                      │
│     ▼                                                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ HTTPS
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. SCRAPER API (FastAPI)                                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  POST /run                                                               │
│     │                                                                    │
│     ├─► Crear sesión Chrome remoto                                      │
│     │   (Browserless/Browserbase o self-host)                           │
│     │                                                                    │
│     ├─► Generar login_url (viewer)                                      │
│     │   https://viewer.sesion-remota/abc123                             │
│     │                                                                    │
│     └─► Response: {login_url, session_id}                               │
│                                                                          │
│  Spring recibe login_url                                                │
│     │                                                                    │
│     └─► Abre popup window(login_url)                                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. VIEWER (Popup) + CHROME REMOTO                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ Popup Window (viewer)                                    │           │
│  │ ┌────────────────────────────────────────────────────┐   │           │
│  │ │                                                     │   │           │
│  │ │   [Stream del Chrome Remoto via WebRTC/noVNC]     │   │           │
│  │ │                                                     │   │           │
│  │ │   ┌─────────────────────────────────────────┐     │   │           │
│  │ │   │ Cruz Blanca - Login                     │     │   │           │
│  │ │   │                                         │     │   │           │
│  │ │   │ Usuario: [____________]                 │     │   │           │
│  │ │   │ Clave:   [____________]                 │     │   │           │
│  │ │   │                                         │     │   │           │
│  │ │   │ [reCAPTCHA]                             │     │   │           │
│  │ │   │                                         │     │   │           │
│  │ │   │ [Iniciar Sesión]                        │     │   │           │
│  │ │   └─────────────────────────────────────────┘     │   │           │
│  │ │                                                     │   │           │
│  │ └────────────────────────────────────────────────────┘   │           │
│  └──────────────────────────────────────────────────────────┘           │
│                          │                                               │
│                          │ Usuario interactúa                            │
│                          │ (input + CAPTCHA)                             │
│                          ▼                                               │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ Chrome Remoto (Headful)                                  │           │
│  │ - Corriendo en servidor backend                          │           │
│  │ - Playwright conectado                                   │           │
│  │ - Scraper API controla TODO                              │           │
│  │ - Detecta login OK (URL/selector)                        │           │
│  └──────────────────────────────────────────────────────────┘           │
│                          │                                               │
│                          │ Login exitoso                                │
│                          ▼                                               │
│                   storageState()                                         │
│                   (cookies, localStorage)                                │
│                          │                                               │
└──────────────────────────┼───────────────────────────────────────────────┘
                           │
                           │ Guardar en Redis
                           │ (cifrado, TTL 1h)
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. WORKER (Headless con storageState)                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │ Pipeline Automatizado (100% headless)                       │        │
│  ├─────────────────────────────────────────────────────────────┤        │
│  │                                                              │        │
│  │  1️⃣  SCRAPING                                               │        │
│  │      - Playwright headless                                  │        │
│  │      - context.add_cookies(storageState)                    │        │
│  │      - Ya autenticado (no login)                            │        │
│  │      - Navega páginas privadas                              │        │
│  │      - Descarga PDFs (bytes en memoria)                     │        │
│  │      - Sube a SFTP: /pdfs/                                  │        │
│  │                                                              │        │
│  │  2️⃣  EXTRACTION                                             │        │
│  │      - Lee PDFs desde SFTP                                  │        │
│  │      - pdfplumber → JSON                                    │        │
│  │      - Validación schema                                    │        │
│  │      - Sube a SFTP: /json/                                  │        │
│  │                                                              │        │
│  │  3️⃣  REPORTING                                              │        │
│  │      - Consolida JSONs → CSV                                │        │
│  │      - Sube a SFTP: /reports/                               │        │
│  │      - Persiste en BD (PostgreSQL)                          │        │
│  │                                                              │        │
│  │  ✅ Pipeline completo sin intervención                       │        │
│  │                                                              │        │
│  └─────────────────────────────────────────────────────────────┘        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                    Datos finales en BD + SFTP
```

---

### Flujo Detallado con Navegador Remoto

```
┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌────────┐  ┌─────┐
│ Usuario │  │ Spring  │  │ Scraper  │  │  Viewer  │  │ Chrome  │  │ Worker │  │ DB  │
│         │  │         │  │   API    │  │ (Popup)  │  │ Remoto  │  │        │  │     │
└────┬────┘  └────┬────┘  └────┬─────┘  └────┬─────┘  └────┬────┘  └───┬────┘  └──┬──┘
     │            │             │             │             │            │          │
     │ (1) Clic   │             │             │             │            │          │
     │ "Procesar" │             │             │             │            │          │
     ├───────────►│             │             │             │            │          │
     │            │             │             │             │            │          │
     │            │ POST /run   │             │             │            │          │
     │            │ {params}    │             │             │            │          │
     │            ├────────────►│             │             │            │          │
     │            │             │             │             │            │          │
     │            │             │ (2) Create  │             │            │          │
     │            │             │ Remote      │             │            │          │
     │            │             │ Browser     │             │            │          │
     │            │             ├────────────────────────►  │            │          │
     │            │             │             │          Chrome          │          │
     │            │             │             │          launched        │          │
     │            │             │             │             │            │          │
     │            │             │ (3) Generate│             │            │          │
     │            │             │ login_url   │             │            │          │
     │            │             │ + session_id│             │            │          │
     │            │             │             │             │            │          │
     │            │ 202 Accepted│             │             │            │          │
     │            │ {login_url} │             │             │            │          │
     │            │◄────────────┤             │             │            │          │
     │            │             │             │             │            │          │
     │            │ (4) Open    │             │             │            │          │
     │            │ popup       │             │             │            │          │
     │            ├────────────────────────►  │             │            │          │
     │            │             │          window.open()    │            │          │
     │            │             │             │             │            │          │
     │ (5) Ve     │             │             │             │            │          │
     │ Chrome     │             │             │ WebRTC/     │            │          │
     │ remoto     │             │             │ noVNC       │            │          │
     │◄───────────────────────────────────────┼─────────────┤            │          │
     │            │             │             │ stream      │            │          │
     │            │             │             │             │            │          │
     │ (6) Input  │             │             │             │            │          │
     │ usuario +  │             │             │             │            │          │
     │ CAPTCHA    │             │             │             │            │          │
     ├────────────────────────────────────────┼────────────►│            │          │
     │            │             │             │          Login OK        │          │
     │            │             │             │             │            │          │
     │            │             │ (7) Detect  │             │            │          │
     │            │             │ login OK    │             │            │          │
     │            │             │◄────────────────────────────┤          │          │
     │            │             │ (URL/selector)             │          │          │
     │            │             │             │             │            │          │
     │            │             │ (8) Capture │             │            │          │
     │            │             │ storageState│             │            │          │
     │            │             ├────────────────────────►  │            │          │
     │            │             │             │          cookies         │          │
     │            │             │◄────────────────────────────┤          │          │
     │            │             │             │             │            │          │
     │            │             │ (9) Save to │             │            │          │
     │            │             │ Redis       │             │            │          │
     │            │             │ (encrypted) │             │            │          │
     │            │             │             │             │            │          │
     │            │             │ (10) Enqueue│             │            │          │
     │            │             │ Worker      │             │            │          │
     │            │             ├─────────────────────────────────────►  │          │
     │            │             │             │             │         {storageState}│
     │            │             │             │             │            │          │
     │ (11) Close │             │             │             │            │          │
     │ popup      │             │             │             │            │          │
     │◄───────────────────────────────────────┤             │            │          │
     │ "Procesando│             │          Close viewer      │            │          │
     │  en        │             │             │             │            │          │
     │  background"│            │             │             │            │          │
     │            │             │             │             │            │          │
     │            │             │             │             │            ├─┐        │
     │            │             │             │             │            │ │ (12)   │
     │            │             │             │             │            │ │ Scrape │
     │            │             │             │             │            │ │headless│
     │            │             │             │             │            │ │+storage│
     │            │             │             │             │            │◄┘        │
     │            │             │             │             │            │          │
     │            │             │             │             │            ├─┐        │
     │            │             │             │             │            │ │ (13)   │
     │            │             │             │             │            │ │Extract │
     │            │             │             │             │            │ │PDFs    │
     │            │             │             │             │            │◄┘        │
     │            │             │             │             │            │          │
     │            │             │             │             │            ├─┐        │
     │            │             │             │             │            │ │ (14)   │
     │            │             │             │             │            │ │Generate│
     │            │             │             │             │            │ │CSV     │
     │            │             │             │            │◄┘        │
     │            │             │             │             │            │          │
     │            │             │             │             │            │ (15)     │
     │            │             │             │             │            │ Persist  │
     │            │             │             │             │            ├─────────►│
     │            │             │             │             │            │   INSERT │
     │            │             │             │             │            │◄─────────┤
     │            │             │             │             │            │   OK     │
     │            │             │             │             │            │          │
     │   FIN - Datos en BD                   │             │            │          │
     │                                                                              │
```

---

### Ventajas del Navegador Remoto

#### 1. **Zero Install en Cliente**
- ❌ Ya no: "Instala Playwright en tu PC"
- ✅ Ahora: Solo navegador web estándar

#### 2. **Control Total del Backend**
- Backend controla 100% el navegador
- Puede debuggear, hacer screenshots, logs
- Puede reintentar automáticamente

#### 3. **Sesión Reutilizable**
- `storageState` se guarda en Redis
- Worker puede reusar la sesión (hasta expiración)
- Posibilidad de scraping recurrente sin re-login

#### 4. **Escalabilidad**
- Múltiples usuarios simultáneos
- Pool de navegadores remotos
- Aislamiento por sesión

#### 5. **Headless Real**
- Worker corre 100% headless
- Sin necesidad de UI en servidor
- Más rápido y eficiente

---

### Proveedores de Navegador Remoto

#### Opción A: Browserless/Browserbase (Gestionado)

**Browserless.io**
```
Pros:
- Setup en minutos
- Mantenimiento cero
- API simple
- WebSocket/noVNC built-in
- $79/mes (starter)

Contras:
- Costo recurrente
- Límites de concurrencia
```

**Browserbase**
```
Pros:
- Similar a Browserless
- Optimizado para Playwright
- $49/mes (starter)

Contras:
- Menos features de viewer
```

---

#### Opción B: Self-Host (Docker)

**Stack:**
```dockerfile
# docker-compose.yml
services:
  chrome-remote:
    image: browserless/chrome:latest
    ports:
      - "3000:3000"
    environment:
      - MAX_CONCURRENT_SESSIONS=10
      - CONNECTION_TIMEOUT=300000
    
  novnc:
    image: theasp/novnc:latest
    ports:
      - "8080:8080"
    depends_on:
      - chrome-remote
```

**Pros:**
- Sin costo (solo infra)
- Control total
- Sin límites

**Contras:**
- Mantenimiento
- Escalar manualmente
- Seguridad a cargo tuyo

---

### Implementación del Endpoint `/run`

```python
from fastapi import FastAPI
from playwright.async_api import async_playwright
import redis
import json

app = FastAPI()
redis_client = redis.from_url(REDIS_URL)

@app.post("/run")
async def run(payload: RunPayload):
    """
    Endpoint único que:
    1. Crea sesión Chrome remoto
    2. Retorna login_url
    3. Dispara pipeline en background
    """
    # 1. Crear sesión en proveedor remoto
    session = await create_remote_browser_session(
        client_id=payload.client_id,
        site_id=payload.site_id
    )
    
    login_url = session.viewer_url  # WebRTC/noVNC URL
    session_id = session.id
    
    # 2. Guardar session_id en Redis
    redis_client.setex(
        f"session:{session_id}",
        3600,  # 1 hora TTL
        json.dumps({"client_id": payload.client_id, "params": payload.params})
    )
    
    # 3. Disparar orquestador en background
    background_tasks.add_task(orchestrate, session_id, payload)
    
    # 4. Response inmediato
    return {
        "login_url": login_url,
        "session_id": session_id,
        "message": "Abrir popup y completar login. El proceso continúa automático."
    }

async def orchestrate(session_id: str, payload: RunPayload):
    """
    Orquestador que espera login OK y ejecuta pipeline
    """
    try:
        # 1. Esperar login exitoso (polling interno)
        storage_state = await wait_for_login_and_capture(
            session_id, 
            timeout_minutes=15
        )
        
        # 2. Guardar storageState cifrado en Redis
        encrypted_state = encrypt(json.dumps(storage_state))
        redis_client.setex(
            f"storage:{session_id}",
            3600,
            encrypted_state
        )
        
        # 3. Ejecutar pipeline con storageState
        await run_pipeline_with_storage(
            storage_state=storage_state,
            params=payload.params,
            client_id=payload.client_id
        )
        
    except TimeoutError:
        log.error(f"Login timeout para session {session_id}")
        # Notificar a usuario (webhook/email)
    
    finally:
        # 4. Cleanup
        await close_remote_browser_session(session_id)

async def wait_for_login_and_capture(session_id: str, timeout_minutes: int):
    """
    Polling interno: detecta login OK y captura storageState
    """
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(
            f"ws://browserless:3000?token={session_id}"
        )
        context = browser.contexts[0]
        page = context.pages[0]
        
        # Esperar señal de login OK
        # Opción 1: URL cambió
        # Opción 2: Selector específico aparece
        await page.wait_for_url("**/home.aspx", timeout=timeout_minutes*60*1000)
        
        # Capturar storageState
        storage_state = await context.storage_state()
        
        return storage_state

async def run_pipeline_with_storage(storage_state, params, client_id):
    """
    Worker headless con storageState inyectado
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Inyectar storageState
        context = await browser.new_context(storage_state=storage_state)
        page = await context.new_page()
        
        # Ya estamos autenticados!
        await page.goto("https://cruzblanca.cl/privado.aspx")
        
        # 1. Scrape PDFs
        pdfs = await scrape_pdfs(page, params)
        
        # 2. Extract
        jsons = [extract_pdf(pdf) for pdf in pdfs]
        
        # 3. Report + Persist
        csv = generate_csv(jsons)
        persist_to_db(jsons, csv, client_id)
        
        await browser.close()
```

---

### Seguridad del storageState

**Crítico:** `storageState` contiene cookies de sesión activas.

```python
from cryptography.fernet import Fernet

# En settings
ENCRYPTION_KEY = Fernet.generate_key()  # Guardar en env
cipher = Fernet(ENCRYPTION_KEY)

def encrypt(data: str) -> bytes:
    return cipher.encrypt(data.encode())

def decrypt(encrypted: bytes) -> str:
    return cipher.decrypt(encrypted).decode()

# Uso
encrypted_state = encrypt(json.dumps(storage_state))
redis_client.setex(f"storage:{session_id}", 3600, encrypted_state)

# Recovery
encrypted_state = redis_client.get(f"storage:{session_id}")
storage_state = json.loads(decrypt(encrypted_state))
```

**Medidas adicionales:**
- TTL corto (1 hora máx)
- Nunca exponer al frontend
- Rotar después de uso
- Logs de acceso

---

### Criterios de Aceptación (POC)

Para validar que la arquitectura funciona:

#### ✅ Fase POC
1. **Login Remoto**
   - Se abre popup con viewer
   - Usuario ve el Chrome remoto (no su navegador)
   - Puede interactuar (input + CAPTCHA)

2. **Captura de Sesión**
   - Backend detecta login OK
   - Captura `storageState` correctamente
   - Se guarda cifrado en Redis

3. **Worker Headless**
   - Worker headless se conecta con `storageState`
   - Accede a página privada (200 OK)
   - No necesita re-login

4. **Pipeline Completo**
   - Descarga al menos 1 PDF
   - Convierte a JSON
   - Guarda en BD
   - (Opcional) Sube a SFTP

#### ✅ Criterio de Éxito
- Usuario NO instala nada
- Proceso completo end-to-end
- Datos llegan a BD

---

## 🛠️ Stack Tecnológico

### Backend (Microservicio)

| Componente | Tecnología | Propósito |
|------------|------------|-----------|
| **API Framework** | FastAPI 0.109+ | Endpoints REST |
| **Web Scraping** | Playwright 1.42+ | Automatización browser |
| **PDF Parsing** | pdfplumber 0.10+ | Extracción de datos |
| **Task Queue** | RQ o Celery | Procesamiento async |
| **Broker** | Upstash Redis | Cola de tareas |
| **Storage** | SFTP (Digital Ocean) | Archivos |
| **Language** | Python 3.11 | Runtime |

### Infraestructura

| Servicio | Proveedor | Costo | Propósito |
|----------|-----------|-------|-----------|
| **Hosting** | Railway | Gratis ($5/mes crédito) | API + Workers |
| **Redis** | Upstash | Gratis (10K cmds/día) | Task queue |
| **SFTP** | Digital Ocean | Ya existente | File storage |

### Integración

| Componente | Tecnología |
|------------|------------|
| **Cliente** | Spring Boot + RestTemplate |
| **Protocolo** | HTTP/REST + SFTP |
| **Auth** | API Key (Header) |

---

## 📊 Opciones de Implementación

### Opción A: FastAPI BackgroundTasks (Simple)

**Características:**
- ✅ Built-in en FastAPI
- ✅ Zero dependencias extra
- ✅ Deploy más simple
- ❌ Sin persistencia de jobs
- ❌ Sin retry automático
- ❌ Si Railway reinicia, se pierden jobs en progreso

**Ideal para:**
- 1-2 usuarios
- Jobs poco frecuentes
- Máxima simplicidad

**Código:**
```python
from fastapi import FastAPI, BackgroundTasks

@app.post("/api/v1/scraping/trigger")
async def trigger(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_pipeline, job_id, year, month)
    return {"status": "started", "job_id": job_id}
```

---

### Opción B: RQ (Redis Queue) - **RECOMENDADA**

**Características:**
- ✅ Persistencia en Redis
- ✅ Retry automático
- ✅ Más ligero que Celery
- ✅ Fácil configuración
- ✅ Suficiente para la mayoría de casos

**Ideal para:**
- Múltiples usuarios
- Necesidad de retry
- Balance simplicidad/features

**Código:**
```python
from redis import Redis
from rq import Queue

redis_conn = Redis.from_url(UPSTASH_REDIS_URL)
queue = Queue(connection=redis_conn)

@app.post("/api/v1/scraping/trigger")
async def trigger():
    job = queue.enqueue(
        run_pipeline,
        job_id, year, month,
        job_timeout='30m'
    )
    return {"job_id": job_id, "task_id": job.id}
```

**Deploy:**
```bash
# Servicio 1: API
uvicorn app.main:app --host 0.0.0.0 --port $PORT

# Servicio 2: Worker
rq worker --url $UPSTASH_REDIS_URL
```

---

### Opción C: Celery (Robusto)

**Características:**
- ✅ Retry automático avanzado
- ✅ Scheduling (cron jobs)
- ✅ Monitoreo con Flower
- ✅ Chains y grupos de tasks
- ❌ Más complejo
- ❌ Más recursos

**Ideal para:**
- Producción enterprise
- Múltiples tipos de jobs
- Necesidad de scheduling

**Código:**
```python
from celery import Celery

celery_app = Celery(
    "scraping",
    broker=UPSTASH_REDIS_URL,
    backend=UPSTASH_REDIS_URL
)

@celery_app.task(bind=True)
def run_pipeline(self, job_id, year, month):
    # ...
    self.update_state(state='PROGRESS', meta={'progress': 50})
    # ...

@app.post("/api/v1/scraping/trigger")
async def trigger():
    task = run_pipeline.delay(job_id, year, month)
    return {"job_id": job_id, "task_id": task.id}
```

**Deploy:**
```bash
# Servicio 1: API
uvicorn app.main:app --host 0.0.0.0 --port $PORT

# Servicio 2: Worker
celery -A app.celery_app worker --loglevel=info
```

---

## 📡 API REST

### Endpoints

#### 1. Trigger Scraping (Principal)

```http
POST /api/v1/scraping/trigger
Content-Type: application/json
X-API-Key: your-api-key

{
  "year": 2025,
  "month": "FEBRERO",
  "prestador": "76190254-7 - SOLUCIONES INTEGRALES EN TERAPIA RESPIRATORIA LTDA"
}
```

**Response (202 Accepted):**
```json
{
  "job_id": "febrero_2025_1729634567",
  "message": "Proceso iniciado",
  "estimated_time_minutes": 5,
  "sftp_path": "/scraping_data/febrero_2025_1729634567/"
}
```

---

#### 2. Download Archivo (Opcional)

```http
GET /api/v1/files/{job_id}/reports/consolidado.csv
X-API-Key: your-api-key
```

**Response:** CSV file

---

#### 3. Listar Jobs Completados (Opcional)

```http
GET /api/v1/scraping/completed
X-API-Key: your-api-key
```

**Response:**
```json
[
  {
    "job_id": "febrero_2025_1729634567",
    "completed_at": "2025-02-15T10:30:00Z",
    "files_count": 57,
    "csv_url": "/api/v1/files/febrero_2025_1729634567/reports/consolidado.csv"
  },
  {
    "job_id": "marzo_2025_1729634890",
    "completed_at": "2025-03-10T14:20:00Z",
    "files_count": 45,
    "csv_url": "/api/v1/files/marzo_2025_1729634890/reports/consolidado.csv"
  }
]
```

---

## ☕ Integración con Spring

### Service Layer

```java
package com.empresa.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Service
@RequiredArgsConstructor
public class ScrapingService {
    
    private final RestTemplate restTemplate;
    
    @Value("${scraping.api.url}")
    private String scrapingApiUrl;
    
    @Value("${scraping.api.key}")
    private String apiKey;
    
    /**
     * Gatilla proceso de scraping (Fire & Forget)
     */
    public ScrapingResponse triggerScraping(
        int year, 
        String month, 
        String prestador
    ) {
        String url = scrapingApiUrl + "/api/v1/scraping/trigger";
        
        // Headers
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-API-Key", apiKey);
        
        // Body
        ScrapingRequest request = ScrapingRequest.builder()
            .year(year)
            .month(month)
            .prestador(prestador)
            .build();
        
        HttpEntity<ScrapingRequest> entity = new HttpEntity<>(request, headers);
        
        // POST request
        ResponseEntity<ScrapingResponse> response = restTemplate.postForEntity(
            url, 
            entity, 
            ScrapingResponse.class
        );
        
        if (response.getStatusCode().is2xxSuccessful()) {
            log.info("Scraping iniciado: {}", response.getBody().getJobId());
            return response.getBody();
        }
        
        throw new RuntimeException("Error al iniciar scraping: " + response.getStatusCode());
    }
    
    /**
     * Descarga CSV desde el microservicio
     */
    public byte[] downloadReport(String jobId) {
        String url = scrapingApiUrl + "/api/v1/files/" + jobId + "/reports/consolidado.csv";
        
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-API-Key", apiKey);
        
        HttpEntity<Void> entity = new HttpEntity<>(headers);
        
        ResponseEntity<byte[]> response = restTemplate.exchange(
            url,
            HttpMethod.GET,
            entity,
            byte[].class
        );
        
        return response.getBody();
    }
    
    /**
     * Lista jobs completados
     */
    public List<CompletedJob> listCompletedJobs() {
        String url = scrapingApiUrl + "/api/v1/scraping/completed";
        
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-API-Key", apiKey);
        
        HttpEntity<Void> entity = new HttpEntity<>(headers);
        
        ResponseEntity<CompletedJob[]> response = restTemplate.exchange(
            url,
            HttpMethod.GET,
            entity,
            CompletedJob[].class
        );
        
        return Arrays.asList(response.getBody());
    }
}
```

### DTOs

```java
@Data
@Builder
public class ScrapingRequest {
    private int year;
    private String month;
    private String prestador;
}

@Data
public class ScrapingResponse {
    private String jobId;
    private String message;
    private int estimatedTimeMinutes;
    private String sftpPath;
}

@Data
public class CompletedJob {
    private String jobId;
    private String completedAt;
    private int filesCount;
    private String csvUrl;
}
```

### Configuration

```java
@Configuration
public class RestConfig {
    
    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}
```

### application.yml

```yaml
scraping:
  api:
    url: https://scraping-api.railway.app
    key: ${SCRAPING_API_KEY}
```

---

## 🚀 Despliegue en Railway

### Estructura del Proyecto

```
scrapper-mvp/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app
│   ├── tasks.py          # RQ/Celery tasks
│   ├── config.py         # Settings
│   └── sftp.py           # SFTP client
├── scraper/
│   ├── cruzblanca.py     # Scraper
│   ├── extractor.py      # PDF extractor
│   ├── pdf_parser.py     # PDF parser
│   └── pdf_validator.py  # Validator
├── requirements.txt
├── Procfile              # Railway config
└── runtime.txt           # Python version
```

### Procfile

```procfile
# API Service
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT

# Worker Service (si usas RQ)
worker: rq worker --url $UPSTASH_REDIS_URL

# Worker Service (si usas Celery)
# worker: celery -A app.celery_app worker --loglevel=info
```

### requirements.txt

```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.0
pydantic-settings==2.1.0

# Queue (elegir una)
rq==1.16.0              # Opción simple
# celery==5.3.6         # Opción robusta

# Redis
redis==5.0.1

# Scraping & Extraction
playwright==1.42.0
pdfplumber==0.10.3

# SFTP
paramiko==3.4.0

# Utilities
python-dotenv==1.0.0
httpx==0.26.0
```

### Variables de Entorno en Railway

```bash
# API
PORT=8000
ENVIRONMENT=production

# Redis (Upstash)
UPSTASH_REDIS_URL=redis://default:xxx@xxx.upstash.io:6379

# SFTP (Digital Ocean)
SFTP_HOST=your-server.digitalocean.com
SFTP_PORT=22
SFTP_USER=your-username
SFTP_PASSWORD=your-password
SFTP_BASE_PATH=/scraping_data

# Security
API_KEY=your-secret-api-key

# Scraping
CAPTCHA_TIMEOUT=300
MAX_RETRIES=3
```

### Deploy

```bash
# 1. Instalar Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Init proyecto
railway init

# 4. Link a proyecto existente (si ya existe)
railway link

# 5. Deploy
railway up

# 6. Ver logs
railway logs
```

---

## 📁 Estructura de Archivos en SFTP

```
/scraping_data/
├── febrero_2025_1729634567/
│   ├── pdfs/
│   │   ├── row_1_19_xxx.pdf
│   │   ├── row_2_19_xxx.pdf
│   │   └── ... (57 archivos)
│   ├── json/
│   │   ├── row_1_19_xxx.json
│   │   ├── row_2_19_xxx.json
│   │   ├── ... (57 archivos)
│   │   └── _reporte_extraccion.json
│   ├── reports/
│   │   └── consolidado.csv
│   └── metadata/
│       ├── job_info.json
│       └── scraping_metadata.csv
├── marzo_2025_1729634890/
│   └── ...
└── abril_2025_1729635123/
    └── ...
```

### Nomenclatura de Jobs

```
{month}_{year}_{timestamp}

Ejemplos:
- febrero_2025_1729634567
- marzo_2025_1729634890
- abril_2025_1729635123
```

---

## 🎯 Decisiones de Diseño

### 1. Fire & Forget vs Polling

**Decisión:** Fire & Forget

**Razones:**
- ✅ Simplicidad en el frontend
- ✅ No requiere WebSockets
- ✅ SFTP es la fuente de verdad
- ✅ No necesita monitoreo en tiempo real
- ❌ Usuario debe esperar sin feedback

**Alternativa (futura):**
- Webhook a Spring cuando job completa
- Notificación al usuario vía email/push

---

### 2. RQ vs Celery

**Decisión:** RQ (recomendado)

**Razones:**
- ✅ Más simple que Celery
- ✅ Suficiente para el caso de uso
- ✅ Menos recursos
- ✅ Fácil de debuggear
- ✅ Retry automático

**Cuándo usar Celery:**
- Múltiples tipos de jobs complejos
- Necesidad de scheduling (cron)
- Monitoreo avanzado requerido

---

### 3. Storage: SFTP vs S3

**Decisión:** SFTP (Digital Ocean)

**Razones:**
- ✅ Ya existe en la infraestructura
- ✅ Spring ya tiene cliente SFTP
- ✅ Sin costo adicional
- ❌ Menos escalable que S3

**Migración futura a S3:**
- Sencilla (cambiar solo módulo de storage)
- Mantener SFTP como backup

---

### 4. Autenticación

**Decisión:** API Key en Header

**Implementación:**
```python
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key
```

**Alternativa futura:**
- JWT tokens
- OAuth2

---

### 5. Manejo de Errores

**Strategy:**
- Retry automático (3 intentos)
- Guardar logs en SFTP
- Estado del job en Redis
- Notificación de error (futuro)

```python
@queue.job('default', timeout='30m', result_ttl=86400, failure_ttl=86400)
def run_pipeline(job_id, year, month, prestador):
    try:
        # 1. Scraping
        result = scraper.run(...)
        
        # 2. Extraction
        jsons = extractor.run(...)
        
        # 3. Report
        csv = reporter.run(...)
        
        # Guardar estado
        save_job_status(job_id, "completed")
        
    except Exception as e:
        log.error(f"Job {job_id} failed: {e}")
        save_job_status(job_id, "failed", error=str(e))
        raise
```

---

## 📈 Roadmap Futuro

### Fase 1: MVP (Actual)
- [x] Scraper funcional
- [x] Extractor con validación
- [x] Generador de reportes CSV
- [ ] API REST básica
- [ ] Deploy en Railway

### Fase 2: Producción
- [ ] Queue con RQ
- [ ] Retry automático
- [ ] Logs estructurados
- [ ] Métricas básicas

### Fase 3: Mejoras
- [ ] Webhook a Spring al completar
- [ ] Dashboard de monitoreo
- [ ] Scheduling automático (ej: cada mes)
- [ ] Multi-prestador en paralelo

### Fase 4: Escalabilidad
- [ ] Migración a S3
- [ ] Cache de resultados
- [ ] API de búsqueda de liquidaciones
- [ ] Integración con DB (PostgreSQL)

---

## 🔧 Mantenimiento

### Logs

```bash
# Railway logs
railway logs --service scraping-api
railway logs --service scraping-workers

# Logs locales (desarrollo)
tail -f logs/scraping.log
```

### Debugging

```python
# Modo debug
import logging
logging.basicConfig(level=logging.DEBUG)

# Test SFTP
python -m app.sftp --test

# Test scraper
python -m scraper.cruzblanca --year 2025 --month FEBRERO
```

### Monitoreo

```bash
# Ver jobs en Redis
redis-cli -u $UPSTASH_REDIS_URL
> KEYS *
> GET job:123456

# RQ dashboard
rq info --url $UPSTASH_REDIS_URL
```

---

## 📋 Plan de Migración

### Estado Actual del Sistema

El sistema actual tiene los siguientes componentes funcionales:

```
FASE ACTUAL (Local + Manual)
─────────────────────────────
✅ Scraper Cruz Blanca (scraper/cruzblanca.py)
   - Playwright local
   - Login manual en navegador local
   - Descarga PDFs a data/pdfs/
   - Extrae tabla a CSV

✅ PDF Extractor (scraper/pdf_parser.py + extractor.py)
   - Parse con pdfplumber
   - Validación con JSON schema
   - 100% success rate (57/57 PDFs)

✅ Report Generator (scripts/generate_report.py)
   - Consolida JSONs → CSV
   - Calcula totales

✅ CLI Scripts
   - scripts/scrape.py (solo scraping)
   - scripts/extract_batch.py (solo extracción)
```

**Limitaciones actuales:**
- Requiere instalación local de Playwright
- No es una API (solo CLI)
- Sin SFTP (solo filesystem local)
- Sin persistencia en BD
- 1 usuario a la vez
- Sin observabilidad

---

### Roadmap de Migración

#### Fase 1: API Básica (1-2 semanas)
**Objetivo:** Convertir CLI a API REST con "Fire & Forget"

**Cambios:**
```
1. Crear FastAPI app (api/main.py)
2. Implementar endpoints:
   - POST /api/v1/scraping/trigger
   - GET /api/v1/files/{job_id}/reports/{filename}
3. Integrar RQ para tasks asíncronas
4. Conectar Upstash Redis
5. Deploy en Railway (2 servicios: API + Worker)
```

**Arquitectura Fase 1:**
```
Usuario → Spring → Scraper API → Redis Queue → Worker
                                                   ↓
                                          Local filesystem
                                          (data/pdfs, data/json)
```

**Mantiene:**
- ✅ Login manual en navegador local
- ✅ Playwright local
- ✅ Filesystem local

**Agrega:**
- ✅ API REST
- ✅ Task queue
- ✅ Deploy en cloud

**Criterio de éxito:**
- Spring puede gatillar el proceso via POST
- Worker procesa en background
- API retorna archivos generados

---

#### Fase 2: SFTP Integration (1 semana)
**Objetivo:** Mover archivos de filesystem local a SFTP

**Cambios:**
```
1. Implementar SFTP client (usando postman_collection.json)
2. Modificar Worker para subir archivos:
   - PDFs → /scraping_data/{job_id}/pdfs/
   - JSONs → /scraping_data/{job_id}/json/
   - CSV → /scraping_data/{job_id}/reports/
3. Implementar endpoint para download desde SFTP
4. (Opcional) Mantener cache local temporal
```

**Arquitectura Fase 2:**
```
Usuario → Spring → Scraper API → Redis Queue → Worker
                                                   ↓
                                             Local (temp)
                                                   ↓
                                                 SFTP
                                            (Digital Ocean)
```

**Mantiene:**
- ✅ Login manual en navegador local
- ✅ Playwright local

**Agrega:**
- ✅ Persistencia en SFTP
- ✅ Archivos centralizados
- ✅ Acceso desde Spring

**Criterio de éxito:**
- Worker sube todos los archivos a SFTP
- Spring puede descargar archivos desde SFTP
- Sin archivos huérfanos en local

---

#### Fase 3: PostgreSQL Persistence (1 semana)
**Objetivo:** Persistir datos estructurados en BD

**Cambios:**
```
1. Diseñar schema PostgreSQL:
   - tabla: scraping_jobs
   - tabla: extracted_data (JSON normalizado)
   - tabla: audit_logs
2. Implementar repository layer
3. Modificar Worker para persistir:
   - Metadata del job
   - Datos extraídos de JSONs
   - Logs y métricas
4. Agregar endpoints de query:
   - GET /api/v1/data/search?month=FEBRERO&year=2025
```

**Arquitectura Fase 3:**
```
Usuario → Spring → Scraper API → Redis Queue → Worker
                                                   ↓
                                             PostgreSQL
                                                   +
                                                 SFTP
```

**Mantiene:**
- ✅ Login manual en navegador local
- ✅ Playwright local
- ✅ SFTP para archivos

**Agrega:**
- ✅ BD relacional
- ✅ Queries sobre datos
- ✅ Auditoría

**Criterio de éxito:**
- Datos en BD con integridad referencial
- Spring puede consultar datos sin SFTP
- Dashboard básico de métricas

---

#### Fase 4: Navegador Remoto (2-3 semanas) ⭐
**Objetivo:** Eliminar dependencia de instalación local

**Cambios:**
```
1. Setup infraestructura navegador remoto:
   - Opción A: Browserless.io ($79/mes)
   - Opción B: Self-host Docker (chrome + noVNC)
2. Modificar endpoint /run:
   - Crear sesión Chrome remoto
   - Retornar login_url (viewer)
3. Implementar detección de login OK:
   - Polling en URL/selector
   - Captura de storageState
4. Modificar Worker:
   - Usar storageState en lugar de login manual
   - 100% headless
5. Implementar seguridad:
   - Cifrado de storageState
   - TTL de sesiones
```

**Arquitectura Fase 4 (OBJETIVO):**
```
Usuario → Spring → Scraper API → Chrome Remoto (viewer)
                        ↓                    ↓
                   Redis Queue         storageState
                        ↓                    ↓
                     Worker (headless con storage)
                        ↓
                  PostgreSQL + SFTP
```

**Elimina:**
- ❌ Instalación local de Playwright
- ❌ Login manual en navegador del usuario
- ❌ Dependencia de UI local

**Agrega:**
- ✅ Zero-install para usuarios
- ✅ Navegador controlado por backend
- ✅ Sesión reutilizable
- ✅ Multi-tenancy real
- ✅ Worker 100% headless

**Criterio de éxito:**
- Usuario solo ve popup con viewer
- Backend controla 100% navegador
- Worker procesa con storageState
- Sin instalaciones en PC usuario
- Múltiples usuarios simultáneos

---

#### Fase 5: Observabilidad (1 semana)
**Objetivo:** Feedback en tiempo real a usuarios

**Cambios:**
```
1. Implementar state tracking en Redis:
   - pending → scraping → extracting → reporting → completed
2. Agregar endpoints de estado:
   - GET /api/v1/scraping/jobs/{job_id}
3. Worker actualiza progreso:
   - % de PDFs descargados
   - % de JSONs procesados
4. Spring implementa polling cada 5s
```

**Arquitectura Fase 5:**
```
Usuario → Spring (polling cada 5s)
            ↓
       Scraper API (GET /jobs/{id})
            ↓
       Redis (job state)
            ↑
         Worker (actualiza estado)
```

**Agrega:**
- ✅ Progress bars
- ✅ ETA de finalización
- ✅ Detección temprana de errores
- ✅ UX mejorada

**Criterio de éxito:**
- Usuario ve progreso en tiempo real
- Spring muestra % de avance
- Errores se detectan inmediatamente

---

### Comparación de Fases

| Característica | Actual | Fase 1 | Fase 2 | Fase 3 | Fase 4 | Fase 5 |
|----------------|--------|--------|--------|--------|--------|--------|
| **API REST** | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Task Queue** | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **SFTP** | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| **PostgreSQL** | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| **Navegador Remoto** | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Zero Install** | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Observabilidad** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Multi-user** | ❌ | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ |
| **Complejidad** | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

### Decisión: Qué Fase Implementar

#### Recomendación por Contexto

**Si necesitas:**
- **MVP funcional rápido** → Fase 1 (API Básica)
- **Archivos centralizados** → Fase 2 (+ SFTP)
- **Queries sobre datos** → Fase 3 (+ PostgreSQL)
- **Producto SaaS escalable** → Fase 4 (+ Navegador Remoto)
- **UX premium** → Fase 5 (+ Observabilidad)

**Ruta sugerida para este proyecto:**
```
Actual → Fase 1 (2 semanas) → Validar con usuarios
              ↓
         Fase 2 (1 semana) → Deploy a producción limitada
              ↓
         Fase 3 (1 semana) → Queries y dashboards
              ↓
         Fase 4 (3 semanas) → Producto escalable
              ↓
         Fase 5 (1 semana) → UX final
```

**Total:** ~8-10 semanas para el producto completo

---

### Riesgos y Mitigaciones

#### Fase 1-3 (API + SFTP + BD)
**Riesgos:**
- Login manual sigue siendo bottleneck
- Solo 1 usuario simultáneo realista

**Mitigaciones:**
- Documentar flujo de login claramente
- Implementar colas (si user A usa, user B espera)

---

#### Fase 4 (Navegador Remoto)
**Riesgos:**
- Complejidad alta
- Debuggeo más difícil
- Costos de infraestructura

**Mitigaciones:**
- Empezar con Browserless.io (gestionado)
- POC pequeño antes de migración completa
- Mantener código local como fallback
- Logs exhaustivos + screenshots automáticos

---

#### Fase 5 (Observabilidad)
**Riesgos:**
- Carga adicional en Redis
- Polling consume requests

**Mitigaciones:**
- Usar WebSockets en lugar de polling (opcional)
- Caché de estados (actualizar cada 5s, no por request)
- Rate limiting en endpoints de estado

---

### Checklist Pre-Migración

Antes de iniciar Fase 1, asegurarse de:

```
✅ Documentación actual completa
   - ✅ README.md actualizado
   - ✅ EXTRACTOR_COMPLETADO.md existe
   - ✅ ARQUITECTURA_MICROSERVICIO.md creado

✅ Tests básicos
   - ✅ Scraper funciona con Febrero 2025
   - ✅ Extractor 100% success rate
   - ✅ CSV consolidado genera correctamente

✅ Backup del código actual
   - ✅ Git tag "v1-local-cli"
   - ✅ Branch "pre-api-migration"

✅ Infraestructura lista
   - ✅ Railway account
   - ✅ Upstash Redis account
   - ✅ Digital Ocean SFTP access
   - (Fase 3) PostgreSQL provisioning

✅ Spring preparado
   - ✅ Endpoints de trigger definidos
   - ✅ Auth (API key) diseñado
```

---

### Siguiente Paso Recomendado

**Acción inmediata:** Implementar Fase 1 (API Básica)

**Por qué:**
- Desbloquea integración con Spring
- No requiere cambios arquitectónicos grandes
- Mantiene scraper actual funcionando
- Railway/Upstash son gratis inicialmente
- ROI inmediato (Spring puede gatillar proceso)

**Tareas concretas:**
1. Crear `api/` directory
2. Implementar FastAPI app con `/trigger` endpoint
3. Integrar RQ + Upstash Redis
4. Deploy en Railway (proof of concept)
5. Probar end-to-end: Spring → API → Worker → archivos

**Estimado:** 1-2 semanas part-time

---

## 📝 Notas Finales

1. **CAPTCHA Manual:** El scraper requiere intervención manual para resolver el CAPTCHA de Cruz Blanca. Esto es intencional dado que el CAPTCHA es complejo.

2. **Tiempo de Procesamiento:** Estimado 5-10 minutos para ~60 PDFs. Ajustar `job_timeout` en RQ si es necesario.

3. **Límites de Upstash:** Free tier tiene 10K comandos/día. Suficiente para ~100 jobs/día. Monitorear uso.

4. **Railway Limits:** Plan gratuito tiene $5/mes de crédito. Suficiente para desarrollo. Considerar plan Pro ($5/mes) para producción.

5. **Nombres de PDFs:** Actualmente son aleatorios (`row_X_Y_HASH.pdf`). Para vincular con CSVs de metadata, considerar nombres determinísticos en el futuro.

---

## 📞 Contacto y Soporte

Para dudas sobre implementación, revisar:
- `EXTRACTOR_COMPLETADO.md` - Documentación del extractor
- `README.md` - Guía general del proyecto
- Logs en Railway

---

**Última actualización:** 2025-10-22
**Versión:** 2.0
**Estado:** Arquitectura completa con roadmap de migración en 5 fases

