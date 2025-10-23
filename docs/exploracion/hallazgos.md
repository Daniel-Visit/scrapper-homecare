# 🎯 Hallazgos de la Exploración - Cruz Blanca Extranet

**Fecha:** 14 Oct 2024  
**Sitio:** https://extranet.cruzblanca.cl/login.aspx

---

## ✅ 1. PÁGINA DE LOGIN

**URL:** `https://extranet.cruzblanca.cl/login.aspx`

### Selectores identificados:
```python
username_input: "#LogAcceso_UserName"      # Campo RUT
password_input: "#LogAcceso_Password"       # Campo Clave
submit_button: "#LogAcceso_LoginImageButton"
```

### Características:
- ✅ Sitio ASPX con ViewState, EventValidation, ViewStateGenerator
- ✅ Tiene **reCAPTCHA** - debe resolverse manualmente
- ✅ Formulario POST estándar

---

## ✅ 2. DASHBOARD POST-LOGIN

**URL:** `https://extranet.cruzblanca.cl/Extranet.aspx`

### Usuario logueado capturado:
- Nombre: SEBASTIAN ROMERO REEVES
- RUT: 15370513-5

### Menú principal (3 secciones):
1. **ADMINISTRACION** (`#xbMenu_DXI0_`)
   - Usuarios

2. **PRESTADORES** (`#xbMenu_DXI1_`) ← **SECCIÓN PRINCIPAL**
   - Cuenta Medica Manual (`#xbMenu_DXI1i0_`)
   - Prestador Consulta (`#xbMenu_DXI1i1_`)
   - Rendiciones Web (`#xbMenu_DXI1i2_`)
   - Solicitud de Cobro (BHO) (`#xbMenu_DXI1i3_`)
   - Control Recepción Cuentas Electrónicas (`#xbMenu_DXI1i4_`)
   - **Consulta de Cuentas Médicas** (`#xbMenu_DXI1i5_`) ← **🎯 OBJETIVO**
   - Certificado Tributario (`#xbMenu_DXI1i6_`)

3. **MIS DATOS** (`#xbMenu_DXI2_`)
   - Cambiar Clave
   - Mis Mensajes
   - Perfil Usuario

---

## ✅ 3. PÁGINA DE CUENTAS MÉDICAS (DENTRO DE IFRAME)

**URL del iframe:** `https://prestadores.cruzblanca.cl/CuentaMedicaDirecta/CuentaMedica.aspx?ref=...`

### Estructura:
- El dashboard (`Extranet.aspx`) carga el contenido en un **iframe** (`#frame`)
- Todo el contenido real está DENTRO del iframe
- El iframe carga un subdominio diferente: `prestadores.cruzblanca.cl`

### Filtros disponibles:

| Filtro | Selector | Ejemplo |
|--------|----------|---------|
| Prestador | `#cmbEntidades` | "76190254-7 - SOLUCIONES INTEGRALES EN TERAPIA" |
| Año | `#cmdAgnos` | "2025" |
| Mes | `#cmdMeses` | "SEPTIEMBRE" |
| Botón | `#btnConsultar` | "Consultar" |

---

## ✅ 4. TABLA DE CUENTAS MÉDICAS

### Tabla principal:
```python
table_container: "#panelCuentas_CallBackPanel_gridCuentaMedica"
table: "#panelCuentas_CallBackPanel_gridCuentaMedica_DXMainTable"
rows: "tr.dxgvDataRow_Aqua"
```

### Columnas identificadas (12 columnas):

1. **Nro. Cuenta** - Ej: `104093062025`, `122174742025`
2. **Origen** - Ej: `CMX`
3. **Nro. Envío** - Ej: `2`, `1`
4. **Nro. Cobro** - Ej: `38`, `36`, `8`
5. **Estado** - Ej: `A Pago`
6. **Rut Afiliado** - Ej: `13227027-9`, `16474446-9`
7. **Beneficiario** - Nombre completo + RUT
8. **Diag. Primario** - Diagnóstico médico
9. **Fecha Pago** - Ej: `10-10-2025`
10. **Historial** 📄 - Icono documento (popup)
11. **Reporte Liquidacion** 📑 - Icono PDF ← **🎯 DESCARGAS**
12. **Imagenes** 🔗 - Enlace a imágenes

