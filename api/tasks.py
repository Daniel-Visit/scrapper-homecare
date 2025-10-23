"""
Task worker RQ que ejecuta el pipeline de scraping.

Pipeline de 3 pasos (según ARQUITECTURA_MICROSERVICIO.md líneas 92-106):
1. SCRAPER: Descarga PDFs → Guarda en SFTP /pdfs/
2. EXTRACTOR: Lee PDFs desde SFTP → pdfplumber → Guarda JSONs en SFTP /json/
3. REPORTER: Lee JSONs desde SFTP → Genera CSV → Guarda en SFTP /reports/

SFTP es el storage compartido entre pasos (workers no comparten filesystem).
"""

import asyncio
import json
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import shutil

from scraper.models import ScrapingParams
from scraper.orchestrator import ProcessOrchestrator
from scripts.generate_report import generate_csv_report
from api.sftp_client import SFTPClient
from api.config import settings


def run_pipeline(
    job_id: str,
    year: int,
    month: str,
    prestador: str,
    username: str,
    password: str
) -> Dict[str, Any]:
    """
    Ejecuta el pipeline completo de scraping.
    
    Este es el worker RQ que procesa en background.
    
    Args:
        job_id: ID único del job (ej: "febrero_2025_1729634567")
        year: Año del período
        month: Mes del período (ej: "FEBRERO")
        prestador: RUT y nombre del prestador (opcional)
        username: RUT del usuario para login
        password: Contraseña del usuario
    
    Returns:
        Diccionario con resultado del pipeline
    """
    print("=" * 80)
    print(f"🚀 INICIANDO PIPELINE - Job ID: {job_id}")
    print("=" * 80)
    print(f"📅 Período: {month} {year}")
    print(f"🏥 Prestador: {prestador or 'TODOS'}")
    print(f"👤 Usuario: {username}")
    print()
    
    result = {
        "job_id": job_id,
        "status": "pending",
        "steps": {
            "scraping": {"status": "pending"},
            "extraction": {"status": "pending"},
            "reporting": {"status": "pending"},
            "upload": {"status": "pending"}
        }
    }
    
    try:
        # ====================================================================
        # PASO 1: SCRAPING
        # ====================================================================
        print("=" * 80)
        print("PASO 1/3: SCRAPING")
        print("=" * 80)
        result["steps"]["scraping"]["status"] = "running"
        
        # Ejecutar scraper (usa tu código existente)
        orchestrator = ProcessOrchestrator(data_dir=settings.data_dir)
        
        params = ScrapingParams(
            year=year,
            month=month,
            prestador=prestador,
            username=username,
            password=password
        )
        
        # Ejecutar solo scraping (sin extracción)
        scraping_result = orchestrator.run_scraping(params)
        
        if not scraping_result.validation_passed:
            raise Exception(f"Validación de scraping fallida: {scraping_result.validation.dict()}")
        
        # Subir PDFs a SFTP
        print()
        print("📤 Subiendo PDFs a SFTP...")
        sftp = SFTPClient()
        pdf_dir = Path(scraping_result.pdf_directory)
        remote_pdf_path = f"{settings.sftp_base_path}/{job_id}/pdfs"
        
        upload_result = asyncio.run(
            sftp.upload_directory(pdf_dir, remote_pdf_path, "*.pdf")
        )
        
        print(f"✅ PDFs subidos: {upload_result['uploaded']}/{upload_result['total']}")
        
        result["steps"]["scraping"] = {
            "status": "completed",
            "pdfs_downloaded": scraping_result.successful,
            "pdfs_uploaded": upload_result["uploaded"],
            "validation": scraping_result.validation.dict()
        }
        
        # ====================================================================
        # PASO 2: EXTRACTION
        # ====================================================================
        print()
        print("=" * 80)
        print("PASO 2/3: EXTRACTION")
        print("=" * 80)
        result["steps"]["extraction"]["status"] = "running"
        
        # Crear directorio temporal para descargar PDFs desde SFTP
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_pdf_dir = Path(temp_dir) / "pdfs"
            temp_pdf_dir.mkdir()
            
            print(f"📥 Descargando PDFs desde SFTP para extracción...")
            # TODO: Implementar descarga masiva desde SFTP
            # Por ahora, usar PDFs locales del paso anterior
            # (En producción, esto vendría de SFTP si workers no comparten filesystem)
            
            # Ejecutar extracción
            extraction_result = orchestrator.run_extraction(scraping_result)
            
            # Subir JSONs a SFTP
            print()
            print("📤 Subiendo JSONs a SFTP...")
            json_output_dir = Path(settings.data_dir) / "json_output"
            remote_json_path = f"{settings.sftp_base_path}/{job_id}/json"
            
            upload_json_result = asyncio.run(
                sftp.upload_directory(json_output_dir, remote_json_path, "*.json")
            )
            
            print(f"✅ JSONs subidos: {upload_json_result['uploaded']}/{upload_json_result['total']}")
            
            result["steps"]["extraction"] = {
                "status": "completed",
                "extracted": extraction_result.extracted,
                "success_rate": extraction_result.success_rate,
                "jsons_uploaded": upload_json_result["uploaded"]
            }
        
        # ====================================================================
        # PASO 3: REPORTING
        # ====================================================================
        print()
        print("=" * 80)
        print("PASO 3/3: REPORTING")
        print("=" * 80)
        result["steps"]["reporting"]["status"] = "running"
        
        # Crear directorio temporal para descargar JSONs desde SFTP
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_json_dir = Path(temp_dir) / "json"
            temp_json_dir.mkdir()
            
            print(f"📥 Descargando JSONs desde SFTP para reporte...")
            # TODO: Implementar descarga masiva desde SFTP
            # Por ahora, usar JSONs locales del paso anterior
            
            # Generar CSV consolidado
            csv_output = Path(settings.data_dir) / f"{job_id}_consolidado.csv"
            json_source = Path(settings.data_dir) / "json_output"
            
            report_result = generate_csv_report(json_source, csv_output)
            
            # Subir CSV a SFTP
            print()
            print("📤 Subiendo CSV a SFTP...")
            remote_csv_path = f"{settings.sftp_base_path}/{job_id}/reports/consolidado.csv"
            
            asyncio.run(
                sftp.upload_file(csv_output, remote_csv_path)
            )
            
            print(f"✅ CSV subido: consolidado.csv")
            
            # Subir metadata
            metadata_path = Path(scraping_result.metadata_file)
            remote_metadata_path = f"{settings.sftp_base_path}/{job_id}/metadata/scraping_metadata.json"
            
            asyncio.run(
                sftp.upload_file(metadata_path, remote_metadata_path)
            )
            
            print(f"✅ Metadata subida")
            
            result["steps"]["reporting"] = {
                "status": "completed",
                "rows_exported": report_result["exported"],
                "total_prestacion": report_result["total_prestacion"],
                "total_copago": report_result["total_copago"]
            }
        
        # ====================================================================
        # FINALIZACIÓN
        # ====================================================================
        print()
        print("=" * 80)
        print("🎉 PIPELINE COMPLETADO EXITOSAMENTE")
        print("=" * 80)
        print(f"📊 Resumen:")
        print(f"   PDFs descargados: {result['steps']['scraping']['pdfs_downloaded']}")
        print(f"   JSONs extraídos: {result['steps']['extraction']['extracted']}")
        print(f"   Filas en CSV: {result['steps']['reporting']['rows_exported']}")
        print(f"   📁 Archivos en SFTP: {settings.sftp_base_path}/{job_id}/")
        print("=" * 80)
        
        result["status"] = "completed"
        result["completed_at"] = datetime.now().isoformat()
        result["sftp_path"] = f"{settings.sftp_base_path}/{job_id}/"
        
        return result
        
    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ ERROR EN PIPELINE: {str(e)}")
        print("=" * 80)
        
        result["status"] = "failed"
        result["error"] = str(e)
        result["failed_at"] = datetime.now().isoformat()
        
        # Marcar el paso que falló
        for step_name, step_data in result["steps"].items():
            if step_data["status"] == "running":
                step_data["status"] = "failed"
                step_data["error"] = str(e)
                break
        
        raise


