# 🧪 Guía de Testing del Microservicio

Esta guía te ayudará a testear cada componente del microservicio de forma incremental.

---

## 📋 Pre-requisitos

```bash
# 1. Instalar dependencias
pip install -r requirements-api.txt

# 2. Instalar Playwright (para el scraper)
python -m playwright install chromium
```

---

## FASE 2: Testing SFTP Client ✅ **EJECUTA ESTO AHORA**

### Test Automático

```bash
python api/test_sftp.py
```

**Qué hace este test:**
1. ✅ Verifica conexión a la SFTP API
2. ✅ Crea directorio de prueba: `/test_scraping_TIMESTAMP/`
3. ✅ Crea subdirectorios: `pdfs/`, `json/`, `reports/`, `metadata/`
4. ✅ Sube un archivo de texto de prueba
5. ✅ Lista archivos en el directorio
6. ✅ Descarga el archivo y verifica contenido
7. ✅ (Opcional) Limpia el directorio de prueba

**Resultado esperado:**
```
================================================================================
TESTING SFTP CLIENT
================================================================================

TEST 1: Health Check
--------------------------------------------------------------------------------
✅ SFTP API está funcionando

TEST 2: Crear Directorio
--------------------------------------------------------------------------------
Creando: /test_scraping_20251022_143022
✅ Directorio creado: {...}

TEST 3: Crear Subdirectorios
--------------------------------------------------------------------------------
✅ Creado: /test_scraping_20251022_143022/pdfs
✅ Creado: /test_scraping_20251022_143022/json
✅ Creado: /test_scraping_20251022_143022/reports
✅ Creado: /test_scraping_20251022_143022/metadata

TEST 4: Subir Archivo
--------------------------------------------------------------------------------
Subiendo: tmpXXXX.txt -> /test_scraping_20251022_143022/pdfs/test_file.txt
✅ Archivo subido: {...}

TEST 5: Listar Directorio
--------------------------------------------------------------------------------
✅ Archivos en /test_scraping_20251022_143022:
   - pdfs (0 bytes)
   - json (0 bytes)
   - reports (0 bytes)
   - metadata (0 bytes)

TEST 6: Descargar Archivo
--------------------------------------------------------------------------------
Descargando: /test_scraping_20251022_143022/pdfs/test_file.txt -> /tmp/sftp_test_download.txt
✅ Archivo descargado correctamente
   Contenido: Test file created at 2025-10-22...

TEST 7: Limpiar (Eliminar Directorio)
--------------------------------------------------------------------------------
⚠️  Deseas eliminar el directorio de prueba? (y/n): y
✅ Directorio eliminado: {...}

================================================================================
RESUMEN DE TESTS
================================================================================
✅ Pasados: 7/7
❌ Fallidos: 0/7

🎉 Todos los tests pasaron exitosamente!
✅ El cliente SFTP está listo para usar.
================================================================================
```

---

## Troubleshooting

### Error: "SFTP API no responde"

**Causa:** No hay conexión a internet o la SFTP API está caída.

**Solución:**
```bash
# Verificar conectividad
curl https://sftp-api-production.up.railway.app/healthz

# Debería responder:
# {"status":"ok"}
```

### Error: "Invalid API key"

**Causa:** El API key en `api/config.py` es incorrecto.

**Solución:**
1. Verificar el API key en `postman_collection.json`:
   ```json
   "api_key": "xs0*Zff7V6BemA3>r<["
   ```
2. Actualizar `api/config.py` si es necesario.

### Error: "httpx.ConnectTimeout"

**Causa:** Timeout de conexión (red lenta o API sobrecargada).

**Solución:**
- Reintentar el test
- Verificar tu conexión a internet

---

## FASE 3-4: Testing API Local (PRÓXIMO)

Una vez que el test SFTP pase, continuaremos con:

1. **Test de Health Check API**
   ```bash
   uvicorn api.main:app --reload
   curl http://localhost:8000/healthz
   ```

2. **Test de Worker RQ**
   ```bash
   # Terminal 1: Worker
   rq worker --url redis://localhost:6379
   
   # Terminal 2: Encolar job de prueba
   python -c "from rq import Queue; from redis import Redis; q = Queue(connection=Redis()); print(q.enqueue(lambda: 'Hello World'))"
   ```

3. **Test End-to-End Local**
   - Trigger scraping vía API
   - Resolver CAPTCHA manualmente
   - Ver logs del worker
   - Verificar archivos en SFTP

---

## FASE 7-8: Testing en Railway (FINAL)

Después del deploy:

1. **Test de API en producción**
   ```bash
   curl https://tu-app.railway.app/healthz
   ```

2. **Test de trigger desde Postman**
   - Importar collection
   - Configurar URL de Railway
   - Ejecutar request POST /trigger

3. **Monitoreo de logs**
   ```bash
   railway logs --service scraping-worker --tail
   ```

---

## 📊 Checklist de Validación

Marca cuando completes cada test:

### FASE 2: SFTP ✅
- [ ] `python api/test_sftp.py` pasa todos los tests
- [ ] Archivos se crean correctamente en SFTP
- [ ] Descarga funciona correctamente

### FASE 3-4: API Local (Pendiente)
- [ ] Health check responde
- [ ] Redis conecta correctamente
- [ ] Worker procesa jobs

### FASE 5-6: Integration Local (Pendiente)
- [ ] Scraper se ejecuta desde worker
- [ ] PDFs se suben a SFTP
- [ ] JSONs se generan y suben
- [ ] CSV consolidado se genera

### FASE 7-8: Producción (Pendiente)
- [ ] Deploy en Railway exitoso
- [ ] API responde en Railway
- [ ] Worker procesa jobs en Railway
- [ ] Archivos persisten en SFTP

---

## 🎯 Siguiente Paso

**Ejecuta ahora:**
```bash
python api/test_sftp.py
```

Y comparte el resultado conmigo. Si todos los tests pasan, continuaré con la FASE 3 (Task Worker).

Si algo falla, te ayudaré a debuggearlo. 🔍

