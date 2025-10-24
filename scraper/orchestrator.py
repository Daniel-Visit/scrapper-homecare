"""Orquestador del proceso completo de scraping y extracción."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright

from scraper.models import ScrapingParams, ScrapingResult, ExtractionResult, ValidationReport
from scraper.cruzblanca import CruzBlancaScraper
from scraper.extractor import PDFExtractor
from config.cruzblanca_selectors import DASHBOARD_URL


class ProcessOrchestrator:
    """Orquesta el proceso completo de scraping → validación → extracción."""
    
    def __init__(self, data_dir: str = "data"):
        """
        Inicializa el orquestador.
        
        Args:
            data_dir: Directorio base para datos
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def run_full_process(
        self, 
        params: ScrapingParams,
        skip_scraping: bool = False,
        skip_extraction: bool = False
    ) -> dict:
        """
        Ejecuta el proceso completo: scraping → validación → extracción.
        
        Args:
            params: Parámetros del proceso
            skip_scraping: Si True, salta el scraping
            skip_extraction: Si True, salta la extracción
            
        Returns:
            Diccionario con resultados del proceso
        """
        print("🚀 INICIANDO PROCESO COMPLETO")
        print(f"   📅 Período: {params.month} {params.year}")
        print(f"   🏥 Prestador: {params.prestador or 'TODOS'}")
        print()
        
        scraping_result = None
        extraction_result = None
        
        # 1. Scraping
        if not skip_scraping:
            print("=" * 60)
            print("ETAPA 1: SCRAPING")
            print("=" * 60)
            scraping_result = self.run_scraping(params)
            
            # 2. Validación crítica
            if not scraping_result.validation_passed:
                print("\n" + "=" * 60)
                print("❌ VALIDACIÓN FALLIDA")
                print("=" * 60)
                print("⚠️  El scraping no completó exitosamente.")
                print("⚠️  No se ejecutará la extracción.")
                print(f"\n📊 Tasa de éxito: {scraping_result.validation.success_rate}%")
                print(f"❌ PDFs fallidos: {scraping_result.failed}")
                
                if scraping_result.validation.corrupted_files:
                    print(f"⚠️  Archivos corruptos: {len(scraping_result.validation.corrupted_files)}")
                
                return {
                    "status": "validation_failed",
                    "scraping": scraping_result.dict(),
                    "extraction": None
                }
            
            print("\n" + "=" * 60)
            print("✅ VALIDACIÓN EXITOSA")
            print("=" * 60)
            print(f"🎯 Tasa de éxito: {scraping_result.validation.success_rate}%")
            print(f"✅ PDFs descargados: {scraping_result.successful}")
            print("✅ Todos los criterios de calidad cumplidos")
        else:
            print("⏭️  Saltando scraping (usando datos existentes)")
            # TODO: Cargar resultado de scraping previo
        
        # 3. Extracción (solo si validación OK)
        if not skip_extraction:
            print("\n" + "=" * 60)
            print("ETAPA 2: EXTRACCIÓN")
            print("=" * 60)
            
            if scraping_result:
                extraction_result = self.run_extraction(scraping_result)
            else:
                print("❌ No hay resultado de scraping para extraer")
        else:
            print("⏭️  Saltando extracción")
        
        # Resultado final
        print("\n" + "=" * 60)
        print("🎉 PROCESO COMPLETADO")
        print("=" * 60)
        
        return {
            "status": "completed",
            "scraping": scraping_result.dict() if scraping_result else None,
            "extraction": extraction_result.dict() if extraction_result else None
        }
    
    def run_scraping(self, params: ScrapingParams) -> ScrapingResult:
        """
        Ejecuta solo el proceso de scraping.
        
        Args:
            params: Parámetros del scraping
            
        Returns:
            Resultado del scraping con validación
        """
        print("🔐 Iniciando scraping...")
        print(f"   👤 Usuario: {params.username}")
        print(f"   📅 Período: {params.month} {params.year}")
        
        # Ejecutar scraping con Playwright
        result = asyncio.run(self._run_scraping_async(params))
        
        return result
    
    async def _run_scraping_async(self, params: ScrapingParams) -> ScrapingResult:
        """Ejecuta scraping de forma asíncrona."""
        
        async with async_playwright() as p:
            # Inicializar scraper
            scraper = CruzBlancaScraper(output_dir=self.data_dir)
            
            # Generar job_id único
            job_id = f"{params.month.lower()}_{params.year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Lanzar navegador en modo visible (para CAPTCHA manual)
            browser = await p.chromium.launch(
                headless=False,
                slow_mo=200
            )
            
            context = await browser.new_context(
                accept_downloads=True
                # Sin viewport - se abre en tamaño normal del navegador
            )
            
            page = await context.new_page()
            scraper.context = context
            scraper.page = page
            scraper.job_id = job_id
            
            try:
                # 1. Login (manual con CAPTCHA)
                await scraper.login_via_context(page, params.username, params.password)
                
                # 2. Descubrir y descargar documentos
                scraping_params = {
                    "job_id": job_id,
                    "prestador": params.prestador,
                    "year": params.year,
                    "month": params.month.upper()
                }
                
                all_pdfs = await scraper.discover_documents(page, scraping_params)
                
                # 3. Cargar reporte de validación
                results_file = scraper.results_dir / f"{job_id}_results.json"
                with open(results_file, 'r', encoding='utf-8') as f:
                    results_data = json.load(f)
                
                validation_data = results_data.get("validation", {})
                validation = ValidationReport(**validation_data)
                
                # 4. Crear resultado
                result = ScrapingResult(
                    job_id=job_id,
                    year=params.year,
                    month=params.month,
                    prestador=params.prestador,
                    total_pdfs=len(all_pdfs),
                    successful=validation.total_downloaded,
                    failed=validation.total_expected - validation.total_downloaded,
                    validation=validation,
                    pdf_directory=str(scraper.pdf_dir / job_id),
                    metadata_file=str(results_file)
                )
                
                return result
                
            finally:
                await browser.close()
    
    def run_extraction(self, scraping_result: ScrapingResult) -> ExtractionResult:
        """
        Ejecuta solo el proceso de extracción.
        
        Args:
            scraping_result: Resultado del scraping previo
            
        Returns:
            Resultado de la extracción
        """
        print("📄 Iniciando extracción de PDFs...")
        print(f"   📂 Directorio: {scraping_result.pdf_directory}")
        print(f"   📊 Total PDFs: {scraping_result.successful}")
        
        # Inicializar extractor
        extractor = PDFExtractor()
        
        # Extraer datos de todos los PDFs
        extracted_data = extractor.extract_from_directory(
            dir_path=scraping_result.pdf_directory,
            metadata_file=scraping_result.metadata_file
        )
        
        # Generar archivo de salida
        output_file = self.data_dir / "json" / f"{scraping_result.job_id}_extracted.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Guardar datos extraídos
        extractor.save_to_json(extracted_data, str(output_file))
        
        # Validar extracción
        validation = extractor.validate_extraction(
            extracted_data, 
            expected_count=scraping_result.successful
        )
        
        # Obtener summary del resultado de extracción
        summary = extracted_data.get("summary", {})
        
        # Crear resultado
        result = ExtractionResult(
            job_id=scraping_result.job_id,
            total_files=summary.get("total_files", 0),
            extracted=summary.get("successful", 0),
            failed=summary.get("failed", 0),
            success_rate=validation["success_rate"] * 100,  # Convertir a porcentaje
            output_file=str(output_file),
            failed_files=summary.get("failed_files", [])
        )
        
        print(f"\n✅ Extracción completada:")
        print(f"   📄 Archivos procesados: {result.total_files}")
        print(f"   ✅ Extraídos exitosamente: {result.extracted}")
        print(f"   ❌ Fallidos: {result.failed}")
        print(f"   📈 Tasa de éxito: {result.success_rate}%")
        print(f"   💾 Archivo salida: {result.output_file}")
        
        return result
    
    async def run_with_storage_state(
        self,
        storage_state: dict,
        params: ScrapingParams
    ) -> ScrapingResult:
        """
        Ejecuta scraping usando storageState (sin login manual).
        
        Este método se usa cuando el usuario ya hizo login en el navegador remoto
        y el sistema capturó el storageState. El navegador headless se inicia
        con las cookies/sesión ya autenticada.
        
        Args:
            storage_state: Dict con cookies y localStorage capturados
            params: Parámetros del scraping
            
        Returns:
            ScrapingResult con los PDFs descargados
        """
        print("🔐 Iniciando scraping con storageState (headless)...")
        print(f"   📅 Período: {params.month} {params.year}")
        print(f"   🍪 Cookies: {len(storage_state.get('cookies', []))}")
        
        async with async_playwright() as p:
            # Inicializar scraper
            scraper = CruzBlancaScraper(output_dir=self.data_dir)
            
            # Generar job_id único
            job_id = f"{params.month.lower()}_{params.year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Lanzar navegador HEADLESS con storageState
            browser = await p.chromium.launch(headless=True)
            
            # Crear contexto con storageState (sesión ya autenticada)
            context = await browser.new_context(
                storage_state=storage_state,
                accept_downloads=True
            )
            
            page = await context.new_page()
            scraper.context = context
            scraper.page = page
            scraper.job_id = job_id
            
            try:
                # NO necesitamos hacer login - ya estamos autenticados!
                # Ir directo al área privada (EXTRANET)
                print("🔓 Navegando a la extranet (ya autenticado)...")
                await page.goto(DASHBOARD_URL)
                
                # Esperar un momento para asegurar que la sesión es válida
                await page.wait_for_load_state("networkidle", timeout=10000)
                
                # Verificar que seguimos autenticados
                if "login" in page.url.lower():
                    raise Exception("storageState expiró o es inválido - redireccionó a login")
                
                print("✅ Autenticación válida, iniciando scraping...")
                
                # Ejecutar scraping normal (sin login)
                all_pdfs = await scraper.discover_documents(
                    page=page,
                    params={
                        'year': str(params.year),
                        'month': params.month,
                        'prestador': params.prestador,
                        'job_id': job_id
                    }
                )
                
                print(f"\n✅ SCRAPING COMPLETADO")
                print(f"   📄 PDFs descargados: {len(all_pdfs)}")
                
                # Cargar reporte de validación desde el archivo results.json
                results_file = scraper.results_dir / f"{job_id}_results.json"
                with open(results_file, 'r', encoding='utf-8') as f:
                    results_data = json.load(f)
                
                validation_data = results_data.get("validation", {})
                validation = ValidationReport(**validation_data)
                
                # Construir ScrapingResult
                scraping_result = ScrapingResult(
                    job_id=job_id,
                    year=str(params.year),
                    month=params.month,
                    prestador=params.prestador,
                    total_pdfs=len(all_pdfs),
                    successful=len(all_pdfs),
                    failed=0,
                    pdf_directory=str(scraper.pdf_dir / job_id),
                    metadata_file=str(results_file),
                    validation=validation
                )
                
                return scraping_result
                
            except Exception as e:
                print(f"\n❌ Error en scraping: {e}")
                raise
            finally:
                await browser.close()

