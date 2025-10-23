# 🏥 Scraper Cruz Blanca

Sistema modular para scraping y extracción de datos de Isapres chilenas, con **validación robusta** que garantiza 100% de completitud.

## ✨ Características Principales

- ✅ **Validación automática** - Verifica que todos los PDFs se descargaron correctamente
- 🔄 **Reintentos inteligentes** - Recupera automáticamente descargas fallidas  
- 📊 **Métricas detalladas** - Reportes completos de éxito/fallo
- 🧩 **Módulos desacoplados** - Scraping y extracción independientes
- 🎯 **Proceso parametrizable** - Mes, año y prestador configurables

---

## 🚀 Inicio Rápido

### Instalación

```bash
# Instalar dependencias
pip install -r requirements.txt

# Instalar navegador Chromium
python -m playwright install chromium
```

### Uso Básico

```bash
# Proceso completo (scraping + validación + extracción)
python scripts/run.py --year 2025 --month ENERO

# Solo scraping
python scripts/scrape.py --year 2025 --month ENERO

# Solo extracción (requiere scraping previo)
python scripts/extract.py --input data/pdfs/enero_2025_xxx/ --output data/json/enero_2025.json
```

---

## 📊 Métricas de Éxito

El sistema genera un **reporte de validación completo** después de cada scraping:

```json
{
  "validation": {
    "passed": true,                    // ✅ TRUE solo si tasa >= 95% y sin corruptos
    "total_expected": 150,             // PDFs que debían descargarse
    "total_downloaded": 150,           // PDFs descargados exitosamente
    "success_rate": 100.0,             // Porcentaje de éxito
    "failed_records": [],              // Registros fallidos con detalles
    "corrupted_files": [],             // Archivos corruptos detectados
    "retry_successes": 5,              // PDFs recuperados en reintentos
    "total_size_bytes": 45678900       // Tamaño total descargado
  }
}
```

### Criterios de Validación

El proceso **solo continúa con extracción** si:
- ✅ Tasa de éxito >= 95%
- ✅ Sin archivos corruptos (< 1KB)
- ✅ Todos los registros tienen PDF asociado

Si la validación falla, el sistema se detiene y genera un reporte detallado.

---

## 📂 Estructura del Proyecto

```
scrapper-mvp/
├── scraper/                   # 🧩 Módulos de scraping y extracción
│   ├── cruzblanca.py         # Scraper Cruz Blanca (incluye selectores)
│   ├── isapre_x.py           # Placeholder para otros scrapers
│   ├── extractor.py          # Extracción de datos de PDFs
│   ├── orchestrator.py       # Coordinador del proceso completo
│   ├── models.py             # Modelos de datos (Pydantic)
│   └── base.py               # Clase base para scrapers
├── scripts/                   # 🎯 Scripts ejecutables
│   ├── scrape.py             # Scraping independiente
│   ├── extract.py            # Extracción independiente
│   └── run.py                # Proceso completo orquestado
├── data/                      # 💾 Datos generados
│   ├── pdfs/                 # PDFs descargados (por job_id)
│   ├── json/                 # JSONs extraídos
│   └── logs/                 # Logs, cookies y reportes
├── docs/                      # 📚 Documentación técnica
│   ├── exploracion/          # Exploración del sitio Cruz Blanca
│   ├── guias/                # Guías de implementación
│   └── evidence/             # Evidencia y reportes
├── requirements.txt
└── README.md                  # Este archivo
```

---

## 🔧 Uso Detallado

### 1. Proceso Completo (Recomendado)

Ejecuta scraping → validación → extracción automáticamente:

```bash
python scripts/run.py --year 2025 --month ENERO
```

**Con prestador específico:**
```bash
python scripts/run.py --year 2025 --month ENERO --prestador "76190254-7 - SOLUCIONES INTEGRALES"
```

**Saltar etapas:**
```bash
# Solo scraping (sin extracción)
python scripts/run.py --year 2025 --month ENERO --skip-extraction

# Solo extracción (requiere scraping previo)
python scripts/run.py --year 2025 --month ENERO --skip-scraping
```

### 2. Scraping Independiente

```bash
python scripts/scrape.py --year 2025 --month ENERO
```

**Entrada:**
- RUT del usuario (solicitado interactivamente)
- Contraseña (solicitada interactivamente)
- Resolver CAPTCHA manualmente en el navegador

**Salida:**
- PDFs: `data/pdfs/enero_2025_YYYYMMDD_HHMMSS/`
- Metadata: `data/results/enero_2025_YYYYMMDD_HHMMSS_results.json`
- Reporte de validación incluido en metadata

### 3. Extracción Independiente

```bash
python scripts/extract.py \
  --input data/pdfs/enero_2025_20251021_143022/ \
  --output data/json/enero_2025_extracted.json \
  --metadata data/results/enero_2025_20251021_143022_results.json
```

**Salida:**
- JSON estructurado con datos extraídos
- Validación de completitud

---

## 🔐 Proceso de Login

1. El script solicita **RUT y contraseña**
2. Se abre el navegador en modo visible (no headless)
3. **Usuario resuelve CAPTCHA manualmente** ⚠️
4. Script detecta login exitoso automáticamente
5. Continúa con el scraping

**Nota:** El CAPTCHA debe resolverse manualmente (no se puede automatizar por ToS de Google).

---

## 📖 Arquitectura

