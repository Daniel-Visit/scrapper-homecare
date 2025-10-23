#!/usr/bin/env python3.11
"""
Script para ejecutar scraping de Cruz Blanca con argumentos CLI.

Uso:
    python3.11 scripts/scrape.py --year 2025 --month FEBRERO
    python3.11 scripts/scrape.py --year 2025 --month ENERO --prestador "76190254-7 - SOLUCIONES..."
"""

import argparse
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.cruzblanca import CruzBlancaScraper


async def main_async(year: str, month: str, prestador: str = None):
    """Ejecuta el scraper de forma asíncrona."""
    
    print("=" * 60)
    print(f"SCRAPER CRUZ BLANCA - {month} {year}")
    print("=" * 60)
    print()
    
    # Parámetros
    job_id = f"{month.lower()}_{year}_{int(asyncio.get_event_loop().time())}"
    params = {
        "year": year,
        "month": month.upper(),
        "prestador": prestador,
        "job_id": job_id
    }
    
    print(f"📅 Período: {params['month']} {params['year']}")
    print(f"🏥 Prestador: {params['prestador'] or 'TODOS'}")
    print()
    print("⚠️  El navegador se abrirá automáticamente")
    print("⚠️  Ingresa tu RUT, contraseña y resuelve el CAPTCHA")
    print("⚠️  NO CIERRES LA VENTANA MANUALMENTE")
    print()
    input("Presiona ENTER para continuar...")
    print()
    
    async with async_playwright() as p:
        # Lanzar navegador
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=200
        )
        
        context = await browser.new_context(
            accept_downloads=True
        )
        
        page = await context.new_page()
        
        # Crear scraper
        scraper = CruzBlancaScraper(output_dir=Path("data"))
        scraper.context = context
        scraper.page = page
        scraper.job_id = params["job_id"]
        
        try:
            # Login manual
            await scraper.login_via_context(page, "manual", "manual")
            
            # Scraping
            all_pdfs = await scraper.discover_documents(page, params)
            
            print(f"\n✅ PROCESO COMPLETADO")
            print(f"📊 Total PDFs descargados: {len(all_pdfs)}")
            print(f"📂 Ubicación: data/pdfs/{params['job_id']}/")
            print(f"📄 Metadata: data/results/{params['job_id']}_results.json")
            
            return len(all_pdfs)
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return 0
        finally:
            await browser.close()


def main():
    """Función principal con argumentos CLI."""
    parser = argparse.ArgumentParser(
        description="Ejecuta scraping de Cruz Blanca para un período específico"
    )
    parser.add_argument(
        "--year",
        required=True,
        help="Año a scrapear (ej: 2025)"
    )
    parser.add_argument(
        "--month",
        required=True,
        help="Mes a scrapear (ej: ENERO, FEBRERO, etc.)"
    )
    parser.add_argument(
        "--prestador",
        default=None,
        help="RUT y nombre del prestador (opcional)"
    )
    
    args = parser.parse_args()
    
    # Ejecutar scraping
    try:
        total_pdfs = asyncio.run(main_async(
            year=args.year,
            month=args.month,
            prestador=args.prestador
        ))
        
        sys.exit(0 if total_pdfs > 0 else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error durante el scraping: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
