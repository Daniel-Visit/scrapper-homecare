# Guía de Deployment a Railway + Upstash

Esta guía te ayudará a deployar la API y el Worker del microservicio de scraping a Railway, usando Upstash Redis como cola de tareas.

## Prerequisitos

- ✅ Cuenta de Railway activa
- ✅ Upstash Redis ya configurado con URL: `redis://default:AVNlAAIncDJmOTkwN...@upright-dog-21349.upstash.io:6379`
- ✅ SFTP API ya deployada en Railway: `https://sftp-api-production.up.railway.app`
- ✅ Código pusheado a GitHub: `https://github.com/Daniel-Visit/scrapper-homecare`

## Arquitectura de Deployment

```
┌─────────────────┐
│  GitHub Repo    │
│  scrapper-mvp   │
└────────┬────────┘
         │
         ├──────────────────┬────────────────────┐
         │                  │                    │
         ▼                  ▼                    ▼
┌────────────────┐ ┌────────────────┐  ┌────────────────┐
│ Railway: API   │ │Railway: Worker │  │ Upstash Redis  │
│ (Web Service)  │ │ (Worker)       │  │ (Managed)      │
└───────┬────────┘ └────────┬───────┘  └────────┬───────┘
        │                   │                   │
        └───────────────────┴───────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │   SFTP API      │
                  │   (Railway)     │
                  └─────────────────┘
```

**NOTA IMPORTANTE:** El viewer (noVNC) NO se despliega en Railway porque requiere X11/VNC. Para testing con viewer remoto, se necesitará Digital Ocean o similar.

---

## Paso 1: Deploy del Servicio API

### 1.1 Crear Servicio en Railway

