"""
FastAPI application principal.

Expone endpoints REST para:
- Health check
- Trigger de procesos de scraping
- (Opcional) Consulta de estado de jobs
- (Opcional) Download de archivos desde SFTP
"""

from fastapi import FastAPI, Header, HTTPException, status, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from rq import Queue
import time
import asyncio
from pathlib import Path

from api.config import settings
from api.models import (
    HealthResponse, ErrorResponse, TriggerRequest, TriggerResponse,
    RunRequest, RunResponse  # API v2
)
from api.tasks import run_pipeline, run_pipeline_with_state
from api.remote_orchestrator import remote_orchestrator
from api import __version__
import logging

logger = logging.getLogger(__name__)

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
        # Upstash requiere SSL - solo convertir si es upstash.io
        redis_url = settings.redis_url
        if redis_url.startswith('redis://') and 'upstash.io' in redis_url:
            redis_url = redis_url.replace('redis://', 'rediss://', 1)
        
        redis_client = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_keepalive=True,
            health_check_interval=30
        )
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
        "docs": "/docs",
        "test": "/test"
    })


# Test page endpoint
@app.get("/test", response_class=HTMLResponse, include_in_schema=False)
async def test_page():
    """Página de testing de la API."""
    html_path = Path(__file__).parent / "templates" / "test_api.html"
    
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(), status_code=200)
    else:
        return HTMLResponse(content="<h1>Test page not found</h1>", status_code=404)


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
        # Upstash requiere SSL - solo convertir si es upstash.io
        redis_url = settings.redis_url
        if redis_url.startswith('redis://') and 'upstash.io' in redis_url:
            redis_url = redis_url.replace('redis://', 'rediss://', 1)
        
        redis_conn = Redis.from_url(
            redis_url,
            decode_responses=False,
            socket_keepalive=True,
            health_check_interval=30
        )
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


# ====================================================================
# API V2: Remote Browser con storageState
# ====================================================================

async def background_wait_and_process(
    session_id: str,
    request: RunRequest
):
    """
    Tarea en background que lanza navegador, espera login, captura storageState y encola job.
    """
    import traceback
    logger.info(f"🔄🔄🔄 BACKGROUND TASK INICIADO para sesión {session_id}")
    print(f"🔄🔄🔄 BACKGROUND TASK INICIADO para sesión {session_id}", flush=True)
    
    try:
        # 1. Lanzar navegador remoto
        logger.info(f"🚀 Lanzando navegador para sesión {session_id}")
        print(f"🚀 Lanzando navegador para sesión {session_id}", flush=True)
        
        await remote_orchestrator.start_remote_session(session_id)
        
        logger.info(f"✅ Navegador lanzado para sesión {session_id}")
        print(f"✅ Navegador lanzado para sesión {session_id}", flush=True)
        
        # 2. Esperar login OK (máx 15 min)
        logger.info(f"⏳ Iniciando wait_for_login para {session_id}")
        print(f"⏳ Iniciando wait_for_login", flush=True)
        
        login_ok = await remote_orchestrator.wait_for_login(session_id, timeout_seconds=900)
        
        logger.info(f"🔍 wait_for_login retornó: {login_ok}")
        print(f"🔍 wait_for_login retornó: {login_ok}", flush=True)
        
        if not login_ok:
            logger.error(f"⏰ Timeout esperando login para {session_id}")
            print(f"⏰ Timeout esperando login", flush=True)
            await remote_orchestrator.close_session(session_id)
            return
        
        # 3. Capturar storageState
        logger.info(f"📸 Capturando storageState para {session_id}")
        print(f"📸 Capturando storageState", flush=True)
        
        storage_state = await remote_orchestrator.capture_storage_state(session_id)
        
        logger.info(f"🔍 storageState capturado: {storage_state is not None}")
        print(f"🔍 storageState: {storage_state is not None}", flush=True)
        
        if not storage_state:
            logger.error(f"❌ No se pudo capturar storageState para {session_id}")
            print(f"❌ No se pudo capturar storageState", flush=True)
            await remote_orchestrator.close_session(session_id)
            return
        
        # 4. Generar job_id para el pipeline
        logger.info(f"🔢 Generando job_id para {session_id}")
        print(f"🔢 Generando job_id", flush=True)
        
        timestamp = int(time.time())
        job_id = f"{request.month.lower()}_{request.year}_{timestamp}"
        
        logger.info(f"📤 Encolando job {job_id} con storageState")
        print(f"📤 Encolando job {job_id}", flush=True)
        
        # 5. Encolar job en RQ con storageState
        logger.info(f"🔗 Conectando a Redis para {session_id}")
        print(f"🔗 Conectando a Redis", flush=True)
        
        redis_url = settings.redis_url
        if redis_url.startswith('redis://') and 'upstash.io' in redis_url:
            redis_url = redis_url.replace('redis://', 'rediss://', 1)
        
        logger.info(f"🔗 Creando conexión Redis")
        print(f"🔗 Creando conexión Redis", flush=True)
        
        redis_conn = Redis.from_url(
            redis_url,
            decode_responses=False,
            socket_keepalive=True,
            health_check_interval=30
        )
        
        logger.info(f"📋 Creando cola RQ")
        print(f"📋 Creando cola RQ", flush=True)
        
        queue = Queue(connection=redis_conn)
        
        logger.info(f"➕ Encolando job en RQ")
        print(f"➕ Encolando job en RQ", flush=True)
        
        job = queue.enqueue(
            run_pipeline_with_state,
            # Parámetros de la función (en orden)
            session_id,
            storage_state,
            job_id,
            str(request.year),  # Convertir a string
            request.month.value,
            request.prestador,
            request.client_id,
            # Parámetros de RQ
            job_timeout=f'{settings.job_timeout_minutes}m',
            result_ttl=86400,
            failure_ttl=86400
        )
        
        logger.info(f"✅ Job {job_id} encolado exitosamente (RQ job: {job.id})")
        print(f"✅ Job {job_id} encolado (RQ: {job.id})", flush=True)
        
        # 6. Cerrar sesión de navegador (ya no la necesitamos)
        logger.info(f"🔒 Cerrando sesión {session_id}")
        print(f"🔒 Cerrando sesión", flush=True)
        
        await remote_orchestrator.close_session(session_id)
        
        logger.info(f"✅✅✅ Flujo completo exitoso para {session_id}")
        print(f"✅✅✅ Flujo completo exitoso", flush=True)
        
    except Exception as e:
        logger.error(f"❌❌❌ ERROR en background task para {session_id}: {e}")
        print(f"❌❌❌ ERROR en background task para {session_id}: {e}", flush=True)
        traceback.print_exc()
        try:
            await remote_orchestrator.close_session(session_id)
        except:
            pass


