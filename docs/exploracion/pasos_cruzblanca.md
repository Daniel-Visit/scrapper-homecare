# 🔍 Guía de Exploración: Cruz Blanca Extranet

---

## 🧠 Memoria Viva (Actualizar en cada iteración)

### Hallazgos clave (navegación y DOM)
- **Iframe**: Contenido principal dentro de `#frame` → usar `page.frame_locator('#frame')`.
- **Ruta objetivo**: `Prestadores` → `Control Recepción Cuentas Electrónicas`.
- **Selectores DevExpress (filtros)**:
  - Año: `#cmdAgnos` (abrir con imagen/ícono, seleccionar por `get_by_role('cell', name=year)`)
  - Mes: `#cmdMeses` (selección por `get_by_role('cell', name=month)`)
  - Prestador: `#cmbEntidades_B-1Img` (abrir) + celda exacta del prestador.
  - Botón Consultar: `#btnConsultar` y fallback por texto `Consultar`.
- **Tabla Resumen**:
  - Columna objetivo: `Cuentas A Pago` → ordenable; enlaces con números > 0.
  - Paginación: `#panelResumen_CallBackPanel_1_gridCuentaMedicaResumen_DXPagerBottom`.
- **Tabla Detalle**:
  - Headers incluyen: `Nro. Cuenta`, `Rut Afiliado`, `Beneficiario`, `Diag. Primario`, `Fecha Pago`, `Estado`.
  - Enlace PDF: link con texto `Reporte Liquidación` y `onclick` con `AbrirImagen_ReporteLiquidacion('TOKEN')`.
  - Paginación: `#panelCuentas_CallBackPanel_gridCuentaMedica_DXPagerBottom`.

### Mejoras implementadas (robustez)
- Ordenamiento por `Cuentas A Pago` con reintentos (3) y verificación de icono.
- Procesamiento inmediato por página en tabla resumen para evitar referencias obsoletas tras paginación.
- Extracción completa de metadata por fila de la tabla detalle (headers dinámicos).
- Descarga de PDF con `expect_download` y validación de integridad (≥1KB) + eliminación de corruptos.
- Nombres de archivo únicos: `{NroCuenta}_{LinkText}_{token8}.pdf` y manejo de duplicados.
- Validación cruzada por enlace: compara esperados (con token) vs descargados; reintenta faltantes (2 intentos adicionales).
- Validación global final: estadísticas, integridad en disco, tasa de éxito y listado de fallos.
- Logs detallados y capturas de HTML/Screenshot cuando no se encuentran filas (debug rápido).
- Seguridad: sin imprimir credenciales; login manual con reCAPTCHA, navegador headful.

### Validaciones críticas
- Confirmar carga de dashboard por texto estable (no selector frágil).
- Confirmar que filtros aplican (mensajes de "No existe Cuentas Médicas" y estados visibles).
- Confirmar presencia de `onclick` esperado y extracción de token antes de descargar.
- Confirmar retorno a tabla resumen tras salir de detalle.

### Pendientes/Revisiones
- Mejorar heurística de detección de la tabla detalle (fallbacks por texto y estructura).
- Persistencia de resultados parciales por enlace (para resiliencia ante cierres inesperados).
- Modo estricto de cuotas: límite de PDFs (ej. 5) con verificación de conteo objetivo.

### Procedimiento Operativo (siempre seguir este orden)
1) Revisar el error en terminal/logs y, si aplica, abrir HTML/Screenshot de debug en `data/results/`.
2) Leer esta Memoria Viva (sección Hallazgos/Validaciones) y selectores en `config/cruzblanca_selectors.py`.
3) Pensar hipótesis concretas del fallo y el punto exacto del flujo.
4) Planificar cambios mínimos (selectores, waits, reintentos, flujo) y su validación.
5) Implementar y ejecutar el test (`test_5_pdfs.py`) verificando: conteo, integridad, metadata y tasa de éxito.

---

## ✅ Paso 1: Identificación inicial (COMPLETADO)

Ya capturamos la página de login y identificamos:

```python
LOGIN_SELECTORS = {
    "username_input": "#LogAcceso_UserName",      # Campo RUT
    "password_input": "#LogAcceso_Password",       # Campo Clave
    "submit_button": "#LogAcceso_LoginImageButton" # Botón submit
}
```

✅ Detectado: Sitio ASPX con ViewState, EventValidation, reCAPTCHA

---

## 📋 Paso 2: Exploración completa (SIGUIENTE)

### Ejecutar el script nuevamente:

```bash
SCRAPER_LOGIN_URL="https://extranet.cruzblanca.cl/login.aspx" \
/opt/homebrew/bin/python3.11 scripts/explore_site.py
```

### Flujo de exploración paso a paso:

