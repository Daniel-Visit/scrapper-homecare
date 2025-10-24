"""
Docker Manager API - Gestiona viewers dinámicos por cliente.

Pool fijo de 10 puertos:
- noVNC: 6080-6089
- CDP: 9222-9231

Cada cliente obtiene un slot dedicado con su propio viewer container.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import docker
from typing import Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Docker Manager API", version="1.0.0")

class ViewerRequest(BaseModel):
    """Request para obtener un viewer."""
    client_id: str

class ViewerResponse(BaseModel):
    """Response con info del viewer asignado."""
    client_id: str
    container_name: str
    novnc_port: int
    cdp_port: int
    status: str  # 'running' | 'created' | 'started'
    viewer_url: str
    slot_index: int

# Pool de 10 slots fijos
PORT_POOL = [
    {'novnc': 6080, 'cdp': 9222},
    {'novnc': 6081, 'cdp': 9223},
    {'novnc': 6082, 'cdp': 9224},
    {'novnc': 6083, 'cdp': 9225},
    {'novnc': 6084, 'cdp': 9226},
    {'novnc': 6085, 'cdp': 9227},
    {'novnc': 6086, 'cdp': 9228},
    {'novnc': 6087, 'cdp': 9229},
    {'novnc': 6088, 'cdp': 9230},
    {'novnc': 6089, 'cdp': 9231},
]

class ViewerManager:
    """Gestiona pool de viewers por cliente."""
    
    def __init__(self, docker_host: str = "localhost"):
        self._docker_client = None
        self.docker_host = docker_host
        
        # Mapeos de asignación de slots
        self.client_slots: Dict[str, int] = {}  # client_id → slot_index
        self.slot_clients: Dict[int, str] = {}  # slot_index → client_id
        
        logger.info(f"🚀 ViewerManager inicializado con {len(PORT_POOL)} slots disponibles")
    
    @property
    def docker_client(self):
        """Lazy loading del cliente Docker."""
        if self._docker_client is None:
            try:
                # Intentar diferentes métodos de conexión
                import platform
                if platform.system() == "Darwin":  # macOS
                    # En Mac, usar socket de Docker Desktop
                    self._docker_client = docker.DockerClient(base_url='unix:///var/run/docker.sock')
                else:
                    # En Linux/otros, usar configuración automática
                    self._docker_client = docker.from_env()
                
                # Verificar conexión
                self._docker_client.ping()
                logger.info("✅ Conectado a Docker daemon")
            except Exception as e:
                logger.error(f"❌ Error conectando a Docker: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"No se pudo conectar a Docker daemon: {str(e)}"
                )
        return self._docker_client
    
    def get_or_create_viewer(self, client_id: str) -> ViewerResponse:
        """
        Obtiene o crea un viewer para el cliente.
        
        Args:
            client_id: Identificador único del cliente
            
        Returns:
            ViewerResponse con info del viewer
            
        Raises:
            HTTPException: Si no hay slots disponibles (429)
        """
        # Sanitizar client_id para nombre de container válido
        safe_id = self._sanitize_client_id(client_id)
        container_name = f"viewer-{safe_id}"
        
        logger.info(f"📞 Solicitud de viewer para cliente: {client_id}")
        
        # Si cliente ya tiene slot asignado, usar ese
        if client_id in self.client_slots:
            slot_idx = self.client_slots[client_id]
            logger.info(f"♻️  Cliente {client_id} ya tiene slot {slot_idx} asignado")
            return self._get_or_start_container(client_id, container_name, slot_idx)
        
        # Buscar primer slot libre
        for idx, ports in enumerate(PORT_POOL):
            if idx not in self.slot_clients:
                # Slot libre encontrado, asignar
                logger.info(f"🆕 Asignando slot {idx} a cliente {client_id}")
                self.client_slots[client_id] = idx
                self.slot_clients[idx] = client_id
                return self._get_or_start_container(client_id, container_name, idx)
        
        # No hay slots libres
        logger.warning(f"⚠️  Sin slots disponibles para {client_id}")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Maximum concurrent clients reached",
                "message": "10 clientes simultáneos activos. Intenta en 15-30 minutos.",
                "max_slots": len(PORT_POOL),
                "used_slots": len(self.slot_clients),
                "active_clients": list(self.client_slots.keys())
            }
        )
    
    def _get_or_start_container(
        self, 
        client_id: str, 
        container_name: str, 
        slot_idx: int
    ) -> ViewerResponse:
        """Obtiene container existente o crea uno nuevo."""
        ports = PORT_POOL[slot_idx]
        
        try:
            # Intentar obtener container existente
            container = self.docker_client.containers.get(container_name)
            
            if container.status != 'running':
                logger.info(f"▶️  Iniciando container existente: {container_name}")
                container.start()
                status = 'started'
            else:
                logger.info(f"✅ Container ya corriendo: {container_name}")
                status = 'running'
            
        except docker.errors.NotFound:
            # Container no existe, crear nuevo
            logger.info(f"🔨 Creando nuevo container: {container_name}")
            
            try:
                container = self.docker_client.containers.run(
                    image="scraper-viewer:latest",
                    name=container_name,
                    detach=True,
                    ports={
                        '6080/tcp': ports['novnc'],
                        '9222/tcp': ports['cdp']
                    },
                    environment={'DISPLAY': ':99'},
                    shm_size='2g',
                    restart_policy={'Name': 'unless-stopped'},
                    remove=False
                )
                status = 'created'
                logger.info(f"✅ Container creado exitosamente: {container_name}")
                
            except docker.errors.ImageNotFound:
                raise HTTPException(
                    status_code=500,
                    detail="Imagen 'scraper-viewer:latest' no encontrada. Ejecuta: docker build -t scraper-viewer:latest -f docker/viewer/Dockerfile ."
                )
            except Exception as e:
                logger.error(f"❌ Error creando container: {e}")
                raise HTTPException(status_code=500, detail=f"Error creando container: {str(e)}")
        
        viewer_url = f"http://{self.docker_host}:{ports['novnc']}/vnc.html?resize=remote&autoconnect=true"
        
        return ViewerResponse(
            client_id=client_id,
            container_name=container_name,
            novnc_port=ports['novnc'],
            cdp_port=ports['cdp'],
            status=status,
            viewer_url=viewer_url,
            slot_index=slot_idx
        )
    
    def release_slot(self, client_id: str) -> bool:
        """
        Libera el slot de un cliente.
        
        Args:
            client_id: ID del cliente
            
        Returns:
            True si se liberó, False si no estaba asignado
        """
        if client_id in self.client_slots:
            slot_idx = self.client_slots[client_id]
            del self.client_slots[client_id]
            del self.slot_clients[slot_idx]
            logger.info(f"🔓 Slot {slot_idx} liberado de cliente {client_id}")
            return True
        
        logger.warning(f"⚠️  Cliente {client_id} no tenía slot asignado")
        return False
    
    def _sanitize_client_id(self, client_id: str) -> str:
        """Convierte client_id en nombre válido de container."""
        # Convertir a lowercase, reemplazar espacios y caracteres especiales
        safe = client_id.lower()
        safe = safe.replace('_', '-').replace(' ', '-').replace('.', '-')
        # Limitar longitud
        safe = safe[:30]
        return safe


# Instancia global del manager
viewer_manager = ViewerManager()


# === ENDPOINTS ===

@app.get("/")
async def root():
    """Health check."""
    return {
        "service": "Docker Manager API",
        "status": "healthy",
        "version": "1.0.0"
    }


@app.post("/viewer/get", response_model=ViewerResponse)
async def get_viewer(request: ViewerRequest):
    """
    Obtiene o crea un viewer para el cliente especificado.
    
    Args:
        request: ViewerRequest con client_id
        
    Returns:
        ViewerResponse con info del viewer asignado
    """
    return viewer_manager.get_or_create_viewer(request.client_id)


@app.post("/viewer/release/{client_id}")
async def release_viewer(client_id: str):
    """
    Libera el slot de un cliente (opcional, para cleanup manual).
    
    Args:
        client_id: ID del cliente a liberar
    """
    released = viewer_manager.release_slot(client_id)
    
    if released:
        return {
            "message": f"Slot liberado para cliente: {client_id}",
            "status": "released"
        }
    else:
        return {
            "message": f"Cliente {client_id} no tenía slot asignado",
            "status": "not_found"
        }


@app.get("/viewer/status")
async def get_status():
    """
    Obtiene el estado actual del pool de viewers.
    
    Returns:
        Estado del pool (slots usados, disponibles, clientes activos)
    """
    return {
        "total_slots": len(PORT_POOL),
        "used_slots": len(viewer_manager.slot_clients),
        "available_slots": len(PORT_POOL) - len(viewer_manager.slot_clients),
        "active_clients": list(viewer_manager.client_slots.keys()),
        "slot_assignments": {
            f"slot_{idx}": client_id 
            for client_id, idx in viewer_manager.client_slots.items()
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

