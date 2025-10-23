#!/usr/bin/env python3.11
"""
Script para generar reporte CSV consolidado desde JSONs extraídos.
"""

import json
import csv
import sys
from pathlib import Path
from typing import List, Dict


def extract_summary_data(json_file: Path) -> Dict:
    """
    Extrae campos clave de un JSON de liquidación.
    
    Returns:
        Dict con los campos para el CSV
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return {
        'rut_paciente': data['paciente']['rut'],
        'n_spm': data['plan']['n_spm'],
        'fecha_inicio': data['plan']['inicio_hospitalizacion'],
        'total_prestacion': data['resumen']['filas']['totales']['prestacion'],
        'copago_afiliado': data['resumen']['filas']['totales']['copago_afiliado']
    }


def generate_csv_report(json_dir: Path, output_csv: Path) -> Dict:
    """
    Genera CSV consolidado desde todos los JSONs.
    
    Args:
        json_dir: Directorio con JSONs
        output_csv: Archivo CSV de salida
    
    Returns:
        Dict con estadísticas del proceso
    """
    # Obtener todos los JSONs (excluyendo el reporte)
    json_files = sorted([
        f for f in json_dir.glob('*.json')
        if f.name != '_reporte_extraccion.json'
    ])
    
    if not json_files:
        print(f"❌ No se encontraron JSONs en {json_dir}")
        return {"success": False, "total": 0}
    
    print(f"{'='*80}")
    print(f"GENERACIÓN DE REPORTE CSV")
    print(f"{'='*80}")
    print(f"📁 Directorio: {json_dir}")
    print(f"📄 JSONs encontrados: {len(json_files)}")
    print(f"📊 Archivo salida: {output_csv}")
    print(f"\n{'='*80}")
    print("PROCESANDO...")
    print(f"{'='*80}\n")
    
    # Procesar cada JSON
    rows = []
    errors = []
    
    for idx, json_file in enumerate(json_files, 1):
        try:
            summary = extract_summary_data(json_file)
            summary['archivo_json'] = json_file.name
            rows.append(summary)
            
            if idx % 10 == 0:
                print(f"  Procesados: {idx}/{len(json_files)}")
        
        except Exception as e:
            error_msg = f"Error en {json_file.name}: {str(e)}"
            errors.append(error_msg)
            print(f"  ⚠️  {error_msg}")
    
    # Escribir CSV
    if rows:
        with open(output_csv, 'w', encoding='utf-8', newline='') as f:
            # Headers
            fieldnames = [
                'RUT Paciente',
                'N° SPM',
                'Fecha Inicio Hospitalización',
                'Total Prestación',
                'Copago Afiliado'
            ]
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            # Datos
            for row in rows:
                writer.writerow({
                    'RUT Paciente': row['rut_paciente'],
                    'N° SPM': row['n_spm'],
                    'Fecha Inicio Hospitalización': row['fecha_inicio'],
                    'Total Prestación': f"${row['total_prestacion']:,}",
                    'Copago Afiliado': f"${row['copago_afiliado']:,}"
                })
    
    # Estadísticas
    total_prestacion = sum(r['total_prestacion'] for r in rows)
    total_copago = sum(r['copago_afiliado'] for r in rows)
    
    print(f"\n{'='*80}")
    print("REPORTE GENERADO")
    print(f"{'='*80}")
    print(f"✅ Filas exportadas: {len(rows)}/{len(json_files)}")
    
    if errors:
        print(f"⚠️  Errores: {len(errors)}")
        for err in errors[:5]:
            print(f"    - {err}")
    
    print(f"\n📊 TOTALES:")
    print(f"    Total Prestación: ${total_prestacion:,}")
    print(f"    Total Copago: ${total_copago:,}")
    
    print(f"\n💾 Archivo guardado: {output_csv}")
    print(f"{'='*80}")
    
    return {
        "success": len(errors) == 0,
        "total": len(json_files),
        "exported": len(rows),
        "errors": len(errors),
        "total_prestacion": total_prestacion,
        "total_copago": total_copago
    }


def main():
    """Punto de entrada principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Genera reporte CSV consolidado desde JSONs de liquidación"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="data/json_output",
        help="Directorio con JSONs (default: data/json_output)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/reporte_consolidado.csv",
        help="Archivo CSV de salida (default: data/reporte_consolidado.csv)"
    )
    
    args = parser.parse_args()
    
    # Convertir a Path
    json_dir = Path(args.input)
    output_csv = Path(args.output)
    
    # Validar que json_dir existe
    if not json_dir.exists():
        print(f"❌ Error: Directorio no existe: {json_dir}")
        sys.exit(1)
    
    # Crear directorio de salida si no existe
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    
    # Generar reporte
    result = generate_csv_report(json_dir, output_csv)
    
    # Exit code
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()