@app.post(
    "/api/v2/run",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["API v2 - Remote Browser"],
    summary="Iniciar scraping con navegador remoto",
    description="Inicia sesión de navegador remoto visible via noVNC. El usuario hace login manualmente, el sistema detecta login OK, captura storageState y ejecuta pipeline headless.",
    dependencies=[Depends(verify_api_key)]
)
async def run_remote_browser(
    request: RunRequest,
    background_tasks: BackgroundTasks
):
    """
    Endpoint v2 que usa navegador remoto con storageState.
    
    Flujo:
    1. Genera session_id único
    2. Inicia navegador en viewer container (visible via noVNC)
    3. Navega a Cruz Blanca login
    4. Devuelve viewer_url para que usuario vea el navegador
    5. En background: espera login OK, captura storageState, lanza worker headless
    
    Args:
        request: RunRequest con datos del scraping
        background_tasks: FastAPI background tasks
        
    Returns:
        RunResponse con session_id y viewer_url
    """
    # Generar session_id único
    timestamp = int(time.time())
    session_id = f"session_{request.month.lower()}_{request.year}_{timestamp}"
    
    # URL del viewer noVNC
    viewer_url = f"http://localhost:6080/vnc.html?resize=remote&autoconnect=true"
    
    # Callback para capturar excepciones del task
    def task_done_callback(task):
        try:
            task.result()  # Esto levantará la excepción si hubo una
        except Exception as e:
            logger.error(f"❌ Background task falló: {e}")
            print(f"❌ Background task falló: {e}", flush=True)
            import traceback
            traceback.print_exc()
    
    # Lanzar background task que inicia navegador, espera login y procesa
    task = asyncio.create_task(background_wait_and_process(session_id, request))
    task.add_done_callback(task_done_callback)  # Capturar excepciones
    
    logger.info(f"✅ Sesión {session_id} encolada, background task iniciado")
    print(f"✅ Sesión {session_id} encolada, background task CREADO", flush=True)
    
    return RunResponse(
        session_id=session_id,
        viewer_url=viewer_url,
        message="Sesión iniciada. Abre el viewer_url en un popup, haz login en Cruz Blanca y resuelve el CAPTCHA. El sistema detectará automáticamente cuando completes el login y continuará el proceso en segundo plano.",
        estimated_time_minutes=15
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

