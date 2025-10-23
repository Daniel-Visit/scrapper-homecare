"""
Plugin de scraping para Cruz Blanca Extranet.
Implementa el flujo completo: login → navegación → descarga de PDFs.
"""

import asyncio
import csv
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import Page, BrowserContext, Frame, Download

from scraper.base import ScraperBase
from config.cruzblanca_selectors import (
    LOGIN_URL, LOGIN_SELECTORS, DASHBOARD_SELECTORS, 
    PRESTADORES_SUBMENU, IFRAME_SELECTOR, CONTROL_RECEPCION_SELECTORS
)


class DebugLogger:
    """Sistema de logging autónomo con screenshots y HTML dumps."""
    
    def __init__(self, job_id: str):
        self.debug_dir = Path("data/debug") / job_id
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.events = []
    
    async def capture_state(self, page: Page, iframe: Frame, step_name: str, extra_data: dict = None):
        """Captura screenshot, HTML y datos del estado actual."""
        timestamp = time.time()
        
        try:
            # Screenshot
            screenshot = self.debug_dir / f"{step_name}_{timestamp:.0f}.png"
            await page.screenshot(path=screenshot)
            
            # HTML dump
            html_file = self.debug_dir / f"{step_name}_{timestamp:.0f}.html"
            try:
                html_content = await iframe.locator("#panelResumen_CallBackPanel_1").inner_html()
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
            except Exception as e:
                html_file = None
            
            # Event log
            event = {
                "timestamp": timestamp,
                "step": step_name,
                "screenshot": screenshot.name,
                "html": html_file.name if html_file else None,
                "data": extra_data or {}
            }
            self.events.append(event)
            
            return event
        except Exception as e:
            # Si falla la captura, al menos registrar el error
            event = {
                "timestamp": timestamp,
                "step": step_name,
                "error": str(e),
                "data": extra_data or {}
            }
            self.events.append(event)
            return event
    
    def save_report(self):
        """Guarda el reporte completo de eventos."""
        report_file = self.debug_dir / "debug_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.events, f, indent=2)
    
    def analyze_and_save(self):
        """Analiza el reporte y genera conclusiones automáticas."""
        if not self.events:
            return None
        
        analysis = {
            "total_eventos": len(self.events),
            "enlaces_procesados": 0,
            "errores": [],
            "cambios_tabla": [],
            "pdfs_totales": 0
        }
        
        # Detectar cambios en número de enlaces
        prev_count = None
        for event in self.events:
            if "error" in event:
                analysis["errores"].append({
                    "step": event["step"],
                    "error": event["error"]
                })
            
            if "enlaces_frescos" in event.get("data", {}):
                current = event["data"]["enlaces_frescos"]
                if prev_count is not None and current != prev_count:
                    analysis["cambios_tabla"].append({
                        "step": event["step"],
                        "anterior": prev_count,
                        "actual": current,
                        "diferencia": current - prev_count
                    })
                prev_count = current
            
            if "pdfs_descargados" in event.get("data", {}):
                analysis["pdfs_totales"] += event["data"]["pdfs_descargados"]
                analysis["enlaces_procesados"] += 1
        
        # Guardar análisis
        analysis_file = self.debug_dir / "analysis.json"
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2)
        
        return analysis