### Ejemplo de filas encontradas en la exploración:
- 8 cuentas médicas visibles en la captura
- Estado: todas "A Pago" (pagadas)
- Rango de fechas: Septiembre 2025

---

## ✅ 5. DESCARGA DE PDFs

### 🔥 Patrón de descarga identificado:

```html
<a href="javascript:void(0);" 
   onclick="AbrirImagen_ReporteLiquidacion('TgHfWPWsMtxo5JrGEj5iJw==', this)">
    <img src="img/pdf.png" alt="Reporte Liquidación" border="0">
</a>
```

### Características IMPORTANTES:

1. **NO hay href directo** - usa `javascript:void(0)`
2. **Descarga via onclick** - función JavaScript `AbrirImagen_ReporteLiquidacion()`
3. **Token único por PDF** - Base64 encode, ej: `'TgHfWPWsMtxo5JrGEj5iJw=='`
4. **Selector**: `a[onclick*='AbrirImagen_ReporteLiquidacion']`

### Tokens capturados (ejemplos):
```
TgHfWPWsMtxo5JrGEj5iJw==  (Cuenta: 104093062025)
T52J4S1T7clu0YesaTklKQ==  (Cuenta: 122174742025)
dSxULaYhaN08gbZdXhBt9w==  (Cuenta: 131717002025)
Ur4F+u6wP2s6W1KbJwbMTg==  (Cuenta: 179822742025)
pvhDq6LueiW1dNwvZ6g3/g==  (Cuenta: 180154772025)
qIWxbekdCyX8I+XoP6NIpg==  (Cuenta: 191824312025)
0VyhaNKziG1ed1mPU+G8Eg==  (Cuenta: 199585912025)
WIsMPfd2UBWb2mbepo9uWg==  (Cuenta: 200310152025)
```

### Estrategia de descarga:
1. **Opción A (Recomendada):** Usar Playwright para hacer click en cada enlace y capturar el download
2. **Opción B:** Interceptar requests de red después del click para obtener la URL real del PDF
3. **Opción C:** Reverse engineer la función JavaScript (más complejo)

---

## ✅ 6. PAGINACIÓN

### Controles detectados:
- **Grid DevExpress** con paginación integrada
- Selector container: `.dxgvPagerBottom_Aqua`
- Botón siguiente: `a.dxp-button[title*='Next']`
- Botón anterior: `a.dxp-button[title*='Prev']`
- Info de páginas: `.dxp-summary` (muestra "1-10 of 50")

---

## ✅ 7. OTROS ELEMENTOS

### Popup de Historial:
```html
<a onclick="AbrirHistorial('104093062025', '10', '38','1','76190254', this)">
    <img src="img/documento.png" width="25px" alt="Reporte Liquidación">
</a>
```
- Selector: `a[onclick*='AbrirHistorial']`
- Parámetros: (nro_cuenta, ?, nro_cobro, ?, rut_prestador, elemento)

### Tabla resumen:
- ID: `#panelResumen_CallBackPanel_1_gridCuentaMedicaResumen_DXMainTable`
- Muestra resumen agregado de cuentas

---

## 🎯 8. FLUJO DE AUTOMATIZACIÓN PROPUESTO

### Paso 1: Login
```python
1. Navegar a login.aspx
2. Ingresar RUT en #LogAcceso_UserName
3. Ingresar Clave en #LogAcceso_Password
4. Resolver reCAPTCHA manualmente (REQUERIDO)
5. Click en #LogAcceso_LoginImageButton
6. Esperar a que cargue Extranet.aspx
7. Verificar presencia de #lbNombreCliente (login exitoso)
8. Guardar cookies de sesión (TTL: ~1 hora)
```

### Paso 2: Navegación a Cuentas
```python
1. Hacer hover sobre #xbMenu_DXI1_ (PRESTADORES)
2. Click en #xbMenu_DXI1i5_ (Consulta de Cuentas Médicas)
3. Esperar a que cargue el iframe
4. Cambiar contexto al iframe #frame
```

### Paso 3: Aplicar filtros (opcional)
```python
1. Seleccionar prestador en #cmbEntidades
2. Seleccionar año en #cmdAgnos
3. Seleccionar mes en #cmdMeses
4. Click en #btnConsultar
5. Esperar a que se actualice la tabla
```

