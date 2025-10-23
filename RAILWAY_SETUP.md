# 🚂 Guía de Despliegue en Railway

Esta guía te llevará paso a paso para desplegar el microservicio de scraping en Railway.

---

## 📋 Pre-requisitos

Antes de comenzar, asegúrate de tener:
- ✅ Cuenta de GitHub
- ✅ Repositorio Git con el código
- ✅ Código funcionando localmente (tests pasando)

---

## PASO 1: Crear Cuenta en Upstash Redis (5 minutos)

Redis es necesario para la cola de tareas (RQ).

### 1.1 Registro

1. Ve a https://upstash.com
2. Click en "Sign Up" o "Get Started"
3. Regístrate con GitHub (recomendado) o email
4. Confirma tu email si es necesario

### 1.2 Crear Database Redis

1. Una vez logged in, click en "Create Database"
2. Configuración:
   - **Name:** `scraping-queue` (o el nombre que prefieras)
   - **Type:** `Regional`
   - **Region:** `us-east-1` (o el más cercano a ti)
   - **Eviction:** `allkeys-lru` (default)
   - **TLS:** ✅ Enabled (default)

3. Click "Create"

### 1.3 Copiar Connection String

1. En el dashboard de tu database, busca **"REST API"** tab
2. Copia el **"UPSTASH_REDIS_REST_URL"**
   - Se ve así: `redis://default:XXXX@us1-promoted-duck-12345.upstash.io:6379`

3. **Guárdalo en un lugar seguro** (lo necesitarás en Railway)

---

## PASO 2: Crear Cuenta en Railway (5 minutos)

### 2.1 Registro

1. Ve a https://railway.app
2. Click en "Start a New Project"
3. Regístrate con GitHub (RECOMENDADO)
   - Railway necesita acceso a tus repos para deployar

### 2.2 Plan Gratuito

Railway ofrece:
- ✅ **$5 USD de crédito gratis** cada mes
- ✅ Suficiente para desarrollo/testing
- ✅ No necesitas tarjeta de crédito inicialmente

---

## PASO 3: Desplegar el Microservicio (10 minutos)

### 3.1 Crear Proyecto en Railway

1. En Railway dashboard, click "New Project"
2. Selecciona "Deploy from GitHub repo"
3. Autoriza Railway a acceder a tus repos (si no lo hiciste antes)
4. Selecciona el repositorio `scrapper-mvp`

### 3.2 Configurar Variables de Entorno

Después de seleccionar el repo, Railway detectará automáticamente que es un proyecto Python.

**ANTES de deployar**, configura las variables de entorno:

1. Click en tu servicio (se llamará algo como "scrapper-mvp")
2. Ve a la pestaña **"Variables"**
3. Agrega las siguientes variables:

```bash
# API Configuration
API_KEY=tu-api-key-secreta-aqui-cambiala
ENVIRONMENT=production

# Redis (Upstash)
REDIS_URL=rediss://default:XXXX@us1-promoted-duck-12345.upstash.io:6379
# 👆 Pega aquí el URL que copiaste de Upstash
# ⚠️  Importante: Usa 'rediss://' (con doble 's') para SSL
# Si Upstash te da 'redis://', el código lo convertirá automáticamente

# SFTP API (Digital Ocean)
SFTP_API_URL=https://sftp-api-production.up.railway.app
SFTP_API_KEY=xs0*Zff7V6BemA3>r<[
SFTP_BASE_PATH=/scraping_data

# Scraping Configuration
CAPTCHA_TIMEOUT_SECONDS=300
MAX_RETRIES=3
JOB_TIMEOUT_MINUTES=30

# Paths
DATA_DIR=data
```

4. Click "Add" después de cada variable

### 3.3 Configurar Servicios

Railway necesita dos servicios (API + Worker):

#### Servicio 1: API (Web)

1. En tu proyecto, verás un servicio creado automáticamente
2. Renómbralo a `scraping-api`
3. En Settings:
   - **Start Command:** `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
   - **Build Command:** `pip install -r requirements-api.txt && python -m playwright install chromium`

#### Servicio 2: Worker (Background)

1. Click en "+ New Service"
2. Selecciona "Empty Service"
3. Nómbralo `scraping-worker`
4. Conecta al mismo repositorio
5. En Settings:
   - **Start Command:** `rq worker --url $REDIS_URL default`
   - **Build Command:** `pip install -r requirements-api.txt && python -m playwright install chromium`
6. **Importante:** Copia las mismas variables de entorno del servicio API

### 3.4 Deploy

1. Railway deployará automáticamente al hacer push a GitHub
2. Puedes forzar un redeploy con "Deploy" → "Redeploy"

### 3.5 Obtener URL de la API

1. Ve al servicio `scraping-api`
2. En la pestaña "Settings", busca **"Domains"**
3. Click "Generate Domain"
4. Railway te dará un dominio como: `scraping-api-production.up.railway.app`
5. **Guarda este URL** - es la URL de tu API

---

## PASO 4: Verificar que Funciona (5 minutos)

### 4.1 Health Check

Prueba que la API responde:

```bash
curl https://tu-dominio.railway.app/healthz
```

**Respuesta esperada:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "redis_connected": true
}
```