#### 1️⃣ **Página de Login**
```bash
# El navegador se abre automáticamente
🔍 Comando: selectors
# → Confirma los selectores de username/password

🔍 Comando: capture login_page
# → Captura el estado inicial
```

#### 2️⃣ **Autenticación Manual**
- Ingresa tu RUT y contraseña en el navegador
- Resuelve el reCAPTCHA (si aparece)
- Click en "Iniciar sesión"
- **Espera a que cargue el dashboard**

```bash
🔍 Comando: capture post_login_dashboard
# → Captura la página después del login

🔍 Comando: links
# → Lista todos los enlaces/menús disponibles

🔍 Comando: cookies
# → Captura las cookies de sesión activa
```

**Qué buscar:**
- ✅ Menú de navegación principal
- ✅ Sección de "Bonos", "Facturas", "Documentos", "Liquidaciones"
- ✅ Indicador de usuario logueado (nombre, RUT visible)

#### 3️⃣ **Navegar a la Sección de Documentos**
En el navegador:
- Click en el menú que lleva a los documentos/PDFs que necesitas
- Puede ser "Bonos", "Liquidaciones", "Facturas", etc.

```bash
🔍 Comando: capture seccion_documentos
# → Captura la vista de la sección

🔍 Comando: tables
# → CRÍTICO: Analiza la estructura de las tablas

🔍 Comando: links
# → Busca los enlaces de descarga de PDFs

🔍 Comando: forms
# → Identifica filtros (fechas, tipos, etc.)
```

**Qué buscar:**
- ✅ Estructura de la tabla (headers: Fecha, Tipo, Nombre, etc.)
- ✅ Cómo están los enlaces de descarga (atributo href, onclick, etc.)
- ✅ Filtros disponibles (fecha desde/hasta, tipo de documento)
- ✅ Paginación o scroll infinito

#### 4️⃣ **Probar Descarga de un PDF**
- En el navegador, haz click en un enlace de descarga
- Observa qué sucede:
  - ¿Se descarga directamente?
  - ¿Abre una nueva pestaña/ventana?
  - ¿Hace un postback ASPX?

```bash
🔍 Comando: capture download_flow
# → Captura el estado durante/después de la descarga
```

#### 5️⃣ **Probar Filtros (si existen)**
- Usa los filtros de fecha o tipo
- Aplica el filtro
- Observa cómo se actualiza la tabla

```bash
🔍 Comando: capture filtered_results
# → Captura resultados filtrados

🔍 Comando: tables
# → Verifica estructura de la tabla filtrada
```

#### 6️⃣ **Paginación (si existe)**
- Si hay múltiples páginas de resultados
- Navega a la página 2

```bash
🔍 Comando: capture page_2
# → Captura segunda página
```

#### 7️⃣ **Finalizar**
```bash
🔍 Comando: quit
# → Cierra el navegador y guarda todo
```

---

## 📁 Archivos Generados

Después de la exploración completa tendrás:

```
data/exploration/
├── 20251015_HHMMSS_login_page.html
├── 20251015_HHMMSS_login_page.png
├── 20251015_HHMMSS_post_login_dashboard.html
├── 20251015_HHMMSS_post_login_dashboard.png
├── 20251015_HHMMSS_seccion_documentos.html     ← IMPORTANTE
├── 20251015_HHMMSS_seccion_documentos.png      ← IMPORTANTE
├── 20251015_HHMMSS_*_cookies.json              ← IMPORTANTES (sesión)
└── ...
```

---

## 🎯 Información Crítica a Capturar

### Para el Dashboard:
- [ ] Selector del menú de navegación principal
- [ ] Indicador de sesión exitosa (elemento que confirma login)
- [ ] Selector del enlace/botón a la sección de documentos

### Para el Listado de PDFs:
- [ ] Selector de la tabla principal
- [ ] Selectores de columnas (fecha, tipo, nombre)
- [ ] Selector de enlaces de descarga
- [ ] Atributos de los enlaces (href, onclick, data-*)
- [ ] Estructura de metadata visible (fechas, tipos, nombres)

### Para Filtros:
- [ ] Selectores de campos de filtro (fecha desde/hasta)
- [ ] Selector de tipo de documento (si es dropdown)
- [ ] Botón de aplicar filtros
- [ ] Mecanismo de submit (POST ASPX, AJAX, etc.)

### Para Descargas:
- [ ] URL pattern de los PDFs
- [ ] Parámetros requeridos (IDs, tokens, etc.)
- [ ] Tipo de autenticación (cookies, headers, etc.)

---

## 🔄 Después de la Exploración

Una vez que completes la exploración:

1. **Revisa los HTMLs capturados** en `data/exploration/`
2. **Actualiza** `config/cruzblanca_selectors.py` con los selectores reales
3. **Documenta** el flujo de navegación exacto
4. **Guarda** un ejemplo de PDF anonimizado para probar extracción