class CruzBlancaScraper(ScraperBase):
    """Scraper para Cruz Blanca Extranet."""
    
    site_id = "cruzblanca"
    
    def __init__(self, output_dir: Path = None):
        super().__init__()
        self.output_dir = output_dir or Path("data")
        self.pdf_dir = self.output_dir / "pdfs"
        self.results_dir = self.output_dir / "results"
        self.logs_dir = self.output_dir / "logs"
        
        # Crear directorios
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Variables de estado
        self.job_id = None
        self.context = None
        self.page = None
        self.iframe = None
        self.downloads = []
        self.logger = None  # Se inicializa cuando se establece job_id
        
    async def login_via_context(self, page: Page, username: str, password: str) -> None:
        """Realiza login en Cruz Blanca Extranet."""
        print(f"🔐 Iniciando proceso de login...")
        
        # Navegar a login
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=60000)
        print("✅ Página de login cargada")
        
        # IMPORTANTE: El usuario hace login manualmente
        print("⚠️  INICIA SESIÓN MANUALMENTE en el navegador:")
        print("   1. Ingresa tu RUT y contraseña")
        print("   2. Resuelve el CAPTCHA")
        print("   3. Presiona el botón de login")
        print("   El script detectará automáticamente cuando hayas iniciado sesión...")
        print()
        
        # Esperar a que el usuario haga login manualmente
        # Detectamos que ya inició sesión cuando la URL cambia a Extranet.aspx
        try:
            # Esperar hasta 5 minutos a que aparezca el dashboard (tiempo suficiente para login manual)
            await page.wait_for_url("**/Extranet.aspx", timeout=300000)
            print("✅ Login exitoso - Dashboard detectado")
            
            # Esperar a que cargue completamente
            await page.wait_for_load_state("networkidle", timeout=30000)
            
            # Intentar obtener el nombre del usuario
            try:
                user_name = await page.text_content(DASHBOARD_SELECTORS["user_name"])
                if user_name:
                    print(f"👤 Usuario: {user_name}")
            except:
                print("👤 Dashboard cargado")
                
        except Exception as e:
            print(f"⚠️  Timeout esperando el dashboard: {e}")
            print("⚠️  Asegúrate de haber iniciado sesión correctamente")
            raise
        
        # Guardar cookies para reutilizar
        if self.context:
            cookies = await self.context.cookies()
            cookies_file = self.logs_dir / f"{self.job_id}_cookies.json"
            cookies_file.write_text(json.dumps(cookies, indent=2))
            print(f"🍪 Cookies guardadas en: {cookies_file}")
        else:
            print("⚠️  Contexto no disponible para guardar cookies")
    
    async def navigate_to_accounts_section(self, page: Page = None) -> None:
        """Navega a la sección de Control Recepción Cuentas Electrónicas."""
        print("🧭 Navegando a Control Recepción Cuentas Electrónicas...")
        
        if page:
            self.page = page
        
        if not self.page:
            raise Exception("❌ Page no está inicializada")
        
        # Hacer hover sobre menú PRESTADORES para desplegar submenu
        print("🔄 Haciendo hover en menú Prestadores...")
        await self.page.hover(DASHBOARD_SELECTORS["menu_prestadores"])
        await asyncio.sleep(3)  # Esperar a que se despliegue
        
        # Verificar que el submenu es visible
        print("🔍 Verificando submenu...")
        try:
            await self.page.wait_for_selector(PRESTADORES_SUBMENU["control_recepcion"], state="visible", timeout=10000)
            print("✅ Submenu visible")
        except Exception as e:
            print(f"⚠️  Submenu no visible: {e}")
            # Intentar click directo en el menú principal
            await self.page.click(DASHBOARD_SELECTORS["menu_prestadores"])
            await asyncio.sleep(2)
        
        # Click en Control Recepción Cuentas Electrónicas
        print("🔄 Haciendo click en Control Recepción...")
        await self.page.click(PRESTADORES_SUBMENU["control_recepcion"])
        await asyncio.sleep(5)  # Esperar sin networkidle
        
        # Esperar a que cargue el iframe
        await self.page.wait_for_selector(IFRAME_SELECTOR, timeout=30000)
        
        # Cambiar contexto al iframe
        self.iframe = self.page.frame_locator(IFRAME_SELECTOR)
        print("✅ Navegación completada - iframe cargado")
    
    async def apply_filters(self, prestador: str = None, year: str = "2025", month: str = "SEPTIEMBRE") -> None:
        """Aplica filtros usando los selectores exactos de Playwright codegen."""
        print(f"🔍 Aplicando filtros: Prestador={prestador}, Año={year}, Mes={month}")
        
        # Esperar a que cargue el iframe
        await asyncio.sleep(2)
        
        # Seleccionar prestador
        if prestador:
            try:
                # Click en el input del prestador (selector correcto del codegen)
                await self.iframe.locator("#cmbEntidades_I").click()
                await asyncio.sleep(1)
                
                # Click en la opción del prestador (buscar por el texto completo)
                await self.iframe.get_by_role("cell", name=prestador, exact=True).click()
                print(f"  ✓ Prestador seleccionado")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"  ⚠️  No se pudo seleccionar prestador exacto, continuando: {e}")
        
        # Seleccionar año
        try:
            # Click en el input del año (selector correcto del codegen)
            await self.iframe.locator("#cmdAgnos_I").click()
            await asyncio.sleep(1)
            
            # Click en la opción del año
            await self.iframe.get_by_role("cell", name=year, exact=True).click()
            print(f"  ✓ Año {year} seleccionado")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"  ⚠️  Error seleccionando año: {e}")
        
        # Seleccionar mes - con scroll JavaScript en contenedor DevExpress
        try:
            # Paso 1: Abrir dropdown
            print(f"  🔽 Abriendo dropdown de meses...")
            await self.iframe.locator("#cmdMeses").get_by_role("cell").first.click()
            await asyncio.sleep(1)
            
            # Paso 2: Mapear mes a índice
            month_ids = {
                "ENERO": 0, "FEBRERO": 1, "MARZO": 2, "ABRIL": 3,
                "MAYO": 4, "JUNIO": 5, "JULIO": 6, "AGOSTO": 7,
                "SEPTIEMBRE": 8, "OCTUBRE": 9, "NOVIEMBRE": 10, "DICIEMBRE": 11
            }
            month_index = month_ids.get(month, 0)
            
            # Paso 3: Hacer scroll inteligente según rango del mes
            if month_index <= 6:  # ENERO-JULIO (visibles desde el tope)
                print(f"  📜 Scroll al tope (meses ENERO-JULIO)...")
                await self.iframe.locator("#cmdMeses_DDD_L_D").evaluate("el => el.scrollTop = 0")
            else:  # AGOSTO-DICIEMBRE (visibles desde el fondo)
                print(f"  📜 Scroll al fondo (meses AGOSTO-DICIEMBRE)...")
                await self.iframe.locator("#cmdMeses_DDD_L_D").evaluate("el => el.scrollTop = el.scrollHeight")
            await asyncio.sleep(0.5)
            
            # Paso 4: Click en el mes por su ID fijo
            month_id = f"#cmdMeses_DDD_L_LBI{month_index}T0"
            print(f"  🔍 Seleccionando {month}...")
            await self.iframe.locator(month_id).click()
            print(f"  ✓ Click en {month}")
            await asyncio.sleep(0.5)
            
            # Paso 5: Cerrar dropdown para confirmar
            print(f"  🔒 Cerrando dropdown...")
            await self.iframe.locator("#cmdMeses").get_by_role("img", name="v").click()
            print(f"  ✅ Mes {month} confirmado")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"  ❌ Error seleccionando mes: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Click en botón Consultar (selector correcto del codegen)
        try:
            await self.iframe.get_by_role("cell", name="Consultar Consultar", exact=True).locator("span").click()
            print(f"  ✓ Botón Consultar presionado")
            await asyncio.sleep(5)
            
            # Verificar si hay resultados o mensaje de "No existen datos"
            # Ignorar mensaje "No existe Cuentas Médicas" - es falso positivo común
            if await self.iframe.locator("text=No existe Cuentas Médicas para el periodo consultado").count() > 0:
                print(f"⚠️  Detectado mensaje 'No existe Cuentas Médicas' - IGNORANDO (falso positivo)")
                print(f"✅ Continuando con el flujo normal...")
            
            # Solo verificar mensajes realmente críticos
            no_data_messages = [
                "No se encontraron resultados",
                "Sin datos disponibles",
                "No hay información"
            ]
            
            for msg in no_data_messages:
                if await self.iframe.locator(f"text={msg}").count() > 0:
                    print(f"⚠️  {msg}")
                    print(f"⚠️  El período {year}/{month} no tiene datos para este prestador")
                    return False  # Indicar que no hay datos
            
            print("✅ Filtros aplicados correctamente")
            return True  # Hay datos
            
        except Exception as e:
            print(f"  ⚠️  Error presionando Consultar: {e}")
            # Intento alternativo
            await self.iframe.locator("#btnConsultar").click()
            await asyncio.sleep(5)
            return True  # Asumir que hay datos si no podemos verificar
    
    async def get_summary_table_data_and_process(self) -> List[Dict[str, Any]]:
        """Obtiene datos de la tabla resumen, ordena y procesa INMEDIATAMENTE cada enlace."""
        print("📊 Procesando tabla resumen...")
        
        # Ordenar por "Cuentas A Pago" (descendente)
        await self.iframe.get_by_text("Cuentas A Pago").click()
        await asyncio.sleep(1)
        await self.iframe.get_by_text("Cuentas A Pago").click()
        await asyncio.sleep(2)
        
        all_pdfs = []
        page_num = 1
        
        while True:
            # Capturar estado inicial
            await self.logger.capture_state(self.page, self.iframe, f"tabla_resumen_pag{page_num}", {
                "pagina": page_num
            })
            
            # Buscar enlaces SOLO en columna "Cuentas A Pago"
            links = await self.iframe.locator("div[id*='panelAPago'] a[onclick*=\"DetalleCtas('APago'\"]").all()
            
            # Extraer datos con FECHA como identificador
            found_zero = False
            links_data = []
            
            for idx, link in enumerate(links):
                link_text = await link.text_content()
                onclick = await link.get_attribute("onclick")
                
                # Extraer fecha del onclick
                fecha_match = re.search(r"DetalleCtas\('APago',\s*'([^']+)'", onclick)
                fecha = fecha_match.group(1) if fecha_match else None
                
                if not fecha:
                    await self.logger.capture_state(self.page, self.iframe, f"error_fecha_idx{idx}", {
                        "onclick": onclick,
                        "text": link_text.strip() if link_text else ""
                    })
                    continue
                
                if link_text and link_text.strip().isdigit():
                    count = int(link_text.strip())
                    if count == 0:
                        found_zero = True
                        break
                    if count > 0:
                        links_data.append({
                            "fecha": fecha,  # Usar fecha como ID único
                            "count": count,
                            "text": link_text.strip()
                        })
            
            if found_zero:
                break
            
            if len(links_data) == 0:
                break
            
            print(f"✅ {len(links_data)} enlaces para procesar")
            
            # Procesar cada enlace
            for i, link_data in enumerate(links_data, 1):
                print(f"📊 Enlace {i}/{len(links_data)}: {link_data['count']} cuentas")
                
                # Re-obtener enlace por FECHA (inmutable)
                fresh_links = await self.iframe.locator(
                    f"div[id*='panelAPago'] a[onclick*=\"'{link_data['fecha']}'\"]"
                ).all()
                
                if not fresh_links:
                    await self.logger.capture_state(self.page, self.iframe, f"error_no_link_pag{page_num}_iter{i}", {
                        "fecha_buscada": link_data['fecha'],
                        "iteracion": i
                    })
                    continue
                
                target_link = fresh_links[0]
                
                # Click en el enlace
                try:
                    await target_link.click()
                    await asyncio.sleep(3)
                    
                    if await self.iframe.locator("text=Fecha Recepción Isapre:").count() == 0:
                        continue
                except Exception as e:
                    await self.logger.capture_state(self.page, self.iframe, f"error_click_pag{page_num}_iter{i}", {
                        "error": str(e),
                        "fecha": link_data['fecha']
                    })
                    continue
                
                # Procesar tabla detalle
                try:
                    pdfs = await self.process_detail_table(link_data['text'])
                    all_pdfs.extend(pdfs)
                    
                    # process_detail_table() ya vuelve a tabla resumen
                    # Solo esperamos a que la tabla se estabilice y capturamos estado
                    await asyncio.sleep(2)
                    
                    # Capturar estado después de volver
                    await self.logger.capture_state(self.page, self.iframe, f"vuelta_pag{page_num}_iter{i}", {
                        "enlace_procesado": link_data['fecha'],
                        "pdfs_descargados": len(pdfs)
                    })
                    
                    print(f"✅ Completado: {len(pdfs)} PDFs")
                    
                except Exception as e:
                    await self.logger.capture_state(self.page, self.iframe, f"error_detalle_pag{page_num}_iter{i}", {
                        "error": str(e)
                    })
                    print(f"❌ Error: {e}")
            
            # Paginación
            try:
                next_btn = self.iframe.locator("#panelResumen_CallBackPanel_1_gridCuentaMedicaResumen_DXPagerBottom_PBN")
                if await next_btn.count() > 0:
                    await next_btn.click()
                    await asyncio.sleep(2)
                    page_num += 1
                    continue
                else:
                    break
            except:
                break
        
        # Validación final
        validation_report = await self.final_validation(all_pdfs)
        
        print(f"\n✅ Total: {len(all_pdfs)} PDFs")
        return all_pdfs, validation_report
    
    async def process_detail_table(self, link_text: str) -> List[Dict[str, Any]]:
        """Procesa la tabla de detalle, extrae metadata completa y descarga todos los PDFs."""
        print(f"    📋 Procesando tabla de detalle...")
        
        # Verificar que aparezca la tabla de detalle
        await self.iframe.locator("text=Fecha Recepción Isapre:").wait_for(timeout=10000)
        
        # CRITICAL: Resetear paginación a página 1
        # La tabla detalle tiene "memoria" de la página del enlace anterior
        # DEBUG: Listar todos los botones de paginación disponibles
        try:
            all_pager_links = await self.iframe.locator("#panelCuentas_CallBackPanel_gridCuentaMedica_DXPagerBottom a").all()
            print(f"    🔍 DEBUG: Botones de paginación encontrados: {len(all_pager_links)}")
            for idx, link in enumerate(all_pager_links[:5]):  # Mostrar máximo 5
                text = await link.text_content()
                onclick = await link.get_attribute("onclick")
                print(f"      [{idx}] Texto: '{text.strip()}' | onclick: {onclick[:50] if onclick else 'N/A'}...")
            
            # Buscar el botón "1" con clase dxp-num
            page_1_btn = self.iframe.locator("a.dxp-num[onclick*='PN0']")
            count = await page_1_btn.count()
            print(f"    🔍 Botones con PN0: {count}")
            
            if count > 0:
                await page_1_btn.first.click()
                await asyncio.sleep(2)  # Aumentado de 1 a 2 segundos
                # Esperar que la tabla se actualice
                await self.iframe.locator("#panelCuentas_CallBackPanel_gridCuentaMedica_DXMainTable tr[id*='DXDataRow']").first.wait_for(state="visible", timeout=5000)
                print(f"    🔄 Paginación reseteada a página 1")
        except Exception as e:
            print(f"    ⚠️  Error en reset de paginación: {e}")
            import traceback
            traceback.print_exc()
        
        # Extraer headers de la tabla (columnas)
        headers_row = await self.iframe.locator("#panelCuentas_CallBackPanel_gridCuentaMedica_DXHeadersRow0 td").all()
        headers = []
        for header in headers_row:
            header_text = await header.text_content()
            # Limpiar texto (quitar saltos de línea, espacios extras)
            clean_text = " ".join(header_text.strip().split())
            headers.append(clean_text)
        
        print(f"    📋 Columnas: {', '.join(headers)}")
        
        # Lista para almacenar TODOS los datos de la tabla
        all_rows_data = []
        pdfs_data = []
        page_num = 1
        
        while True:
            print(f"📄 Procesando página {page_num} de tabla detalle...")
            
            # Obtener TODAS las filas de datos (excluir header)
            data_rows = await self.iframe.locator("#panelCuentas_CallBackPanel_gridCuentaMedica_DXMainTable tr[id*='DXDataRow']").all()
            
            if not data_rows:
                print("⚠️  No se encontraron filas en tabla detalle")
                break
            
            print(f"    📌 Encontradas {len(data_rows)} filas en esta página")
            
            # Procesar cada fila: extraer datos completos y descargar PDF
            for row_idx, data_row in enumerate(data_rows, 1):
                # Extraer TODAS las celdas de la fila
                cells = await data_row.locator("td.dxgv").all()
                
                # Crear diccionario con metadata completa
                row_data = {}
                for idx, cell in enumerate(cells):
                    if idx < len(headers):
                        cell_text = await cell.text_content()
                        row_data[headers[idx]] = cell_text.strip() if cell_text else ""
                
                # Guardar en lista para CSV
                all_rows_data.append(row_data.copy())
                
                # Obtener Nro. Cuenta (primera columna)
                nro_cuenta = row_data.get("Nro. Cuenta", f"row_{row_idx}")
                
                # Buscar enlace de PDF en esta fila
                pdf_link = data_row.locator("a[onclick*='AbrirImagen_ReporteLiquidacion']")
                
                if await pdf_link.count() == 0:
                    print(f"      ⚠️  Fila {row_idx} (Cuenta {nro_cuenta}): Sin PDF")
                    continue
                
                # Extraer token del PDF
                try:
                    onclick = await pdf_link.get_attribute("onclick")
                    token_match = re.search(r"AbrirImagen_ReporteLiquidacion\('([^']+)'", onclick)
                    if not token_match:
                        print(f"      ⚠️  Cuenta {nro_cuenta}: No se pudo extraer token")
                        continue
                    
                    token = token_match.group(1)
                    row_data["pdf_token"] = token
                    
                    print(f"      📄 [{row_idx}/{len(data_rows)}] Cuenta {nro_cuenta} - Token: {token[:10]}...")
                    
                except Exception as e:
                    print(f"      ⚠️  Cuenta {nro_cuenta}: Error extrayendo token: {e}")
                    continue
                
                # Descargar PDF con validación robusta
                pdf_downloaded = False
                for retry in range(3):
                    try:
                        print(f"      🔄 Intento {retry + 1}/3: Descargando PDF para {nro_cuenta}")
                        
                        # Generar nombre de archivo único
                        pdf_filename = f"{nro_cuenta}_{link_text}_{token[:8]}.pdf"
                        pdf_path = self.pdf_dir / self.job_id / pdf_filename
                        pdf_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Verificar si ya existe (evitar duplicados)
                        if pdf_path.exists():
                            print(f"      ⚠️  PDF ya existe: {pdf_filename}")
                            # Verificar que no esté corrupto
                            if pdf_path.stat().st_size > 0:
                                row_data["pdf_filename"] = pdf_filename
                                row_data["pdf_size"] = pdf_path.stat().st_size
                                row_data["pdf_token"] = token
                                pdfs_data.append(row_data)
                                print(f"      ✅ PDF existente válido: {pdf_filename} ({pdf_path.stat().st_size} bytes)")
                                pdf_downloaded = True
                                break
                            else:
                                print(f"      🗑️  PDF corrupto, eliminando: {pdf_filename}")
                                pdf_path.unlink()
                        
                        # Configurar descarga
                        async with self.page.expect_download() as download_info:
                            await pdf_link.click()
                        
                        download = await download_info.value
                        
                        # Guardar con validación
                        await download.save_as(pdf_path)
                        
                        # VALIDACIÓN CRÍTICA: Verificar que el PDF se descargó correctamente
                        await asyncio.sleep(1)  # Esperar a que se escriba completamente
                        
                        if pdf_path.exists() and pdf_path.stat().st_size > 1000:  # Mínimo 1KB
                            row_data["pdf_filename"] = pdf_filename
                            row_data["pdf_size"] = pdf_path.stat().st_size
                            row_data["pdf_token"] = token
                            pdfs_data.append(row_data)
                            print(f"      ✅ PDF descargado y validado: {pdf_filename} ({pdf_path.stat().st_size} bytes)")
                            pdf_downloaded = True
                            break
                        else:
                            print(f"      ⚠️  PDF descargado pero inválido: {pdf_filename}")
                            if pdf_path.exists():
                                pdf_path.unlink()  # Eliminar archivo corrupto
                            if retry < 2:
                                await asyncio.sleep(2)
                                
                    except Exception as e:
                        print(f"      ⚠️  Intento {retry + 1}/3 falló: {e}")
                        if retry < 2:
                            await asyncio.sleep(2)
                
                if not pdf_downloaded:
                    print(f"      ❌ FALLO CRÍTICO: No se pudo descargar PDF para {nro_cuenta} después de 3 intentos")
                    # Registrar el fallo para auditoría
                    row_data["download_status"] = "FAILED"
                    row_data["error_count"] = 3
                    pdfs_data.append(row_data)
            
            # Verificar si hay siguiente página (detectar botón deshabilitado)
            try:
                next_btn = self.iframe.locator("#panelCuentas_CallBackPanel_gridCuentaMedica_DXPagerBottom_PBN")
                
                # Verificar si el botón existe y NO está deshabilitado
                if await next_btn.count() > 0:
                    # Verificar si tiene clase "dxp-disabledButton" (última página)
                    btn_class = await next_btn.get_attribute("class")
                    if btn_class and "dxp-disabledButton" in btn_class:
                        print(f"    ℹ️  Última página detectada (botón Next deshabilitado)")
                        break
                    
                    # Botón activo, ir a siguiente página
                    await next_btn.click()
                    await asyncio.sleep(3)
                    page_num += 1
                    continue
                else:
                    # No hay botón Next (solo 1 página)
                    print(f"    ℹ️  Solo existe 1 página")
                    break
            except Exception as e:
                print(f"    ⚠️  Error en paginación: {e}")
                break
        
        # Guardar metadata completa como CSV
        if all_rows_data:
            csv_filename = f"metadata_{link_text}_{self.job_id}.csv"
            csv_path = Path("data/metadata") / csv_filename
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                import csv
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    if all_rows_data:
                        writer = csv.DictWriter(f, fieldnames=headers)
                        writer.writeheader()
                        writer.writerows(all_rows_data)
                print(f"    💾 Metadata guardada: {csv_filename} ({len(all_rows_data)} filas)")
            except Exception as e:
                print(f"    ⚠️  Error guardando CSV: {e}")
        
        # VALIDACIÓN CRUZADA Y REINTENTOS
        await self.validate_and_retry_downloads(pdfs_data, link_text)
        
        # RESUMEN FINAL
        total_attempted = len([r for r in pdfs_data])
        total_success = len([r for r in pdfs_data if r.get("pdf_filename")])
        total_failed = len([r for r in pdfs_data if r.get("download_status") == "FAILED"])
        expected_cuentas = int(link_text) if link_text.isdigit() else 0
        
        print(f"\n📊 RESUMEN FINAL - Enlace {link_text}:")
        print(f"   📄 Total filas procesadas: {total_attempted}")
        print(f"   ✅ PDFs descargados exitosamente: {total_success}")
        print(f"   ❌ PDFs fallidos: {total_failed}")
        
        # Validación: PDFs >= Cuentas (una cuenta puede tener múltiples PDFs)
        if expected_cuentas > 0:
            if total_success < expected_cuentas:
                print(f"   🚨 ERROR CRÍTICO: Se esperaban al menos {expected_cuentas} PDFs (cuentas) pero solo se descargaron {total_success}")
                print(f"   ⚠️  Posible problema: paginación empezó en página incorrecta o PDFs faltantes")
            elif total_success > expected_cuentas:
                print(f"   ✅ OK: {total_success} PDFs de {expected_cuentas} cuentas (algunas cuentas tienen múltiples PDFs)")
            else:
                print(f"   ✅ PERFECTO: {total_success} PDFs de {expected_cuentas} cuentas")
        
        if total_failed > 0:
            print(f"   ⚠️  ATENCIÓN: {total_failed} PDFs no se pudieron descargar después de todos los reintentos")
        
        # Volver a la tabla resumen usando el botón de búsqueda
        try:
            await self.iframe.locator("#panelCuentas_CallBackPanel_btnSearchImg").click()
            await asyncio.sleep(2)
            print("✅ Volviendo a tabla resumen")
        except Exception as e:
            print(f"⚠️  Error volviendo a tabla resumen: {e}")
        
        return pdfs_data
    
    async def validate_and_retry_downloads(self, pdfs_data: List[Dict[str, Any]], link_text: str) -> None:
        """Valida que los PDFs descargados coincidan con la metadata y reintenta si no cuadran."""
        print(f"\n🔍 VALIDACIÓN CRUZADA - Enlace {link_text}")
        
        # Contar cuántos deberían haberse descargado
        expected_pdfs = len([r for r in pdfs_data if r.get("pdf_token")])
        actual_pdfs = len([r for r in pdfs_data if r.get("pdf_filename")])
        
        print(f"   📊 Esperados: {expected_pdfs}, Descargados: {actual_pdfs}")
        
        if expected_pdfs == actual_pdfs:
            print(f"   ✅ Todos los PDFs descargados correctamente")
            return
        
        print(f"   ⚠️  DISCREPANCIA DETECTADA: Faltan {expected_pdfs - actual_pdfs} PDFs")
        
        # Identificar cuáles fallaron
        failed_records = [r for r in pdfs_data if not r.get("pdf_filename") and r.get("pdf_token")]
        
        if not failed_records:
            print(f"   ℹ️  No hay registros fallidos para reintentar")
            return
        
        print(f"   🔄 REINTENTANDO {len(failed_records)} PDFs fallidos...")
        
        # Reintentar cada PDF fallido
        for i, record in enumerate(failed_records, 1):
            nro_cuenta = record.get('Nro. Cuenta', '')
            print(f"   🔄 [{i}/{len(failed_records)}] Reintentando: {nro_cuenta}")
            
            # Buscar el enlace PDF en la tabla actual
            try:
                # Buscar fila por Nro. Cuenta
                rows = await self.iframe.locator("table").filter(has_text="Nro. Cuenta").locator("tr").all()
                
                target_row = None
                for row in rows[1:]:  # Skip header
                    cells = await row.locator("td").all()
                    if len(cells) > 0:
                        cell_text = await cells[0].text_content()
                        if cell_text and cell_text.strip() == nro_cuenta:
                            target_row = row
                            break
                
                if not target_row:
                    print(f"      ❌ No se encontró fila para {nro_cuenta}")
                    continue
                
                # Buscar enlace PDF en esa fila
                pdf_link = target_row.get_by_role("link", name="Reporte Liquidación").first
                if await pdf_link.count() == 0:
                    print(f"      ❌ No se encontró enlace PDF para {nro_cuenta}")
                    continue
                
                # Reintentar descarga
                success = False
                for retry in range(2):  # Solo 2 reintentos adicionales
                    try:
                        print(f"      🔄 Reintento {retry + 1}/2 para {nro_cuenta}")
                        
                        # Generar nombre único
                        token = record.get("pdf_token", "")
                        pdf_filename = f"{nro_cuenta}_{link_text}_{token[:8]}_retry{retry+1}.pdf"
                        pdf_path = self.pdf_dir / self.job_id / pdf_filename
                        
                        # Configurar descarga
                        async with self.page.expect_download() as download_info:
                            await pdf_link.click()
                        
                        download = await download_info.value
                        await download.save_as(pdf_path)
                        
                        # Validar descarga
                        await asyncio.sleep(1)
                        if pdf_path.exists() and pdf_path.stat().st_size > 1000:
                            record["pdf_filename"] = pdf_filename
                            record["pdf_size"] = pdf_path.stat().st_size
                            record["retry_success"] = True
                            record["retry_count"] = retry + 1
                            print(f"      ✅ Reintento exitoso: {pdf_filename} ({pdf_path.stat().st_size} bytes)")
                            success = True
                            break
                        else:
                            print(f"      ⚠️  Reintento falló: archivo corrupto")
                            if pdf_path.exists():
                                pdf_path.unlink()
                            await asyncio.sleep(1)
                            
                    except Exception as e:
                        print(f"      ❌ Error en reintento {retry + 1}: {e}")
                        await asyncio.sleep(1)
                
                if not success:
                    print(f"      ❌ Todos los reintentos fallaron para {nro_cuenta}")
                    record["download_status"] = "FAILED_FINAL"
                    record["final_error"] = "All retries failed"
                
            except Exception as e:
                print(f"      ❌ Error general en reintento para {nro_cuenta}: {e}")
                record["download_status"] = "FAILED_FINAL"
                record["final_error"] = str(e)
        
        # Resumen final de reintentos
        final_success = len([r for r in pdfs_data if r.get("pdf_filename")])
        print(f"   📊 RESULTADO FINAL: {final_success}/{expected_pdfs} PDFs descargados")
    
    async def final_validation(self, all_pdfs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validación final global de todos los PDFs descargados."""
        print(f"\n🔍 VALIDACIÓN GLOBAL FINAL")
        
        # Contar estadísticas
        total_records = len(all_pdfs)
        successful_downloads = len([r for r in all_pdfs if r.get("pdf_filename")])
        failed_downloads = len([r for r in all_pdfs if r.get("download_status") == "FAILED"])
        retry_successes = len([r for r in all_pdfs if r.get("retry_success")])
        
        print(f"   📊 ESTADÍSTICAS GLOBALES:")
        print(f"      📄 Total registros procesados: {total_records}")
        print(f"      ✅ PDFs descargados exitosamente: {successful_downloads}")
        print(f"      🔄 PDFs recuperados en reintentos: {retry_successes}")
        print(f"      ❌ PDFs fallidos definitivamente: {failed_downloads}")
        
        # Verificar archivos en disco
        corrupted_files = []
        total_size = 0
        pdf_dir = self.pdf_dir / self.job_id
        if pdf_dir.exists():
            pdf_files = list(pdf_dir.glob("*.pdf"))
            print(f"      📂 Archivos PDF en disco: {len(pdf_files)}")
            
            # Verificar integridad de archivos
            for pdf_file in pdf_files:
                size = pdf_file.stat().st_size
                total_size += size
                if size < 1000:  # Menos de 1KB probablemente corrupto
                    corrupted_files.append(pdf_file.name)
            
            print(f"      💾 Tamaño total descargado: {total_size:,} bytes")
            
            if corrupted_files:
                print(f"      ⚠️  ARCHIVOS CORRUPTOS DETECTADOS:")
                for file in corrupted_files:
                    print(f"         ❌ {file}")
            else:
                print(f"      ✅ Todos los archivos PDF tienen integridad válida")
        
        # Identificar registros problemáticos
        failed_records = []
        if failed_downloads > 0:
            print(f"\n   ⚠️  REGISTROS CON PROBLEMAS:")
            for record in all_pdfs:
                if record.get("download_status") == "FAILED":
                    error_info = {
                        "nro_cuenta": record.get('Nro. Cuenta', 'N/A'),
                        "error": record.get('final_error', 'Unknown error')
                    }
                    failed_records.append(error_info)
                    print(f"      ❌ {error_info['nro_cuenta']}: {error_info['error']}")
        
        # Calcular tasa de éxito
        success_rate = (successful_downloads / total_records * 100) if total_records > 0 else 0
        print(f"\n   📈 TASA DE ÉXITO: {success_rate:.1f}%")
        
        validation_passed = success_rate >= 95 and len(corrupted_files) == 0
        
        if success_rate >= 95:
            print(f"   🎯 EXCELENTE: Tasa de éxito superior al 95%")
        elif success_rate >= 90:
            print(f"   ✅ BUENO: Tasa de éxito superior al 90%")
        elif success_rate >= 80:
            print(f"   ⚠️  ACEPTABLE: Tasa de éxito superior al 80%")
        else:
            print(f"   ❌ PROBLEMÁTICO: Tasa de éxito inferior al 80%")
        
        # Retornar reporte estructurado
        return {
            "passed": validation_passed,
            "total_expected": total_records,
            "total_downloaded": successful_downloads,
            "success_rate": round(success_rate, 2),
            "failed_records": failed_records,
            "corrupted_files": corrupted_files,
            "retry_successes": retry_successes,
            "total_size_bytes": total_size
        }
    
    async def download_pdf(self, row_data: Dict[str, Any], link_text: str, pdf_element) -> str:
        """Descarga un PDF específico."""
        nro_cuenta = row_data.get("Nro. Cuenta", "unknown")
        
        # Configurar descarga
        download_path = self.pdf_dir / f"{self.job_id}"
        download_path.mkdir(parents=True, exist_ok=True)
        
        # Generar nombre de archivo
        pdf_filename = f"{nro_cuenta}_{link_text}.pdf"
        pdf_path = download_path / pdf_filename
        
        # Configurar download handler
        async with self.page.expect_download() as download_info:
            await pdf_element.click()
        
        download = await download_info.value
        
        # Guardar archivo
        await download.save_as(pdf_path)
        print(f"    💾 PDF guardado: {pdf_path}")
        
        return pdf_filename
    
    async def discover_documents(self, page: Page, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Flujo principal de descubrimiento y descarga de documentos."""
        print("🚀 Iniciando descubrimiento de documentos...")
        
        self.page = page
        self.context = page.context
        self.job_id = params.get("job_id", f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        # Inicializar logger autónomo
        self.logger = DebugLogger(self.job_id)
        
        # 1. Navegar a la sección de cuentas
        await self.navigate_to_accounts_section()
        
        # 2. Aplicar filtros
        has_data = await self.apply_filters(
            prestador=params.get("prestador"),
            year=params.get("year", "2025"),
            month=params.get("month", "SEPTIEMBRE")
        )
        
        if not has_data:
            print("⚠️  No hay datos para este período, retornando lista vacía")
            return []
        
        # 3. Obtener, procesar y descargar TODO (con reintentos y validaciones)
        try:
            all_pdfs, validation_report = await self.get_summary_table_data_and_process()
            
            if not all_pdfs:
                print("⚠️  No se descargaron PDFs (tabla vacía o sin enlaces válidos)")
                # Guardar resultado vacío con metadata
                results_file = self.results_dir / f"{self.job_id}_results.json"
                results_file.parent.mkdir(parents=True, exist_ok=True)
                results_data = {
                    "job_id": self.job_id,
                    "timestamp": datetime.now().isoformat(),
                    "status": "no_data",
                    "total_pdfs": 0,
                    "pdfs": [],
                    "validation": {
                        "passed": False,
                        "total_expected": 0,
                        "total_downloaded": 0,
                        "success_rate": 0,
                        "failed_records": [],
                        "corrupted_files": []
                    }
                }
                results_file.write_text(json.dumps(results_data, indent=2, ensure_ascii=False))
                return []
            
            # Guardar resultados exitosos
            results_file = self.results_dir / f"{self.job_id}_results.json"
            results_file.parent.mkdir(parents=True, exist_ok=True)
            results_data = {
                "job_id": self.job_id,
                "timestamp": datetime.now().isoformat(),
                "status": "success",
                "total_pdfs": len(all_pdfs),
                "pdfs": all_pdfs,
                "validation": validation_report
            }
            
            results_file.write_text(json.dumps(results_data, indent=2, ensure_ascii=False))
            
            # Guardar reportes de debug
            self.logger.save_report()
            analysis = self.logger.analyze_and_save()
            
            print(f"\n🎉 SCRAPING COMPLETADO")
            print(f"📊 Total: {len(all_pdfs)} PDFs descargados")
            print(f"📁 Resultados: {results_file}")
            print(f"📂 PDFs: {self.pdf_dir / self.job_id}")
            print(f"🔍 Debug: data/debug/{self.job_id}/")
            
            if analysis:
                print(f"📈 Análisis: {analysis['total_eventos']} eventos, {analysis['enlaces_procesados']} enlaces procesados")
                if analysis['errores']:
                    print(f"⚠️  {len(analysis['errores'])} errores detectados (ver analysis.json)")
            
            return all_pdfs
            
        except Exception as e:
            print(f"❌ Error fatal en scraping: {e}")
            import traceback
            traceback.print_exc()
            
            # Guardar reportes de debug incluso en caso de error
            if self.logger:
                self.logger.save_report()
                self.logger.analyze_and_save()
                print(f"🔍 Debug info guardado en: data/debug/{self.job_id}/")
            
            # Guardar resultado de error
            results_file = self.results_dir / f"{self.job_id}_results.json"
            results_file.parent.mkdir(parents=True, exist_ok=True)
            results_data = {
                "job_id": self.job_id,
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e),
                "total_pdfs": 0,
                "pdfs": []
            }
            results_file.write_text(json.dumps(results_data, indent=2, ensure_ascii=False))
            
            return []
    
    def extract(self, pdf_path: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extrae información de un PDF descargado."""
        # TODO: Implementar extracción de PDFs usando pdfplumber o similar
        # Por ahora retorna metadata básico
        return [metadata]
    
    def postprocess(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Post-procesamiento de registros extraídos."""
        # TODO: Implementar normalización de datos
        return records
