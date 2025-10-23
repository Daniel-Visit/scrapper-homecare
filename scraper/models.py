"""Modelos de datos simplificados para el proceso de scraping y extracción."""

from typing import List, Optional
from pydantic import BaseModel, Field


class ScrapingParams(BaseModel):
    """Parámetros para ejecutar scraping."""
    year: str
    month: str
    prestador: Optional[str] = None
    username: str
    password: str


class ValidationReport(BaseModel):
    """Reporte de validación del scraping."""
    passed: bool
    total_expected: int
    total_downloaded: int
    success_rate: float
    failed_records: List[dict] = Field(default_factory=list)
    corrupted_files: List[str] = Field(default_factory=list)


class ScrapingResult(BaseModel):
    """Resultado del proceso de scraping."""
    job_id: str
    year: str
    month: str
    prestador: Optional[str] = None
    total_pdfs: int
    successful: int
    failed: int
    validation: ValidationReport
    pdf_directory: str
    metadata_file: str
    
    @property
    def validation_passed(self) -> bool:
        """Indica si la validación fue exitosa."""
        return self.validation.passed


class ExtractionResult(BaseModel):
    """Resultado del proceso de extracción."""
    job_id: str
    total_files: int
    extracted: int
    failed: int
    success_rate: float
    output_file: str
    failed_files: List[str] = Field(default_factory=list)
