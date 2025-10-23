"""
FastAPI application principal.

Expone endpoints REST para:
- Health check
- Trigger de procesos de scraping
- (Opcional) Consulta de estado de jobs
- (Opcional) Download de archivos desde SFTP
"""

from fastapi import FastAPI, Header, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from rq import Queue
import time

from api.config import settings
from api.models import HealthResponse, ErrorResponse, TriggerRequest, TriggerResponse
from api.tasks import run_pipeline
from api import __version__

# Inicializar FastAPI
app = FastAPI(
    title="Scraping Microservice API",
    description="API REST para scraping de Cruz Blanca con extracción de datos y subida a SFTP",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc"
)


# Dependency: Verificar API Key
async def verify_api_key(x_api_key: str = Header(..., description="API Key para autenticación")):
    """
    Dependency que verifica el API key en el header X-API-Key.
    
    Raises:
        HTTPException: Si el API key es inválido
    """
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return x_api_key


# Healthcheck endpoint (sin autenticación)
@app.get(
    "/healthz",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check",
    description="Verifica que la API está funcionando y tiene conexión a Redis"
)
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        HealthResponse con status, versión y estado de conexión a Redis
    """
    # Verificar conexión a Redis
    redis_connected = False
    try:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        redis_client.ping()
        redis_connected = True
    except (RedisConnectionError, Exception):
        pass
    
    return HealthResponse(
        status="healthy" if redis_connected else "degraded",
        version=__version__,
        redis_connected=redis_connected
    )


# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    """Redirect a /docs."""
    return JSONResponse({
        "message": "Scraping Microservice API",
        "version": __version__,
        "docs": "/docs"
    })


# ====================================================================
# ENDPOINTS PRINCIPALES
# ====================================================================

@app.post(
    "/api/v1/scraping/trigger",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Scraping"],
    summary="Gatilla proceso de scraping",
    description="Encola un job de scraping en background. El proceso se ejecuta de forma asíncrona."
)
async def trigger_scraping(
    request: TriggerRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Gatilla el proceso de scraping + extracción + reporte.
    
    El job se encola en Redis y se procesa en background por un worker RQ.
    El usuario debe resolver el CAPTCHA manualmente cuando se abra el navegador.
    
    Returns:
        TriggerResponse con job_id y información del proceso
    """
    # Generar job_id único
    timestamp = int(time.time())
    job_id = f"{request.month.lower()}_{request.year}_{timestamp}"
    
    try:
        # Conectar a Redis
        redis_conn = Redis.from_url(settings.redis_url, decode_responses=False)
        queue = Queue(connection=redis_conn)
        
        # Encolar job
        job = queue.enqueue(
            run_pipeline,
            job_id=job_id,
            year=request.year,
            month=request.month.value,
            prestador=request.prestador,
            username=request.username,
            password=request.password,
            job_timeout=f'{settings.job_timeout_minutes}m',
            result_ttl=86400,  # Guardar resultado 24 horas
            failure_ttl=86400  # Guardar fallos 24 horas
        )
        
        return TriggerResponse(
            job_id=job_id,
            message="Proceso iniciado. Resuelve el CAPTCHA en el navegador que se abrirá.",
            estimated_time_minutes=settings.job_timeout_minutes // 2,
            sftp_path=f"{settings.sftp_base_path}/{job_id}/"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al encolar job: {str(e)}"
        )


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handler para HTTPExceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handler para excepciones no controladas."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

