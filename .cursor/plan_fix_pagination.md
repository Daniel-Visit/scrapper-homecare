# Plan: Corrección Final de Paginación

## Objetivo
Corregir paginación del scraper, consolidar scripts y ejecutar scraping completo de Febrero 2025 con 61+ PDFs sin errores.

---

## Paso 1: Mejorar Reset de Paginación
**Archivo:** `scraper/cruzblanca.py` línea ~506

**Cambio:**
```python
# ANTES:
await page_1_btn.first.click()
await asyncio.sleep(1)
print(f"    🔄 Paginación reseteada a página 1")

# DESPUÉS:
await page_1_btn.first.click()
await asyncio.sleep(2)  # Aumentar a 2s
await self.iframe.locator("#panelCuentas_CallBackPanel_gridCuentaMedica_DXMainTable tr[id*='DXDataRow']").first.wait_for(state="visible", timeout=5000)
print(f"    🔄 Paginación reseteada a página 1")
```

**Razón:** El test confirmó que el selector funciona, solo necesita más tiempo para que la tabla se recargue.

---

## Paso 2: Crear scripts/scrape.py Mejorado
**Acción:** Reemplazar `scripts/scrape.py` con versión basada en `run_scraper_simple.py`

**Características:**
- CLI con argumentos: `--year`, `--month`, `--prestador`
- Usa `CruzBlancaScraper` directamente
- Login manual en navegador
- Sin orchestrator

---

## Paso 3: Limpieza
**Eliminar:**
- `run_scraper_simple.py`
- `test_paginacion.py`
- `data/debug_test/`

---

## Paso 4: Ejecutar
```bash
python3.11 scripts/scrape.py --year 2025 --month FEBRERO --prestador "76190254-7 - SOLUCIONES INTEGRALES EN TERAPIA RESPIRATORIA LTDA"
```

**Esperado:**
- 7 enlaces procesados
- 61+ PDFs (19+15+12+10+3+1+1)
- Sin "ERROR CRÍTICO: Se esperaban 15 pero solo se descargaron 5"
- Tasa de éxito: 100%