def run_pipeline_with_state(
    session_id: str,
    storage_state: dict,
    job_id: str,
    year: int,
    month: str,
    prestador: str,
    client_id: str
) -> Dict[str, Any]:
    """
    Ejecuta el pipeline completo usando storageState capturado (API v2).
    
    Este worker RQ se usa cuando el usuario completa login manual en el navegador
    remoto. El sistema captura el storageState y lo pasa a este worker que ejecuta
    el scraping en modo headless (sin GUI).
    
    Args:
        session_id: ID de la sesión de navegador remoto
        storage_state: Dict con cookies y localStorage capturados
        job_id: ID único del job (ej: "febrero_2025_1729634567")
        year: Año del período
        month: Mes del período (ej: "FEBRERO")
        prestador: RUT y nombre del prestador (opcional)
        client_id: ID del cliente que solicitó el proceso
    
    Returns:
        Diccionario con resultado del pipeline
    """
    print("=" * 80)
    print(f"🚀 INICIANDO PIPELINE CON STORAGE STATE - Job ID: {job_id}")
    print("=" * 80)
    print(f"🔑 Session ID: {session_id}")
    print(f"📅 Período: {month} {year}")
    print(f"🏥 Prestador: {prestador or 'TODOS'}")
    print(f"👤 Client ID: {client_id}")
    print(f"🍪 Cookies en storage: {len(storage_state.get('cookies', []))}")
    print()
    
    result = {
        "job_id": job_id,
        "session_id": session_id,
        "client_id": client_id,
        "status": "pending",
        "steps": {
            "scraping": {"status": "pending"},
            "extraction": {"status": "pending"},
            "reporting": {"status": "pending"}
        }
    }
    
    try:
        # PASO 1: SCRAPING (con storageState - headless)
        print("=" * 80)
        print("PASO 1/3: SCRAPING (Headless con storageState)")
        print("=" * 80)
        result["steps"]["scraping"]["status"] = "running"
        
        orchestrator = ProcessOrchestrator(data_dir=settings.data_dir)
        
        params = ScrapingParams(
            year=year,
            month=month,
            prestador=prestador,
            username="",  # No necesario - ya autenticado
            password=""   # No necesario - ya autenticado
        )
        
        # Scraping con storageState
        scraping_result = asyncio.run(
            orchestrator.run_with_storage_state(storage_state, params)
        )
        
        if not scraping_result.validation_passed:
            raise Exception(f"Validación fallida: {scraping_result.validation.dict()}")
        
        # Subir PDFs a SFTP
        print("\n📤 Subiendo PDFs a SFTP...")
        sftp = SFTPClient()
        pdf_dir = Path(scraping_result.pdf_directory)
        remote_pdf_path = f"{settings.sftp_base_path}/{job_id}/pdfs"
        
        upload_result = asyncio.run(
            sftp.upload_directory(pdf_dir, remote_pdf_path, "*.pdf")
        )
        
        print(f"✅ PDFs subidos: {upload_result['uploaded']}/{upload_result['total']}")
        
        result["steps"]["scraping"] = {
            "status": "completed",
            "pdfs_downloaded": scraping_result.successful,
            "pdfs_uploaded": upload_result["uploaded"]
        }
        
        # PASO 2: EXTRACTION
        print("\n" + "=" * 80)
        print("PASO 2/3: EXTRACTION")
        print("=" * 80)
        result["steps"]["extraction"]["status"] = "running"
        
        extraction_result = orchestrator.run_extraction(scraping_result)
        
        # Subir JSONs
        print("\n📤 Subiendo JSONs a SFTP...")
        json_dir = Path(settings.data_dir) / "json_output"
        remote_json_path = f"{settings.sftp_base_path}/{job_id}/json"
        
        upload_json_result = asyncio.run(
            sftp.upload_directory(json_dir, remote_json_path, "*.json")
        )
        
        print(f"✅ JSONs subidos: {upload_json_result['uploaded']}/{upload_json_result['total']}")
        
        result["steps"]["extraction"] = {
            "status": "completed",
            "extracted": extraction_result.extracted
        }
        
        # PASO 3: REPORTING
        print("\n" + "=" * 80)
        print("PASO 3/3: REPORTING")
        print("=" * 80)
        result["steps"]["reporting"]["status"] = "running"
        
        csv_output = Path(settings.data_dir) / f"{job_id}_consolidado.csv"
        json_source = Path(settings.data_dir) / "json_output"
        
        report_result = generate_csv_report(json_source, csv_output)
        
        # Subir CSV
        print("\n📤 Subiendo CSV a SFTP...")
        remote_csv_path = f"{settings.sftp_base_path}/{job_id}/reports/consolidado.csv"
        
        asyncio.run(sftp.upload_file(csv_output, remote_csv_path))
        
        print(f"✅ CSV subido")
        
        result["steps"]["reporting"] = {
            "status": "completed",
            "rows_exported": report_result["exported"]
        }
        
        # FINALIZACIÓN
        print("\n" + "=" * 80)
        print("🎉 PIPELINE COMPLETADO (storageState)")
        print("=" * 80)
        
        result["status"] = "completed"
        result["completed_at"] = datetime.now().isoformat()
        result["sftp_path"] = f"{settings.sftp_base_path}/{job_id}/"
        
        return result
        
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ ERROR: {str(e)}")
        print("=" * 80)
        
        result["status"] = "failed"
        result["error"] = str(e)
        result["failed_at"] = datetime.now().isoformat()
        
        for step_name, step_data in result["steps"].items():
            if step_data["status"] == "running":
                step_data["status"] = "failed"
                break
        
        raise

