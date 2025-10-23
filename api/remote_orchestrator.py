"""
Orquestador para navegador remoto con noVNC.

Funciones principales:
- start_remote_session: inicia navegador en viewer container
- wait_for_login: detecta cuando el usuario completó login
- capture_storage_state: captura cookies/session del navegador
- launch_headless_worker: ejecuta pipeline con storageState
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class RemoteOrchestrator:
    """Orquestador de sesiones de navegador remoto."""
    
    def __init__(self, viewer_host: str = "viewer", viewer_display: str = ":99"):
        """
        Args:
            viewer_host: Hostname del contenedor viewer
            viewer_display: Display de X11 (ej: :99)
        """
        self.viewer_host = viewer_host
        self.viewer_display = viewer_display
        self.active_sessions: Dict[str, Dict] = {}
        
    async def start_remote_session(
        self,
        session_id: str,
        username: str,
        password: str
    ) -> Dict:
        """
        Inicia una sesión de navegador remoto en el viewer container.
        
        Fase 3: Conecta al display del viewer y lanza Chromium visible via noVNC.
        
        Args:
            session_id: ID único de la sesión
            username: RUT para login (no usado aún, para futuro auto-fill)
            password: Contraseña para login (no usado aún, para futuro auto-fill)
            
        Returns:
            Dict con metadata de la sesión
        """
        logger.info(f"🚀 Iniciando sesión remota (Fase 3): {session_id}")
        
        try:
            playwright = await async_playwright().start()
            
            # Conectar al display del viewer
            # El viewer tiene DISPLAY=:99 con Xvfb corriendo
            logger.info(f"📺 Conectando a display {self.viewer_display} en {self.viewer_host}")
            
            browser = await playwright.chromium.launch(
                headless=False,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--window-size=1280,720'
                ],
                env={
                    'DISPLAY': self.viewer_display
                }
            )
            
            context = await browser.new_context(
                accept_downloads=True,
                viewport={'width': 1280, 'height': 720}
            )
            
            page = await context.new_page()
            
            # Navegar a Cruz Blanca login
            logger.info(f"🌐 Navegando a Cruz Blanca...")
            await page.goto("https://www.cruzblanca.cl/wps/portal/", timeout=30000)
            
            # Guardar sesión activa
            session_data = {
                'session_id': session_id,
                'username': username,
                'password': password,
                'created_at': datetime.now(),
                'login_completed': False,
                'storage_state': None,
                'playwright': playwright,
                'browser': browser,
                'context': context,
                'page': page
            }
            
            self.active_sessions[session_id] = session_data
            
            logger.info(f"✅ Sesión {session_id} iniciada - navegador visible en noVNC")
            return session_data
            
        except Exception as e:
            logger.error(f"❌ Error iniciando sesión {session_id}: {e}")
            raise
    
    async def wait_for_login(
        self,
        session_id: str,
        timeout_seconds: int = 900  # 15 minutos
    ) -> bool:
        """
        Espera a que el usuario complete el login manualmente.
        Detecta login exitoso cuando la URL cambia a /Privado/*.aspx
        
        Args:
            session_id: ID de la sesión
            timeout_seconds: Timeout en segundos (default: 15 min)
            
        Returns:
            True si login exitoso, False si timeout
        """
        if session_id not in self.active_sessions:
            raise ValueError(f"Sesión {session_id} no existe")
        
        session = self.active_sessions[session_id]
        page: Page = session['page']
        
        logger.info(f"⏳ Esperando login manual para sesión {session_id} (timeout: {timeout_seconds}s)")
        
        try:
            # Esperar a que la URL contenga "Privado" (indica login exitoso)
            await page.wait_for_url(
                "**/Privado/*.aspx",
                timeout=timeout_seconds * 1000
            )
            
            logger.info(f"✅ Login detectado para sesión {session_id}")
            session['login_completed'] = True
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Timeout esperando login para sesión {session_id}")
            return False
        except Exception as e:
            logger.error(f"❌ Error esperando login para {session_id}: {e}")
            return False
    
    async def capture_storage_state(self, session_id: str) -> Optional[Dict]:
        """
        Captura el storageState (cookies, localStorage) de la sesión.
        
        Args:
            session_id: ID de la sesión
            
        Returns:
            Dict con storageState o None si falla
        """
        if session_id not in self.active_sessions:
            raise ValueError(f"Sesión {session_id} no existe")
        
        session = self.active_sessions[session_id]
        
        if not session['login_completed']:
            logger.warning(f"⚠️ Intentando capturar storageState sin login completo: {session_id}")
        
        try:
            context: BrowserContext = session['context']
            
            logger.info(f"📸 Capturando storageState de sesión {session_id}")
            storage_state = await context.storage_state()
            
            session['storage_state'] = storage_state
            
            logger.info(f"✅ storageState capturado para {session_id}")
            logger.debug(f"   - Cookies: {len(storage_state.get('cookies', []))}")
            logger.debug(f"   - Origins: {len(storage_state.get('origins', []))}")
            
            return storage_state
            
        except Exception as e:
            logger.error(f"❌ Error capturando storageState de {session_id}: {e}")
            return None
    
    async def close_session(self, session_id: str):
        """
        Cierra una sesión y libera recursos.
        
        Args:
            session_id: ID de la sesión
        """
        if session_id not in self.active_sessions:
            logger.warning(f"⚠️ Sesión {session_id} no existe, nada que cerrar")
            return
        
        session = self.active_sessions[session_id]
        
        try:
            logger.info(f"🔒 Cerrando sesión {session_id}")
            
            # Cerrar browser context y browser
            context: BrowserContext = session.get('context')
            browser: Browser = session.get('browser')
            playwright = session.get('playwright')
            
            if context:
                await context.close()
            
            if browser:
                await browser.close()
            
            if playwright:
                await playwright.stop()
            
            # Remover de sesiones activas
            del self.active_sessions[session_id]
            
            logger.info(f"✅ Sesión {session_id} cerrada correctamente")
            
        except Exception as e:
            logger.error(f"❌ Error cerrando sesión {session_id}: {e}")
    
    async def get_session_status(self, session_id: str) -> Optional[Dict]:
        """
        Obtiene el estado actual de una sesión.
        
        Args:
            session_id: ID de la sesión
            
        Returns:
            Dict con status o None si no existe
        """
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        
        return {
            'session_id': session['session_id'],
            'created_at': session['created_at'].isoformat(),
            'login_completed': session['login_completed'],
            'has_storage_state': session['storage_state'] is not None
        }
    
    async def cleanup_old_sessions(self, max_age_seconds: int = 3600):
        """
        Limpia sesiones antiguas que no se completaron.
        
        Args:
            max_age_seconds: Edad máxima de sesión en segundos (default: 1 hora)
        """
        now = datetime.now()
        sessions_to_close = []
        
        for session_id, session in self.active_sessions.items():
            age = (now - session['created_at']).total_seconds()
            
            if age > max_age_seconds:
                logger.info(f"🧹 Sesión {session_id} expirada (edad: {age:.0f}s)")
                sessions_to_close.append(session_id)
        
        for session_id in sessions_to_close:
            await self.close_session(session_id)
        
        if sessions_to_close:
            logger.info(f"🧹 Limpiadas {len(sessions_to_close)} sesiones expiradas")


# Instancia global del orquestador
# Se usa desde el endpoint /api/v2/run
remote_orchestrator = RemoteOrchestrator()

