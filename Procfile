# Railway Procfile
# Define los procesos que Railway debe ejecutar

# API Service (web)
web: uvicorn api.main:app --host 0.0.0.0 --port $PORT

# Worker Service (worker RQ)
worker: rq worker --url $REDIS_URL default