1. Ve a [railway.app](https://railway.app)
2. Click en **"New Project"**
3. Selecciona **"Deploy from GitHub repo"**
4. Elige el repositorio: `Daniel-Visit/scrapper-homecare`
5. Railway detectará el `Dockerfile` automáticamente

### 1.2 Configurar el Servicio API

**Nombre del servicio:** `scraper-api`

**Settings → Deploy:**
- Build Command: (dejar vacío, usa Dockerfile)
- Start Command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- Root Directory: `/` (dejar vacío)
- Dockerfile Path: `Dockerfile`

**Settings → Networking:**
- Generate Domain: **Activar** (generará URL pública como `scraper-api-production.up.railway.app`)

### 1.3 Configurar Variables de Entorno

**Variables → Raw Editor** (pegar todo junto):

```env
REDIS_URL=redis://default:AVNlAAIncDJmOTkwN2U1Y2ViMzE0NzE2ODJjMzI2NGY1NDIxOGRjM3AyMjEzNDk@upright-dog-21349.upstash.io:6379
SFTP_API_URL=https://sftp-api-production.up.railway.app
SFTP_API_KEY=xs0*Zff7V6BemA3>r<[}
SFTP_BASE_PATH=/scraping_data
API_KEY=scraping-homecare-2025-secret-key
DATABASE_PATH=/app/data/scraper.db
DATA_DIR=/app/data
ENVIRONMENT=production
VIEWER_HOST=viewer
```

### 1.4 Deploy y Verificar

1. Click en **"Deploy"** (o espera al autodeploy)
2. Monitorea los logs en la pestaña **"Deployments"**
3. Espera a que el servicio esté **"Active"** (círculo verde)

**Verificar que funciona:**

```bash
curl https://scraper-api-production.up.railway.app/healthz
```

**Respuesta esperada:**
```json
{
  "status": "healthy",
  "redis_status": "connected",
  "environment": "production"
}
```

---

## Paso 2: Deploy del Servicio Worker

### 2.1 Crear Segundo Servicio

1. En el mismo proyecto de Railway, click en **"+ New"**
2. Selecciona **"GitHub Repo"** nuevamente
3. Elige el mismo repositorio: `Daniel-Visit/scrapper-homecare`

### 2.2 Configurar el Servicio Worker

**Nombre del servicio:** `scraper-worker`

**Settings → Deploy:**
- Build Command: (dejar vacío, usa Dockerfile)
- Start Command: `python start_worker.py`
- Root Directory: `/`
- Dockerfile Path: `Dockerfile`

**Settings → Networking:**
- **NO generar dominio** (el worker no necesita URL pública)

### 2.3 Configurar Variables de Entorno

**Variables → Raw Editor** (pegar todo junto):

```env
REDIS_URL=redis://default:AVNlAAIncDJmOTkwN2U1Y2ViMzE0NzE2ODJjMzI2NGY1NDIxOGRjM3AyMjEzNDk@upright-dog-21349.upstash.io:6379
SFTP_API_URL=https://sftp-api-production.up.railway.app
SFTP_API_KEY=xs0*Zff7V6BemA3>r<[}
SFTP_BASE_PATH=/scraping_data
DATABASE_PATH=/app/data/scraper.db
DATA_DIR=/app/data
ENVIRONMENT=production
```

### 2.4 Deploy y Verificar

1. Click en **"Deploy"**
2. Monitorea los logs en **"Deployments"**

**Verificar en los logs:**

```
🔒 Usando SSL para conexión a Upstash Redis
✅ Connected to Redis successfully
📋 Redis URL: rediss://upright-dog...
🚀 Starting RQ worker on queue 'default'...
👷 Worker started, waiting for jobs...
*** Listening on default...
```

---

## Paso 3: Testing del Deployment

### 3.1 Test del Healthcheck

```bash
curl https://scraper-api-production.up.railway.app/healthz \
  -H "X-API-Key: scraping-homecare-2025-secret-key"
```

### 3.2 Test del Endpoint `/trigger` (Flow Original)

**NOTA:** Este endpoint usa credenciales (no viewer remoto):

```bash
curl -X POST https://scraper-api-production.up.railway.app/api/v1/scraping/trigger \
  -H "Content-Type: application/json" \
  -H "X-API-Key: scraping-homecare-2025-secret-key" \
  -d '{
    "client_id": "test-railway-001",
    "year": "2024",
    "month": "ENERO",
    "username": "TU_USUARIO_CRUZBLANCA",
    "password": "TU_PASSWORD_CRUZBLANCA",
    "prestador": "76190254-7 - SOLUCIONES INTEGRALES EN TERAPIA RESPIRATORIA LTDA"
  }'
```

**Respuesta esperada:**
```json
{
  "job_id": "enero_2024_1234567890",
  "message": "Job de scraping encolado exitosamente",
  "estimated_time_minutes": 15,
  "sftp_path": "/scraping_data/enero_2024_1234567890"
}
```

### 3.3 Monitorear el Worker

Ve a los logs del servicio `scraper-worker` en Railway y deberías ver:

```
default: api.tasks.run_pipeline(...)
🚀 INICIANDO PIPELINE - Job ID: enero_2024_...
PASO 1/3: SCRAPING
🔐 Iniciando scraping...
...
✅ SCRAPING COMPLETADO
PASO 2/3: EXTRACCIÓN
...
PASO 3/3: REPORTING
...
✅ Pipeline completado exitosamente
```

---

## Troubleshooting

### Worker no se conecta a Redis

**Síntoma:** Logs muestran `ConnectionError` o `Connection closed by server`

**Solución:**
1. Verificar que `REDIS_URL` tenga el protocolo correcto (`redis://` no `rediss://`)
2. El código en `start_worker.py` ya convierte automáticamente a `rediss://` para Upstash
3. Verificar que la URL de Upstash sea correcta

### API retorna 500 en `/healthz`

**Síntoma:** Curl retorna error 500

**Solución:**
1. Revisar logs de la API en Railway
2. Verificar que todas las variables de entorno estén configuradas
3. Verificar que `REDIS_URL` sea accesible

### Worker no procesa jobs

**Síntoma:** API encola jobs pero worker no los procesa

**Solución:**
1. Verificar que ambos servicios usen la **misma** `REDIS_URL`
2. Verificar logs del worker: debe mostrar "Listening on default..."
3. Reiniciar el servicio worker

### Errores de SFTP

**Síntoma:** Pipeline falla en subida de archivos

**Solución:**
1. Verificar que `SFTP_API_URL` y `SFTP_API_KEY` sean correctos
2. Probar el SFTP API directamente:
   ```bash
   curl https://sftp-api-production.up.railway.app/healthz
   ```

---

## Limitaciones del Deployment a Railway

### ❌ NO Incluido en Railway:

1. **Viewer (noVNC):** El viewer remoto requiere X11 y VNC, que Railway no soporta
2. **Endpoint `/api/v2/run`:** No funciona sin el viewer

### ✅ Funcionalidades Disponibles:

1. **Endpoint `/api/v1/scraping/trigger`:** Funciona con credenciales
2. **Worker RQ:** Procesa jobs en background
3. **SFTP Upload:** Sube archivos a SFTP API
4. **Extracción y Reporting:** Todo el pipeline funciona

### Alternativa: Hybrid Setup

Para usar el viewer remoto:

1. **Viewer:** Correr localmente con `docker-compose up viewer`
2. **API + Worker:** En Railway (como está ahora)
3. Usuario accede al viewer local → login → worker procesa en Railway

---

## Costos Estimados

- **Railway (2 servicios):** ~$10-15/mes (dependiendo del uso)
- **Upstash Redis:** $0 (free tier hasta 10,000 comandos/día)
- **SFTP API:** $0 (ya incluido en Railway)

**Total:** ~$10-15/mes

---

## Próximos Pasos (Opcional)

Para producción completa con viewer remoto:

1. **Digital Ocean Droplet:** $12/mes
   - Correr viewer + API + worker
   - Acceso público al viewer (noVNC)
   
2. **Render.com:** Plan web service
   - Similar a Railway pero soporta contenedores más complejos

---

## Comandos Útiles

### Ver logs en Railway:

```bash
# Desde Railway CLI (si instalado)
railway logs -s scraper-api
railway logs -s scraper-worker
```

### Redeploy:

1. Push cambios a GitHub → Autodeploy en Railway
2. O desde Railway Dashboard: **"Deployments"** → **"Redeploy"**

### Rollback:

1. En Railway Dashboard: **"Deployments"**
2. Encuentra el deployment anterior
3. Click en **"Redeploy"**

---

## Soporte

Si encuentras problemas:

1. Revisa los logs en Railway Dashboard
2. Verifica las variables de entorno
3. Prueba el healthcheck de cada servicio
4. Revisa el estado de Upstash Redis en su dashboard

¡Deployment completado! 🚀

