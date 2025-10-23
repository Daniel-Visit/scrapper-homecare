"""
Cliente SFTP para subir archivos a Digital Ocean vía API HTTP.

Basado en la API documentada en postman_collection.json.
Base URL: https://sftp-api-production.up.railway.app
"""

import httpx
from pathlib import Path
from typing import List, Dict, Optional
import asyncio

from api.config import settings


class SFTPClient:
    """Cliente para interactuar con la SFTP API."""
    
    def __init__(self, base_url: str = None, api_key: str = None):
        """
        Inicializa el cliente SFTP.
        
        Args:
            base_url: URL base de la API SFTP (default: settings.sftp_api_url)
            api_key: API key para autenticación (default: settings.sftp_api_key)
        """
        self.base_url = base_url or settings.sftp_api_url
        self.api_key = api_key or settings.sftp_api_key
        self.headers = {
            "X-API-Key": self.api_key
        }
    
    async def health_check(self) -> bool:
        """
        Verifica que la API SFTP está funcionando.
        
        Returns:
            True si la API responde OK, False en caso contrario
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/healthz", timeout=10.0)
                return response.status_code == 200
            except Exception as e:
                print(f"❌ Error al conectar con SFTP API: {e}")
                return False
    
    async def create_directory(self, path: str) -> Dict:
        """
        Crea un directorio en SFTP.
        
        Args:
            path: Ruta del directorio (ej: "/scraping_data/febrero_2025_123")
        
        Returns:
            Diccionario con el resultado
        
        Raises:
            httpx.HTTPStatusError: Si la petición falla
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mkdir",
                headers=self.headers,
                json={"path": path},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def list_directory(self, path: str = "/") -> List[Dict]:
        """
        Lista archivos y directorios en una ruta.
        
        Args:
            path: Ruta a listar (default: "/")
        
        Returns:
            Lista de diccionarios con información de archivos/directorios
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/list",
                headers=self.headers,
                params={"path": path},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def upload_file(self, local_path: Path, remote_path: str) -> Dict:
        """
        Sube un archivo a SFTP.
        
        Args:
            local_path: Ruta local del archivo
            remote_path: Ruta destino en SFTP (ej: "/scraping_data/job_id/pdfs/file.pdf")
        
        Returns:
            Diccionario con el resultado
        
        Raises:
            FileNotFoundError: Si el archivo local no existe
            httpx.HTTPStatusError: Si la petición falla
        """
        if not local_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {local_path}")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(local_path, 'rb') as f:
                files = {'file': (local_path.name, f, 'application/octet-stream')}
                data = {'remote_path': remote_path}
                
                response = await client.post(
                    f"{self.base_url}/upload",
                    headers=self.headers,
                    files=files,
                    data=data
                )
                response.raise_for_status()
                return response.json()
    
    async def upload_directory(
        self, 
        local_dir: Path, 
        remote_base_path: str,
        pattern: str = "*"
    ) -> Dict:
        """
        Sube todos los archivos de un directorio a SFTP.
        
        Args:
            local_dir: Directorio local
            remote_base_path: Ruta base en SFTP
            pattern: Patrón de archivos (default: "*" = todos)
        
        Returns:
            Diccionario con estadísticas: {uploaded, failed, errors}
        """
        local_dir = Path(local_dir)
        
        if not local_dir.exists():
            raise FileNotFoundError(f"Directorio no encontrado: {local_dir}")
        
        # Obtener archivos a subir
        files = list(local_dir.glob(pattern))
        
        if not files:
            return {
                "uploaded": 0,
                "failed": 0,
                "errors": [],
                "message": f"No se encontraron archivos con patrón '{pattern}' en {local_dir}"
            }
        
        # Crear directorio remoto
        try:
            await self.create_directory(remote_base_path)
        except Exception as e:
            # Puede fallar si ya existe, no es crítico
            pass
        
        # Subir archivos
        uploaded = 0
        failed = 0
        errors = []
        
        for file_path in files:
            if not file_path.is_file():
                continue
            
            remote_path = f"{remote_base_path}/{file_path.name}"
            
            try:
                await self.upload_file(file_path, remote_path)
                uploaded += 1
                print(f"  ✅ Subido: {file_path.name}")
            except Exception as e:
                failed += 1
                error_msg = f"Error al subir {file_path.name}: {str(e)}"
                errors.append(error_msg)
                print(f"  ❌ {error_msg}")
        
        return {
            "uploaded": uploaded,
            "failed": failed,
            "total": len(files),
            "errors": errors
        }
    
    async def download_file(self, remote_path: str, local_path: Path) -> None:
        """
        Descarga un archivo desde SFTP.
        
        Args:
            remote_path: Ruta del archivo en SFTP
            local_path: Ruta local donde guardar
        
        Raises:
            httpx.HTTPStatusError: Si la petición falla
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(
                f"{self.base_url}/download",
                headers=self.headers,
                params={"path": remote_path}
            )
            response.raise_for_status()
            
            # Guardar archivo
            local_path.parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, 'wb') as f:
                f.write(response.content)
    
    async def delete_file(self, path: str, recursive: bool = False) -> Dict:
        """
        Elimina un archivo o directorio de SFTP.
        
        Args:
            path: Ruta a eliminar
            recursive: Si True, elimina directorios con contenido
        
        Returns:
            Diccionario con el resultado
        """
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/delete",
                headers=self.headers,
                json={"path": path, "recursive": recursive},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()


# Helper function para usar en código sincrónico
def upload_directory_sync(local_dir: Path, remote_path: str, pattern: str = "*") -> Dict:
    """
    Versión sincrónica de upload_directory.
    
    Args:
        local_dir: Directorio local
        remote_path: Ruta destino en SFTP
        pattern: Patrón de archivos
    
    Returns:
        Diccionario con estadísticas
    """
    client = SFTPClient()
    return asyncio.run(client.upload_directory(local_dir, remote_path, pattern))