Si `redis_connected` es `false`, verifica tu `REDIS_URL`.

### 4.2 Ver Logs

Para ver qué está pasando:

1. En Railway, click en el servicio (API o Worker)
2. Ve a la pestaña **"Logs"**
3. Verás los logs en tiempo real

**Logs esperados del API:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Logs esperados del Worker:**
```
Worker rq:worker:xxx started, version 1.16.0
Subscribing to channel rq:worker:heartbeat:xxx
default: Job OK
```

---

## PASO 5: Probar el Endpoint (10 minutos)

### 5.1 Test con cURL

```bash
curl -X POST https://tu-dominio.railway.app/api/v1/scraping/trigger \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tu-api-key-secreta" \
  -d '{
    "year": 2025,
    "month": "FEBRERO",
    "prestador": null,
    "username": "12345678-9",
    "password": "tu-contraseña"
  }'
```

**Respuesta esperada (202 Accepted):**
```json
{
  "job_id": "febrero_2025_1729867543",
  "message": "Proceso iniciado. Resuelve el CAPTCHA en el navegador que se abrirá.",
  "estimated_time_minutes": 15,
  "sftp_path": "/scraping_data/febrero_2025_1729867543/"
}
```

### 5.2 Monitorear el Worker

1. Ve a la pestaña "Logs" del servicio `scraping-worker`
2. Deberías ver:
   ```
   🚀 INICIANDO PIPELINE - Job ID: febrero_2025_1729867543
   ================================================================
   📅 Período: FEBRERO 2025
   🏥 Prestador: TODOS
   👤 Usuario: 12345678-9
   ```

3. **Problema Conocido:** El navegador de Playwright no se puede abrir en Railway (sin GUI)
   - Esto se resolverá en Fase 4 del roadmap (Navegador Remoto)
   - Por ahora, el microservicio solo funciona localmente para el scraping

---

## 🐛 Troubleshooting

### Error: "redis.exceptions.ConnectionError"

**Causa:** `REDIS_URL` incorrecto o Redis no accesible.

**Solución:**
1. Verifica que copiaste el URL completo de Upstash
2. Asegúrate de que incluye el prefijo `redis://`
3. Verifica que tu cuenta Upstash esté activa

### Error: "playwright._impl._api_types.Error: Executable doesn't exist"

**Causa:** Chromium no se instaló correctamente.

**Solución:**
1. Verifica que el Build Command incluya:
   ```
   python -m playwright install chromium
   ```
2. Redeploy el servicio

### Error: "No module named 'api'"

**Causa:** El working directory no es correcto.

**Solución:**
1. Asegúrate de que el código está en la raíz del repo
2. Verifica que `api/` es un directorio en la raíz

### Servicio se detiene después de unos minutos

**Causa:** Railway para servicios inactivos en el plan gratuito.

**Solución:**
- Es normal en el plan gratuito
- El servicio se reinicia automáticamente cuando recibe una request
- Para mantenerlo siempre activo, considera el plan Pro

---

## 📊 Costos Estimados

### Plan Gratuito ($5/mes de crédito)

Uso estimado para desarrollo:
- API (web): ~$2/mes
- Worker: ~$2/mes
- Total: ~$4/mes

✅ Cubre perfectamente el uso de desarrollo/testing

### Plan Pro ($5/mes + uso)

Para producción:
- $5/mes base
- + ~$5-10/mes de uso
- Total: ~$10-15/mes

---

## 🎉 ¡Listo!

Tu microservicio está deployado en Railway. Ahora puedes:

1. **Integrar con Spring:** Usa el URL de Railway en tu aplicación Spring
2. **Monitorear logs:** Ve los logs en tiempo real en Railway
3. **Escalar:** Railway escala automáticamente según demanda

**URL de tu API:** `https://tu-dominio.railway.app`
**Swagger docs:** `https://tu-dominio.railway.app/docs`

---

## 📞 Soporte

Si algo no funciona:
1. Revisa los logs en Railway (pestaña "Logs")
2. Verifica las variables de entorno
3. Consulta la documentación de Railway: https://docs.railway.app

---

**Última actualización:** 2025-10-23
**Versión:** 1.0

