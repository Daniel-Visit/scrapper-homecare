"""
Módulo de scraping y extracción de datos de Isapres chilenas.

Componentes:
- cruzblanca: Scraper para Cruz Blanca Extranet
- isapre_x: Placeholder para otros scrapers
- extractor: Extracción de datos de PDFs
- orchestrator: Coordinador del proceso completo
- models: Modelos de datos
"""

from scraper.cruzblanca import CruzBlancaScraper
from scraper.extractor import PDFExtractor
from scraper.orchestrator import ProcessOrchestrator
from scraper.models import ScrapingParams, ScrapingResult, ExtractionResult

__all__ = [
    "CruzBlancaScraper",
    "PDFExtractor",
    "ProcessOrchestrator",
    "ScrapingParams",
    "ScrapingResult",
    "ExtractionResult",
]


