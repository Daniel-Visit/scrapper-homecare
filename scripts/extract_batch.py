#!/usr/bin/env python3.11
"""
Script de producción para extracción batch de PDFs.
Procesa todos los PDFs de un directorio con validación automática.
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Agregar el directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.extractor import PDFExtractor
from scraper.pdf_validator import PDFValidator


def is_valid_pdf(file_path: Path) -> bool:
    """Verifica si es un archivo PDF válido (no temporal, no corrupto)."""
    # Ignorar archivos temporales y del sistema
    if file_path.name.startswith('.'):
        return False
    if file_path.name.startswith('~'):
        return False
    if file_path.suffix.lower() != '.pdf':
        return False
    if file_path.stat().st_size == 0:
        return False
    
    return True


def sanitize_filename(pdf_name: str) -> str:
    """Convierte nombre de PDF a nombre de JSON limpio."""
    # Remover extensión
    base = pdf_name.replace('.pdf', '').replace('.PDF', '')
    # Remover caracteres problemáticos
    clean = base.replace('+', '_').replace(' ', '_')
    return f"{clean}.json"


def process_pdf_batch(
    input_dir: Path,
    output_dir: Path,
    log_dir: Path,
    verbose: bool = False
) -> Dict:
    """
    Procesa todos los PDFs de un directorio.
    
    Args:
        input_dir: Directorio con PDFs
        output_dir: Directorio para JSONs validados
        log_dir: Directorio para logs de errores
        verbose: Mostrar detalles
    
    Returns:
        Dict con estadísticas del proceso
    """
    # Crear directorios si no existen
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Obtener todos los PDFs válidos
    all_files = list(input_dir.glob('*'))
    pdf_files = [f for f in all_files if is_valid_pdf(f)]
    pdf_files.sort()  # Ordenar alfabéticamente
    
    if not pdf_files:
        print(f"❌ No se encontraron PDFs válidos en {input_dir}")
        return {"success": False, "total": 0}
    
    print(f"{'='*80}")
    print(f"EXTRACCIÓN BATCH DE PDFs")
    print(f"{'='*80}")
    print(f"📁 Directorio: {input_dir}")
    print(f"📄 PDFs encontrados: {len(pdf_files)}")
    print(f"📂 Salida: {output_dir}")
    
    # Filtros aplicados
    ignored_count = len(all_files) - len(pdf_files)
    if ignored_count > 0:
        print(f"⚠️  Archivos ignorados (no PDF/temporales): {ignored_count}")
    
    print(f"\n{'='*80}")
    print("PROCESANDO...")
    print(f"{'='*80}\n")
    
    # Inicializar procesadores
    extractor = PDFExtractor()
    validator = PDFValidator()
    
    # Resultados
    results = []
    start_time = datetime.now()
    
    # Procesar cada PDF
    for idx, pdf_path in enumerate(pdf_files, 1):
        pdf_name = pdf_path.name
        progress = f"[{idx}/{len(pdf_files)}]"
        
        print(f"{progress} {pdf_name}...", end=" ", flush=True)
        
        try:
            # Extraer
            json_data = extractor.extract_from_file(str(pdf_path))
            
            # Validar
            validation = validator.validate(str(pdf_path), json_data)
            
            if validation["is_valid"]:
                # Guardar JSON validado
                json_filename = sanitize_filename(pdf_name)
                output_file = output_dir / json_filename
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2, ensure_ascii=False)
                
                print(f"✅")
                
                results.append({
                    "pdf": pdf_name,
                    "json": json_filename,
                    "success": True,
                    "errors": 0,
                    "prestacion": json_data['resumen']['filas']['totales']['prestacion'],
                    "items": sum(len(sec['items']) for sec in json_data['detalle'])
                })
            else:
                # Validación falló
                print(f"❌ {validation['total_errors']} errores")
                
                # Guardar log de errores
                error_log = log_dir / f"{sanitize_filename(pdf_name)}.errors.json"
                with open(error_log, 'w', encoding='utf-8') as f:
                    json.dump({
                        "pdf": pdf_name,
                        "timestamp": datetime.now().isoformat(),
                        "validation": validation,
                        "json_data": json_data
                    }, f, indent=2, ensure_ascii=False)
                
                if verbose:
                    for err in validation["errors"][:3]:
                        print(f"      - [{err.get('section', '?')}] {err.get('field', '?')}: {err.get('error', '?')}")
                
                results.append({
                    "pdf": pdf_name,
                    "json": None,
                    "success": False,
                    "errors": validation['total_errors'],
                    "prestacion": 0,
                    "items": 0
                })
        
        except Exception as e:
            print(f"❌ Exception: {str(e)[:60]}")
            
            # Guardar log de excepción
            error_log = log_dir / f"{sanitize_filename(pdf_name)}.exception.json"
            with open(error_log, 'w', encoding='utf-8') as f:
                json.dump({
                    "pdf": pdf_name,
                    "timestamp": datetime.now().isoformat(),
                    "exception": str(e),
                    "type": type(e).__name__
                }, f, indent=2, ensure_ascii=False)
            
            if verbose:
                import traceback
                traceback.print_exc()
            
            results.append({
                "pdf": pdf_name,
                "json": None,
                "success": False,
                "errors": -1,
                "prestacion": 0,
                "items": 0
            })
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Generar reporte
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful
    total_prestacion = sum(r["prestacion"] for r in results if r["success"])
    total_items = sum(r["items"] for r in results if r["success"])
    
    print(f"\n{'='*80}")
    print("REPORTE FINAL")
    print(f"{'='*80}")
    print(f"✅ PDFs exitosos: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")
    print(f"❌ PDFs fallidos: {failed}/{len(results)}")
    print(f"⏱️  Tiempo total: {duration:.1f}s ({duration/len(results):.2f}s/PDF)")
    print(f"💰 Total prestación: ${total_prestacion:,}")
    print(f"📋 Total items: {total_items}")
    
    if successful > 0:
        print(f"📊 Promedio prestación/PDF: ${total_prestacion/successful:,.0f}")
        print(f"📊 Promedio items/PDF: {total_items/successful:.1f}")
    
    # Guardar reporte completo
    report_file = output_dir / "_reporte_extraccion.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "input_dir": str(input_dir),
            "output_dir": str(output_dir),
            "total_pdfs": len(results),
            "successful": successful,
            "failed": failed,
            "duration_seconds": duration,
            "total_prestacion": total_prestacion,
            "total_items": total_items,
            "results": results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Reporte guardado: {report_file}")
    
    if failed > 0:
        print(f"\n⚠️  Revisar logs de errores en: {log_dir}")
        print(f"PDFs fallidos:")
        for r in results:
            if not r["success"]:
                error_msg = f"{r['errors']} errores" if r['errors'] >= 0 else "excepción"
                print(f"  ❌ {r['pdf']} ({error_msg})")
    else:
        print(f"\n🎉 TODOS LOS PDFs PROCESADOS EXITOSAMENTE")
    
    return {
        "success": failed == 0,
        "total": len(results),
        "successful": successful,
        "failed": failed,
        "duration": duration
    }


def main():
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Extracción batch de PDFs de liquidación Cruz Blanca"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Directorio con PDFs a procesar"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/json_output",
        help="Directorio para JSONs validados (default: data/json_output)"
    )
    parser.add_argument(
        "--logs",
        type=str,
        default="data/extraction_logs",
        help="Directorio para logs de errores (default: data/extraction_logs)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Mostrar detalles de errores"
    )
    
    args = parser.parse_args()
    
    # Convertir a Path
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    log_dir = Path(args.logs)
    
    # Validar que input_dir existe
    if not input_dir.exists():
        print(f"❌ Error: Directorio no existe: {input_dir}")
        sys.exit(1)
    
    if not input_dir.is_dir():
        print(f"❌ Error: No es un directorio: {input_dir}")
        sys.exit(1)
    
    # Procesar
    result = process_pdf_batch(input_dir, output_dir, log_dir, args.verbose)
    
    # Exit code
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()



