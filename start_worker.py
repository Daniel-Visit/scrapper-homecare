#!/usr/bin/env python3
"""
Script de inicio del worker RQ con soporte SSL para Upstash Redis.
"""

import os
from redis import Redis
from rq import Worker

# Obtener Redis URL desde env
redis_url = os.environ.get('REDIS_URL')

if not redis_url:
    raise ValueError("REDIS_URL environment variable is required")

# Configurar conexión a Redis
# Upstash Redis ya maneja SSL automáticamente cuando usamos rediss:// o el puerto 6379 con TLS
redis_conn = Redis.from_url(
    redis_url,
    decode_responses=False,
    socket_keepalive=True,
    health_check_interval=30
)

# Verificar conexión
try:
    redis_conn.ping()
    print("✅ Connected to Redis successfully")
except Exception as e:
    print(f"❌ Failed to connect to Redis: {e}")
    raise

# Iniciar worker
worker = Worker(['default'], connection=redis_conn)
print(f"🚀 Starting RQ worker...")
worker.work(with_scheduler=True)

