#!/usr/bin/env python3
"""
Script orquestador del proceso completo: scraping → validación → extracción.

Uso:
    # Proceso completo
    python scripts/run_process.py --year 2025 --month ENERO
    
    # Solo scraping
    python scripts/run_process.py --year 2025 --month ENERO --skip-extraction
    
    # Solo extracción (requiere scraping previo)
    python scripts/run_process.py --year 2025 --month ENERO --skip-scraping
    
    # Con prestador específico
    python scripts/run_process.py --year 2025 --month ENERO --prestador "76190254-7 - SOLUCIONES..."
"""

import argparse
import getpass
import sys
from pathlib import Path

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.models import ScrapingParams
from scraper.orchestrator import ProcessOrchestrator


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="Ejecuta el proceso completo de scraping y extracción de Cruz Blanca"
    )
    parser.add_argument(
        "--year",
        required=True,
        help="Año a procesar (ej: 2025)"
    )
    parser.add_argument(
        "--month",
        required=True,
        help="Mes a procesar (ej: ENERO, FEBRERO, etc.)"
    )
    parser.add_argument(
        "--prestador",
        default=None,
        help="RUT y nombre del prestador (opcional, si no se especifica procesa todos)"
    )
    parser.add_argument(
        "--skip-scraping",
        action="store_true",
        help="Salta el scraping (usa datos existentes)"
    )
    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Salta la extracción (solo scraping)"
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directorio base para datos (default: data)"
    )
    
    args = parser.parse_args()
    
    # Validar combinaciones
    if args.skip_scraping and args.skip_extraction:
        print("❌ Error: No se puede saltar scraping y extracción al mismo tiempo")
        sys.exit(1)
    
    # No solicitar credenciales - se ingresan manualmente en el navegador
    username = "manual"  # Placeholder - el usuario ingresará en el navegador
    password = "manual"  # Placeholder - el usuario ingresará en el navegador
    
    if not args.skip_scraping:
        print("=" * 60)
        print("⚠️  INSTRUCCIONES")
        print("=" * 60)
        print("1. El navegador se abrirá automáticamente")
        print("2. Ingresa tu RUT y contraseña en el sitio web")
        print("3. Resuelve el CAPTCHA")
        print("4. El script detectará el login y continuará automáticamente")
        print("=" * 60)
        input("\n✅ Presiona ENTER cuando estés listo para continuar...")
        print()
    
    print("=" * 60)
    print("PARÁMETROS DEL PROCESO")
    print("=" * 60)
    print(f"📅 Año: {args.year}")
    print(f"📅 Mes: {args.month.upper()}")
    print(f"🏥 Prestador: {args.prestador or 'TODOS'}")
    print(f"📂 Directorio datos: {args.data_dir}")
    
    if args.skip_scraping:
        print("⏭️  Modo: Solo extracción (scraping omitido)")
    elif args.skip_extraction:
        print("⏭️  Modo: Solo scraping (extracción omitida)")
    else:
        print("🔄 Modo: Proceso completo")
    
    print()
    
    # Crear parámetros
    params = ScrapingParams(
        year=args.year,
        month=args.month.upper(),
        prestador=args.prestador,
        username=username or "",
        password=password or ""
    )
    
    # Ejecutar proceso
    orchestrator = ProcessOrchestrator(data_dir=args.data_dir)
    
    try:
        result = orchestrator.run_full_process(
            params=params,
            skip_scraping=args.skip_scraping,
            skip_extraction=args.skip_extraction
        )
        
        # Mostrar resultado
        print("\n" + "=" * 60)
        print("📊 RESULTADO FINAL")
        print("=" * 60)
        
        status = result.get("status")
        
        if status == "completed":
            print("✅ Proceso completado exitosamente")
            
            scraping = result.get("scraping")
            if scraping:
                print(f"\n📥 SCRAPING:")
                print(f"   Job ID: {scraping['job_id']}")
                print(f"   PDFs descargados: {scraping['successful']}")
                print(f"   Tasa de éxito: {scraping['validation']['success_rate']}%")
            
            extraction = result.get("extraction")
            if extraction:
                print(f"\n📤 EXTRACCIÓN:")
                print(f"   Archivos procesados: {extraction['total_files']}")
                print(f"   Extraídos: {extraction['extracted']}")
                print(f"   Tasa de éxito: {extraction['success_rate']}%")
                print(f"   Archivo salida: {extraction['output_file']}")
            
            sys.exit(0)
            
        elif status == "validation_failed":
            print("❌ Proceso detenido por validación fallida")
            
            scraping = result.get("scraping")
            if scraping:
                print(f"\n⚠️  SCRAPING:")
                print(f"   Tasa de éxito: {scraping['validation']['success_rate']}%")
                print(f"   PDFs fallidos: {scraping['failed']}")
                print(f"   ❌ No se cumplieron los criterios de calidad")
            
            sys.exit(1)
        
        else:
            print(f"⚠️  Estado desconocido: {status}")
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error durante el proceso: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

