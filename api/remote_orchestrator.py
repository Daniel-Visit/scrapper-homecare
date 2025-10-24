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
    
    def __init__(
        self, 
        viewer_host: str = "viewer", 
        viewer_display: str = ":99",
        use_cdp: bool = False
    ):
        """
        Args:
            viewer_host: Hostname del contenedor viewer
            viewer_display: Display de X11 (ej: :99)
            use_cdp: Si True, usa CDP para conectar a Chromium remoto
        """
        self.viewer_host = viewer_host
        self.viewer_display = viewer_display
        self.use_cdp = use_cdp
        self.active_sessions: Dict[str, Dict] = {}
        
    async def start_remote_session(
        self,
        session_id: str,
        cdp_port: Optional[int] = 9222
    ) -> Dict:
        """
        Inicia una sesión de navegador remoto en el viewer container.
        
        Soporta dos modos:
        - Modo local (use_cdp=False): Lanza Chromium en display local compartido
        - Modo CDP (use_cdp=True): Conecta a Chromium remoto via CDP
        
        Args:
            session_id: ID único de la sesión
            cdp_port: Puerto CDP para conexión remota (default: 9222)
            
        Returns:
            Dict con metadata de la sesión
        """
        logger.info(f"🚀 Iniciando sesión remota: {session_id}")
        logger.info(f"   Modo: {'CDP' if self.use_cdp else 'Local Display'}")
        
        try:
            playwright = await async_playwright().start()
            
            if self.use_cdp:
                # Modo CDP: Conectar a Chromium remoto ya corriendo
                cdp_url = f"http://{self.viewer_host}:{cdp_port}"
                logger.info(f"📡 Conectando via CDP a: {cdp_url}")
                
                try:
                    browser = await playwright.chromium.connect_over_cdp(cdp_url)
                    logger.info(f"✅ Conectado exitosamente via CDP")
                except Exception as e:
                    logger.error(f"❌ Error conectando via CDP: {e}")
                    raise Exception(f"No se pudo conectar a Chromium via CDP en {cdp_url}. Asegúrate de que el viewer está corriendo.")
            
            else:
                # Modo local: Lanzar Chromium en display compartido
                logger.info(f"📺 Lanzando Chromium en display {self.viewer_display}")
                
                browser = await playwright.chromium.launch(
                    headless=False,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--start-maximized'
                    ],
                    env={
                        'DISPLAY': self.viewer_display
                    }
                )
            
            context = await browser.new_context(
                accept_downloads=True,
                no_viewport=True  # Sin viewport fijo, se adapta al tamaño de la ventana
            )
            
            page = await context.new_page()
            
            # Navegar a Cruz Blanca Extranet (página de login)
            logger.info(f"🌐 Navegando a Cruz Blanca Extranet login...")
            await page.goto("https://extranet.cruzblanca.cl/login.aspx", timeout=30000)
            
            # SANITY CHECK: Verificar que Playwright controla la instancia visible
            await page.evaluate("document.title = '🟢 CONTROL PLAYWRIGHT';")
            current_title = await page.title()
            logger.info(f"🔍 Playwright title set: {current_title}")
            print(f"🔍 SANITY CHECK - Title: {current_title}", flush=True)
            
            # Guardar sesión activa
            session_data = {
                'session_id': session_id,
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
        timeout_seconds: int = 600  # 10 minutos
    ) -> bool:
        """
        Espera login con polling robusto (URL + selector + cookies).
        
        Detecta login exitoso mediante:
        1. URL contiene "Extranet.aspx"
        2. Selector #menuPrincipal está presente
        3. Cookies ASP.NET + URL correcta
        
        Args:
            session_id: ID de la sesión
            timeout_seconds: Timeout en segundos (default: 10 min)
            
        Returns:
            True si login exitoso, False si timeout
        """
        if session_id not in self.active_sessions:
            raise ValueError(f"Sesión {session_id} no existe")
        
        session = self.active_sessions[session_id]
        page: Page = session['page']
        
        import time
        t0 = time.time()
        last_url = ""
        poll_interval = 2  # segundos
        
        logger.info(f"⏳ Esperando login con polling cada {poll_interval}s (timeout: {timeout_seconds}s)")
        print(f"⏳ Esperando login con polling cada {poll_interval}s", flush=True)
        
        iteration = 0
        while time.time() - t0 < timeout_seconds:
            iteration += 1
            elapsed = int(time.time() - t0)
            
            try:
                current_url = page.url
                
                # Log cada 10 iteraciones para confirmar que el bucle está activo
                if iteration % 10 == 0:
                    logger.info(f"🔄 Polling activo - Iteración {iteration}, Elapsed: {elapsed}s")
                    print(f"🔄 Polling #{iteration} ({elapsed}s)", flush=True)
                
                # Log cambio de URL
                if current_url != last_url:
                    logger.info(f"📍 URL actual: {current_url}")
                    print(f"📍 URL: {current_url}", flush=True)
                    last_url = current_url
                
                # 1) Detectar por URL
                if "Extranet.aspx" in current_url:
                    logger.info(f"✅ Login detectado por URL match")
                    print(f"✅ Login detectado por URL match", flush=True)
                    session['login_completed'] = True
                    return True
                
                # 2) Detectar por selector (más robusto para páginas ASP.NET)
                try:
                    await page.wait_for_selector("#menuPrincipal", timeout=poll_interval * 1000)
                    logger.info(f"✅ Login detectado por selector #menuPrincipal")
                    print(f"✅ Login detectado por selector", flush=True)
                    session['login_completed'] = True
                    return True
                except Exception:
                    pass
                
                # 3) Detectar por cookie ASP.NET (señal débil pero útil)
                cookies = await page.context.cookies()
                session_cookies = [c for c in cookies if "sessionid" in c["name"].lower()]
                if session_cookies and "Extranet.aspx" in current_url:
                    logger.info(f"✅ Login detectado por cookies ASP.NET")
                    print(f"✅ Login detectado por cookies", flush=True)
                    session['login_completed'] = True
                    return True
                    
            except Exception as e:
                logger.error(f"⚠️ Error en polling: {e}")
                print(f"⚠️ Error polling: {e}", flush=True)
            
            await asyncio.sleep(poll_interval)
        
        logger.warning(f"⏰ Timeout esperando login para sesión {session_id}")
        print(f"⏰ Timeout esperando login", flush=True)
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


# Instancia global del orquestador (modo legacy - display compartido)
# NOTA: Para modo multi-cliente con CDP, crear instancia con use_cdp=True en api/main.py
remote_orchestrator = RemoteOrchestrator(use_cdp=False)

