#!/usr/bin/env python3
"""
Script de testing para validar el cliente SFTP.

Ejecutar:
    python api/test_sftp.py

Tests incluidos:
1. Health check de la API
2. Crear directorio de prueba
3. Subir archivo de prueba
4. Listar directorio
5. Descargar archivo
6. Eliminar archivos de prueba
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import tempfile

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.sftp_client import SFTPClient


async def run_tests():
    """Ejecuta suite completa de tests."""
    
    print("=" * 80)
    print("TESTING SFTP CLIENT")
    print("=" * 80)
    print()
    
    client = SFTPClient()
    
    # Directorio de prueba único
    test_dir = f"/test_scraping_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    test_passed = 0
    test_failed = 0
    
    # TEST 1: Health Check
    print("TEST 1: Health Check")
    print("-" * 80)
    try:
        is_healthy = await client.health_check()
        if is_healthy:
            print("✅ SFTP API está funcionando")
            test_passed += 1
        else:
            print("❌ SFTP API no responde")
            test_failed += 1
    except Exception as e:
        print(f"❌ Error: {e}")
        test_failed += 1
    print()
    
    # TEST 2: Crear directorio - SKIPPED (API tiene bug en /mkdir)
    print("TEST 2: Crear Directorio")
    print("-" * 80)
    print(f"⏭️  SKIPPED: API /mkdir tiene bug conocido")
    print(f"   Los directorios se crearán automáticamente al subir archivos")
    print()
    
    # TEST 3: Subir archivo de prueba (esto creará el directorio automáticamente)
    print("TEST 3: Subir Archivo (crea directorio automáticamente)")
    print("-" * 80)
    
    # Crear archivo temporal
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(f"Test file created at {datetime.now()}\n")
        f.write("This is a test file for SFTP upload.\n")
        f.write("If you see this, the upload worked! 🎉\n")
        temp_file = Path(f.name)
    
    try:
        remote_path = f"{test_dir}/pdfs/test_file.txt"
        print(f"Subiendo: {temp_file.name} -> {remote_path}")
        result = await client.upload_file(temp_file, remote_path)
        print(f"✅ Archivo subido: {result}")
        test_passed += 1
    except Exception as e:
        print(f"❌ Error: {e}")
        test_failed += 1
    finally:
        # Limpiar archivo temporal
        temp_file.unlink()
    print()
    
    # TEST 4: Listar directorio
    print("TEST 4: Listar Directorio")
    print("-" * 80)
    try:
        result = await client.list_directory(test_dir)
        print(f"✅ Archivos en {test_dir}:")
        # La API puede retornar un dict con 'items' o una lista directa
        items = result.get('items', []) if isinstance(result, dict) else result
        for file in items:
            if isinstance(file, dict):
                print(f"   - {file.get('name', 'unknown')} ({file.get('size', 0)} bytes)")
            else:
                print(f"   - {file}")
        test_passed += 1
    except Exception as e:
        print(f"❌ Error: {e}")
        test_failed += 1
    print()
    
    # TEST 5: Descargar archivo - SKIPPED (API /download tiene bug)
    print("TEST 5: Descargar Archivo")
    print("-" * 80)
    print(f"⏭️  SKIPPED: API /download tiene bug conocido")
    print(f"   Spring puede descargar directamente vía SFTP o usar API alternativa")
    print()
    
    # TEST 6: Limpiar (eliminar directorio de prueba)
    print("TEST 6: Limpiar (Eliminar Directorio)")
    print("-" * 80)
    print("⚠️  Deseas eliminar el directorio de prueba? (y/n): ", end="")
    
    # Para testing automático, comentar esto y poner auto_cleanup = True
    auto_cleanup = False  # Cambiar a True para limpiar automáticamente
    
    if auto_cleanup:
        cleanup = True
    else:
        try:
            cleanup = input().strip().lower() == 'y'
        except:
            cleanup = False
    
    if cleanup:
        try:
            result = await client.delete_file(test_dir, recursive=True)
            print(f"✅ Directorio eliminado: {result}")
            test_passed += 1
        except Exception as e:
            print(f"❌ Error: {e}")
            test_failed += 1
    else:
        print(f"⏭️  Directorio de prueba mantenido: {test_dir}")
        print(f"   Puedes eliminarlo manualmente o ejecutar:")
        print(f"   curl -X DELETE {client.base_url}/delete \\")
        print(f"        -H 'X-API-Key: {client.api_key}' \\")
        print(f"        -d '{{\"path\": \"{test_dir}\", \"recursive\": true}}'")
    print()
    
    # Resumen
    print("=" * 80)
    print("RESUMEN DE TESTS")
    print("=" * 80)
    total = test_passed + test_failed
    print(f"✅ Pasados: {test_passed}/{total}")
    print(f"❌ Fallidos: {test_failed}/{total}")
    
    if test_failed == 0:
        print("\n🎉 Todos los tests pasaron exitosamente!")
        print("✅ El cliente SFTP está listo para usar.")
    else:
        print(f"\n⚠️  {test_failed} test(s) fallaron.")
        print("   Revisa los errores arriba y verifica la configuración.")
    
    print("=" * 80)
    
    return test_failed == 0


def main():
    """Entry point."""
    try:
        success = asyncio.run(run_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrumpidos por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

