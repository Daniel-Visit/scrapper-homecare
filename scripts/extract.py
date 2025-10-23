#!/usr/bin/env python3
"""
Script independiente para ejecutar solo extracción de PDFs.

Uso:
    python scripts/extraction.py --input data/pdfs/enero_2025_xxx/ --output data/json/enero_2025.json
    python scripts/extraction.py --input data/pdfs/enero_2025_xxx/ --output data/json/enero_2025.json --metadata data/results/enero_2025_xxx_results.json
"""

import argparse
import sys
from pathlib import Path

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.extractor import PDFExtractor


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="Extrae datos estructurados de PDFs de Cruz Blanca"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Directorio con archivos PDF a procesar"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Archivo JSON de salida con datos extraídos"
    )
    parser.add_argument(
        "--metadata",
        default=None,
        help="Archivo JSON con metadata del scraping (opcional)"
    )
    
    args = parser.parse_args()
    
    # Validar inputs
    input_dir = Path(args.input)
    if not input_dir.exists():
        print(f"❌ Error: El directorio de entrada no existe: {args.input}")
        sys.exit(1)
    
    if not input_dir.is_dir():
        print(f"❌ Error: La ruta de entrada no es un directorio: {args.input}")
        sys.exit(1)
    
    if args.metadata:
        metadata_file = Path(args.metadata)
        if not metadata_file.exists():
            print(f"⚠️  Advertencia: Archivo de metadata no existe: {args.metadata}")
            print("   Continuando sin metadata...")
            args.metadata = None
    
    print("=" * 60)
    print("EXTRACCIÓN DE DATOS DE PDFs")
    print("=" * 60)
    print(f"📂 Directorio entrada: {args.input}")
    print(f"💾 Archivo salida: {args.output}")
    if args.metadata:
        print(f"📄 Metadata: {args.metadata}")
    print()
    
    # Ejecutar extracción
    try:
        extractor = PDFExtractor()
        
        # Extraer datos
        extracted_data = extractor.extract_from_directory(
            dir_path=str(input_dir),
            metadata_file=args.metadata
        )
        
        if not extracted_data:
            print("\n⚠️  No se extrajeron datos de ningún PDF")
            sys.exit(1)
        
        # Guardar resultados
        extractor.save_to_json(extracted_data, args.output)
        
        # Validar extracción
        validation = extractor.validate_extraction(extracted_data)
        
        print("\n" + "=" * 60)
        print("📊 RESULTADO DE LA EXTRACCIÓN")
        print("=" * 60)
        print(f"📄 Total archivos procesados: {validation['total_files']}")
        print(f"✅ Extraídos exitosamente: {validation['extracted']}")
        print(f"❌ Fallidos: {validation['failed']}")
        print(f"📈 Tasa de éxito: {validation['success_rate']}%")
        print(f"💾 Archivo salida: {args.output}")
        print()
        
        if validation['passed']:
            print("🎯 VALIDACIÓN: ✅ EXITOSA")
            print("   ✅ Tasa de éxito >= 95%")
        else:
            print("⚠️  VALIDACIÓN: ❌ FALLIDA")
            print(f"   ❌ Tasa de éxito: {validation['success_rate']}% (mínimo 95%)")
            if validation['failed_files']:
                print(f"   ❌ Archivos fallidos: {len(validation['failed_files'])}")
        
        sys.exit(0 if validation['passed'] else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error durante la extracción: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

