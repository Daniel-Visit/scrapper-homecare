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

# Upstash requiere SSL - convertir redis:// a rediss:// solo para Upstash
if redis_url.startswith('redis://') and 'upstash.io' in redis_url:
    redis_url = redis_url.replace('redis://', 'rediss://', 1)
    print(f"🔒 Usando SSL para conexión a Upstash Redis", flush=True)
else:
    print(f"🔓 Usando conexión sin SSL a Redis local", flush=True)

# Configurar conexión a Redis
redis_conn = Redis.from_url(
    redis_url,
    decode_responses=False,
    socket_keepalive=True,
    health_check_interval=30,
    socket_connect_timeout=10,
    retry_on_timeout=True
)

# Verificar conexión
try:
    redis_conn.ping()
    print("✅ Connected to Redis successfully", flush=True)
    print(f"📋 Redis URL: {redis_url[:20]}...", flush=True)
except Exception as e:
    print(f"❌ Failed to connect to Redis: {e}", flush=True)
    raise

# Iniciar worker
print(f"🚀 Starting RQ worker on queue 'default'...", flush=True)
worker = Worker(['default'], connection=redis_conn)
print(f"👷 Worker started, waiting for jobs...", flush=True)
worker.work(with_scheduler=True)