Luego podremos implementar el plugin `scraping/cruzblanca.py` con toda la información necesaria.

---

## ⚠️ Notas Importantes

- **Seguridad**: No compartas credenciales reales en los archivos capturados
- **Privacidad**: Los HTMLs pueden contener información sensible; no los subas a GitHub
- **reCAPTCHA**: Es normal que aparezca; resuélvelo manualmente
- **Sesión**: Las cookies capturadas son válidas ~1 hora
- **ASPX**: Los ViewStates cambian en cada request; no los hardcodees

---

## 💡 ¿Listo?

Ejecuta el comando y sigue el flujo paso a paso:

```bash
SCRAPER_LOGIN_URL="https://extranet.cruzblanca.cl/login.aspx" \
/opt/homebrew/bin/python3.11 scripts/explore_site.py
```

**Durante la exploración, tómate tu tiempo en cada sección y usa los comandos para capturar toda la información necesaria.**

---

## 🎯 **ESTRUCTURA EXACTA DE TABLA DETALLE - CODEGEN FINDINGS**

### **CRITICAL: Selectores exactos identificados via codegen (15/10/2025)**

**Tabla detalle usa estructura DevExpress específica:**

#### **Filas de datos:**
```python
# Patrón de filas: DXDataRow{i} donde i = número de fila
"#panelCuentas_CallBackPanel_gridCuentaMedica_DXDataRow0"  # Fila 0
"#panelCuentas_CallBackPanel_gridCuentaMedica_DXDataRow1"  # Fila 1
"#panelCuentas_CallBackPanel_gridCuentaMedica_DXDataRow10" # Fila 10
```

#### **Enlaces PDF específicos:**
```python
# Patrón: cell{i}_10_panelReportLiq_{i}
"#panelCuentas_CallBackPanel_gridCuentaMedica_cell1_10_panelReportLiq_1"   # PDF fila 1
"#panelCuentas_CallBackPanel_gridCuentaMedica_cell10_10_panelReportLiq_10" # PDF fila 10
```

#### **Paginación:**
```python
"#panelCuentas_CallBackPanel_gridCuentaMedica_DXPagerBottom"  # Controles paginación
# Números de página: .get_by_text("2"), .get_by_text("3"), etc.
```

#### **Celdas específicas:**
```python
"#panelCuentas_CallBackPanel_gridCuentaMedica_col11"  # Columna 11
# Celdas por contenido: .get_by_role("cell", name="122174742025")
```

### **IMPORTANTE:**
- **NO usar selectores genéricos** de tabla (`table`, `tr`, `td`)
- **SÍ usar estos IDs específicos** del codegen
- **Cada fila contiene metadata completa** (Nro. Cuenta, Beneficiario, Estado, etc.)
- **Cada fila tiene su enlace PDF correspondiente** con patrón específico
- **Paginación funciona** con controles DevExpress específicos

### **FLUJO COMPLETO IDENTIFICADO:**
1. **Login** → Dashboard
2. **Hover PRESTADORES** → Click "Control Recepción Cuentas"
3. **Filtros**: Prestador, Año (2025), Mes (SEPTIEMBRE)
4. **Ordenar** "Cuentas A Pago" (descendente)
5. **Click enlace** (ej: "36") → Abre tabla detalle
6. **Tabla detalle** tiene filas con patrón `DXDataRow{i}`
7. **Cada fila** tiene enlace PDF con patrón `cell{i}_10_panelReportLiq_{i}`
8. **Paginación** con controles `DXPagerBottom`
9. **Descargar PDFs** usando `page.expect_download()`

---

## 🔗 **URLs DE DESCARGA DIRECTA - DESCUBIERTAS (15/10/2025)**

### **FORMATO DE URL:**
```
https://prestadores.cruzblanca.cl/CuentaMedicaDirecta/LevantarPDF.aspx?origen=ReporteLiq&folioSPM={TOKEN}
```

### **EJEMPLO REAL:**
```
https://prestadores.cruzblanca.cl/CuentaMedicaDirecta/LevantarPDF.aspx?origen=ReporteLiq&folioSPM=NRyv355tJ9vAGMI8gMG8eA%3D%3D
```

### **CONVERSIÓN DE TOKEN:**
- **JavaScript**: `NRyv355tJ9vAGMI8gMG8eA==`
- **URL encoded**: `NRyv355tJ9vAGMI8gMG8eA%3D%3D`

### **IMPLICACIONES:**
- ✅ **Descarga directa** posible con URL
- ❓ **Requiere sesión activa** (cookies)
- ❓ **Tokens pueden expirar** (investigar TTL)
- 🎯 **Optimización**: Extraer tokens + descargar con requests

