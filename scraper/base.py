"""
Clase base para scrapers.
Define la interfaz común que deben implementar todos los scrapers.
"""

from typing import Any, Dict, Iterable, List
from playwright.async_api import Page


class ScraperBase:
    """Clase base para todos los scrapers."""
    
    site_id: str
    
    def __init__(self):
        """Inicializa el scraper base."""
        pass
    
    async def login_via_context(self, page: Page, username: str, password: str) -> None:
        """
        Realiza login en el sitio.
        
        Args:
            page: Página de Playwright
            username: Nombre de usuario/RUT
            password: Contraseña
        """
        raise NotImplementedError("Cada scraper debe implementar login_via_context")
    
    async def discover_documents(self, page: Page, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Descubre documentos disponibles en el sitio.
        
        Args:
            page: Página de Playwright
            params: Parámetros de búsqueda (filtros, fechas, etc.)
            
        Returns:
            Lista de diccionarios con información de documentos encontrados
        """
        raise NotImplementedError("Cada scraper debe implementar discover_documents")
    
    def extract(self, pdf_path: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extrae información de un PDF descargado.
        
        Args:
            pdf_path: Ruta al archivo PDF
            metadata: Metadatos del documento
            
        Returns:
            Lista de registros extraídos del PDF
        """
        raise NotImplementedError("Cada scraper debe implementar extract")
    
    def postprocess(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Post-procesamiento de registros extraídos.
        
        Args:
            records: Registros extraídos
            
        Returns:
            Registros post-procesados
        """
        return records