### Módulos Desacoplados

El sistema está diseñado con módulos independientes que se pueden ejecutar por separado:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Scraping  │ ──> │  Validación  │ ──> │ Extracción  │
└─────────────┘     └──────────────┘     └─────────────┘
      ↓                    ↓                     ↓
  Descarga PDFs      Verifica 100%        Genera JSON
```

### Flujo del Proceso

1. **Scraping** - `scraper/cruzblanca.py`
   - Login con CAPTCHA manual
   - Navegación y filtros
   - Descarga masiva de PDFs
   - Paginación automática
   - Reintentos en fallos

2. **Validación** - Automática
   - Cuenta PDFs esperados vs descargados
   - Verifica integridad (tamaño > 1KB)
   - Valida que cada registro tiene PDF
   - Genera reporte detallado

3. **Extracción** - `scraper/extractor.py`
   - Lee PDFs descargados
   - Extrae datos estructurados
   - Genera JSON con metadata
   - **Solo se ejecuta si validación pasa**

4. **Orquestación** - `scraper/orchestrator.py`
   - Coordina todo el proceso
   - Maneja flujo condicional
   - Genera reportes finales

---

## 🎯 Casos de Uso

### Caso 1: Scraping de Enero 2025 Completo

```bash
# Ejecutar proceso completo
python scripts/run.py --year 2025 --month ENERO

# Input manual:
👤 Ingresa tu RUT: 12345678-9
🔑 Ingresa tu contraseña: ****

# El navegador se abre → Resolver CAPTCHA
# Script continúa automáticamente

# Output:
📥 SCRAPING:
   Job ID: enero_2025_20251021_143022
   PDFs descargados: 156
   Tasa de éxito: 100.0%

🎯 VALIDACIÓN: ✅ EXITOSA

📤 EXTRACCIÓN:
   Archivos procesados: 156
   Extraídos: 156
   Tasa de éxito: 100.0%
   Archivo salida: data/json/enero_2025_20251021_143022_extracted.json
```

### Caso 2: Re-extraer con Mejores Parámetros

Si ya tienes los PDFs descargados y quieres re-extraer:

```bash
python scripts/extract.py \
  --input data/pdfs/enero_2025_20251021_143022/ \
  --output data/json/enero_2025_v2.json
```

### Caso 3: Validar Scraping Existente

Los resultados de scraping incluyen el reporte de validación:

```bash
cat data/results/enero_2025_20251021_143022_results.json | jq '.validation'
```

---

## 📚 Documentación Adicional

### Exploración del Sitio

- [Pasos de Exploración de Cruz Blanca](docs/exploracion/pasos_cruzblanca.md) - Cómo funciona el sitio, selectores, flujo de navegación
- [Hallazgos de Exploración](docs/exploracion/hallazgos.md) - Descubrimientos importantes, quirks del sitio

### Guías Técnicas

- [Guía de Implementación MVP](docs/guias/implementacion_mvp.md) - Arquitectura del sistema, decisiones de diseño

### Evidencia

- [Reporte Sistema Integrado](docs/evidence/sistema_integrado.md) - Evidencia de pruebas y resultados

---

## 🆘 Troubleshooting

### Error: "Validación fallida"

**Síntomas:** El proceso se detiene después del scraping con mensaje de validación fallida.

**Causas posibles:**
- Conexión interrumpida durante descarga
- PDFs corruptos
- Timeouts en el sitio

**Solución:**
1. Revisar reporte en `data/results/[job_id]_results.json`
2. Ver `validation.failed_records` para identificar problemas
3. Re-ejecutar el scraping para ese período

### Error: "No se encontraron PDFs"

**Causas posibles:**
- Período sin datos en Cruz Blanca
- Prestador incorrectamente escrito
- Credenciales inválidas

**Solución:**
1. Verificar que el período tiene datos en el sitio
2. Verificar formato del prestador: `"RUT - NOMBRE COMPLETO"`
3. Verificar credenciales

### CAPTCHA no se resuelve

**Solución:**
- El navegador debe permanecer abierto y visible
- Resolver el CAPTCHA manualmente
- El script esperará automáticamente (hasta 5 minutos)

---

## 🔮 Roadmap

- [ ] API REST para gatillar procesos remotamente
- [ ] Integración SFTP a Digital Ocean
- [ ] Extracción avanzada con OCR para PDFs escaneados
- [ ] Scrapers para otras Isapres
- [ ] Scheduling automático con cron
- [ ] Dashboard de monitoreo

---

## 🤝 Contribuciones

Para agregar un nuevo scraper:

1. Crear `scraper/nueva_isapre.py` heredando de `ScraperBase`
2. Implementar métodos requeridos
3. Agregar a `scraper/__init__.py`
4. Documentar selectores y flujo

---

## 📝 Notas Importantes

- ⚠️ **CAPTCHA manual obligatorio** - No se puede automatizar
- ✅ **Validación crítica** - No se extrae si validación falla
- 📊 **Métricas siempre disponibles** - En archivos `_results.json`
- 🔄 **Reintentos automáticos** - El scraper reintenta fallos automáticamente
- 🎯 **Tasa objetivo: 95%+** - Criterio de éxito estricto

---

## 📄 Licencia

[Especificar licencia]

## 📞 Contacto

Para dudas o problemas, revisar logs en `data/logs/` o consultar la documentación en `docs/`.
