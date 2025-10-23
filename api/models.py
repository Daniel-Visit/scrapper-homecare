"""
Modelos de datos (DTOs) para la API REST.
Define request/response schemas usando Pydantic.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class MonthEnum(str, Enum):
    """Meses válidos para scraping."""
    ENERO = "ENERO"
    FEBRERO = "FEBRERO"
    MARZO = "MARZO"
    ABRIL = "ABRIL"
    MAYO = "MAYO"
    JUNIO = "JUNIO"
    JULIO = "JULIO"
    AGOSTO = "AGOSTO"
    SEPTIEMBRE = "SEPTIEMBRE"
    OCTUBRE = "OCTUBRE"
    NOVIEMBRE = "NOVIEMBRE"
    DICIEMBRE = "DICIEMBRE"


class TriggerRequest(BaseModel):
    """Request body para endpoint /trigger."""
    
    year: int = Field(..., ge=2020, le=2030, description="Año del período a procesar")
    month: MonthEnum = Field(..., description="Mes del período a procesar")
    prestador: Optional[str] = Field(
        None, 
        description="RUT y nombre del prestador (ej: '76190254-7 - SOLUCIONES INTEGRALES'). Si es None, procesa todos."
    )
    username: str = Field(..., description="RUT del usuario para login en Cruz Blanca")
    password: str = Field(..., description="Contraseña del usuario")
    
    class Config:
        json_schema_extra = {
            "example": {
                "year": 2025,
                "month": "FEBRERO",
                "prestador": None,
                "username": "12345678-9",
                "password": "tu-contraseña"
            }
        }


class TriggerResponse(BaseModel):
    """Response del endpoint /trigger."""
    
    job_id: str = Field(..., description="ID único del job")
    message: str = Field(..., description="Mensaje descriptivo")
    estimated_time_minutes: int = Field(..., description="Tiempo estimado de procesamiento en minutos")
    sftp_path: str = Field(..., description="Ruta donde se guardarán los archivos en SFTP")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "febrero_2025_1729634567",
                "message": "Proceso iniciado. Resuelve el CAPTCHA en el navegador que se abrirá.",
                "estimated_time_minutes": 5,
                "sftp_path": "/scraping_data/febrero_2025_1729634567/"
            }
        }


class JobStatusEnum(str, Enum):
    """Estados posibles de un job."""
    PENDING = "pending"
    SCRAPING = "scraping"
    EXTRACTING = "extracting"
    REPORTING = "reporting"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatusResponse(BaseModel):
    """Response del endpoint /jobs/{job_id} (opcional para observabilidad)."""
    
    job_id: str
    status: JobStatusEnum
    progress_percent: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "febrero_2025_1729634567",
                "status": "scraping",
                "progress_percent": 30,
                "message": "Descargando PDFs: 18/60",
                "error": None
            }
        }


class HealthResponse(BaseModel):
    """Response del endpoint /healthz."""
    
    status: str = Field(..., description="Estado del servicio")
    version: str = Field(..., description="Versión de la API")
    redis_connected: bool = Field(..., description="Conexión a Redis OK")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "redis_connected": True
            }
        }


class ErrorResponse(BaseModel):
    """Response estándar de error."""
    
    detail: str = Field(..., description="Mensaje de error")
    
    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Invalid API key"
            }
        }