### Paso 4: Extraer metadata de la tabla
```python
1. Obtener todas las filas: tr.dxgvDataRow_Aqua
2. Para cada fila, extraer:
   - Nro. Cuenta (columna 0)
   - Origen (columna 1)
   - Estado (columna 4)
   - RUT Afiliado (columna 5)
   - Beneficiario (columna 6)
   - Diagnóstico (columna 7)
   - Fecha Pago (columna 8)
   - Token PDF del onclick (columna 10)
```

### Paso 5: Descargar PDFs
```python
1. Encontrar todos los enlaces: a[onclick*='AbrirImagen_ReporteLiquidacion']
2. Para cada enlace:
   a. Extraer el token del atributo onclick
   b. Click en el enlace
   c. Esperar la descarga del PDF
   d. Renombrar PDF con metadata (nro_cuenta, fecha, etc.)
   e. Guardar en ./data/pdfs/{job_id}/
```

### Paso 6: Paginación (si hay múltiples páginas)
```python
1. Verificar si existe botón "Next": a.dxp-button[title*='Next']
2. Si existe y está habilitado:
   a. Click en Next
   b. Esperar a que cargue nueva página
   c. Repetir extracción (Paso 4-5)
3. Repetir hasta que no haya más páginas
```

---

## 🔐 9. CONSIDERACIONES TÉCNICAS

### ASPX:
- Cada request debe incluir `__VIEWSTATE`, `__EVENTVALIDATION`, `__VIEWSTATEGENERATOR`
- Los postbacks cambian estos valores dinámicamente
- **Solución:** Usar Playwright headful para manejar automáticamente

### Cookies de sesión:
- Cookies capturadas en `/data/exploration/*.cookies.json`
- Duración estimada: ~1 hora
- **Reutilización:** Guardar en Redis con TTL para jobs subsecuentes

### Iframe:
- El contenido está en un iframe cross-origin (subdominio diferente)
- **Solución:** `page.frame_locator('#frame')` o `page.frames[1]`

### Descargas JavaScript:
- No son descargas directas via href
- **Solución:** Configurar `accept_downloads=True` en Playwright y capturar el evento download

---

## 📊 10. MÉTRICAS DE LA EXPLORACIÓN

- **Capturas realizadas:** 4
- **Páginas únicas capturadas:** 3 (login, dashboard, tabla de cuentas)
- **Tablas identificadas:** 2 (principal + resumen)
- **PDFs encontrados:** 8 enlaces en la captura
- **Filtros disponibles:** 3 (prestador, año, mes)
- **Archivos HTML:** ~11KB por iframe (contenido completo)
- **Screenshots:** 187KB-301KB

---

## ✅ 11. PRÓXIMOS PASOS

### Implementación del scraper:
1. ✅ Selectores documentados
2. ⏳ Implementar plugin `scraping/cruzblanca.py`
3. ⏳ Crear pipeline de login → navegación → extracción → descarga
4. ⏳ Manejar descargas JavaScript con Playwright
5. ⏳ Implementar paginación automática
6. ⏳ Extractor de PDFs (metadata + texto)
7. ⏳ Normalización a JSON estructurado

### Testing:
1. ⏳ Probar login manual y guardar cookies
2. ⏳ Probar reutilización de cookies (evitar login repetido)
3. ⏳ Probar descarga de 1 PDF
4. ⏳ Probar descarga masiva (todos los PDFs de una página)
5. ⏳ Probar paginación
6. ⏳ Probar con diferentes filtros (meses, años)

---

## 📁 Archivos capturados:

```
data/exploration/
├── 20251014_230511_001_tabla_cuentas_medicas_*
├── 20251014_230558_002_tabla_detalle_*
├── 20251014_230630_003_tabla_con_pdf_*
└── 20251014_230702_004_tabla_con_pdf_after_download_*
```

**Archivos clave para referencia:**
- `20251014_230630_003_tabla_con_pdf_iframe_1_*.html` - HTML completo con tabla y enlaces
- `20251014_230702_004_tabla_con_pdf_after_download_screenshot.png` - Screenshot visual

---

✅ **Exploración completada exitosamente**

