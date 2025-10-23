#!/bin/bash
set -e

echo "======================================"
echo "🧪 VALIDANDO STACK COMPLETO"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        exit 1
    fi
}

# 1. Check Docker
echo "1️⃣  Verificando Docker..."
docker --version > /dev/null 2>&1
print_status $? "Docker instalado"

docker-compose --version > /dev/null 2>&1
print_status $? "Docker Compose instalado"

# 2. Start stack
echo ""
echo "2️⃣  Iniciando servicios..."
docker-compose up -d
sleep 5

# 3. Check if services are running
echo ""
echo "3️⃣  Verificando servicios..."
VIEWER_RUNNING=$(docker-compose ps | grep "scraper-viewer" | grep "Up" | wc -l)
if [ "$VIEWER_RUNNING" -eq 1 ]; then
    print_status 0 "Viewer container corriendo"
else
    print_status 1 "Viewer container NO está corriendo"
fi

# 4. Wait for services to be healthy
echo ""
echo "4️⃣  Esperando que servicios estén listos (30s)..."
sleep 30

# 5. Test viewer HTTP endpoint
echo ""
echo "5️⃣  Testeando viewer (noVNC)..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:6080/)
if [ "$HTTP_CODE" -eq 200 ]; then
    print_status 0 "noVNC responde en http://localhost:6080/"
else
    echo -e "${RED}❌ noVNC no responde (HTTP $HTTP_CODE)${NC}"
    echo "Logs del viewer:"
    docker-compose logs viewer | tail -20
    exit 1
fi

# 6. Test viewer VNC endpoint
echo ""
echo "6️⃣  Testeando VNC port..."
if nc -z localhost 5900 2>/dev/null; then
    print_status 0 "VNC escuchando en puerto 5900"
else
    print_status 1 "VNC NO está escuchando en puerto 5900"
fi

# 7. Check viewer processes inside container
echo ""
echo "7️⃣  Verificando procesos dentro del viewer..."
XVFB_RUNNING=$(docker-compose exec -T viewer ps aux | grep "Xvfb" | grep -v "grep" | wc -l)
if [ "$XVFB_RUNNING" -ge 1 ]; then
    print_status 0 "Xvfb corriendo"
else
    print_status 1 "Xvfb NO está corriendo"
fi

X11VNC_RUNNING=$(docker-compose exec -T viewer ps aux | grep "x11vnc" | grep -v "grep" | wc -l)
if [ "$X11VNC_RUNNING" -ge 1 ]; then
    print_status 0 "x11vnc corriendo"
else
    print_status 1 "x11vnc NO está corriendo"
fi

# 8. Check for errors in logs
echo ""
echo "8️⃣  Verificando logs por errores..."
ERROR_COUNT=$(docker-compose logs | grep -i "error" | grep -v "ERROR" | wc -l)
if [ "$ERROR_COUNT" -eq 0 ]; then
    print_status 0 "No se encontraron errores en logs"
else
    echo -e "${YELLOW}⚠️  Se encontraron $ERROR_COUNT líneas con 'error' en logs${NC}"
    echo "Últimos errores:"
    docker-compose logs | grep -i "error" | tail -5
fi

# 9. Test API health (if enabled)
echo ""
echo "9️⃣  Testeando API (si está habilitada)..."
if docker-compose ps | grep "scraper-api" > /dev/null 2>&1; then
    sleep 5
    API_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/healthz)
    if [ "$API_HTTP_CODE" -eq 200 ]; then
        print_status 0 "API responde en http://localhost:8000/healthz"
        
        # Check if Redis is connected
        API_RESPONSE=$(curl -s http://localhost:8000/healthz)
        if echo "$API_RESPONSE" | grep -q '"redis_connected":true'; then
            print_status 0 "Redis conectado"
        else
            echo -e "${YELLOW}⚠️  Redis no conectado (esperado si no está configurado)${NC}"
        fi
        
        # Test /api/v2/run endpoint (Checkpoint Fase 2)
        echo ""
        echo "🔟 Testeando endpoint /api/v2/run (Fase 2)..."
        
        # Usar archivo temporal para capturar response y status code separados
        TEMP_RESPONSE=$(mktemp)
        HTTP_CODE=$(curl -s -w "%{http_code}" -o "$TEMP_RESPONSE" -X POST http://localhost:8000/api/v2/run \
            -H "Content-Type: application/json" \
            -H "X-API-Key: scraping-homecare-2025-secret-key" \
            -d '{"client_id":"test","year":2025,"month":"FEBRERO","prestador":null,"username":"test","password":"test"}')
        
        RESPONSE_BODY=$(cat "$TEMP_RESPONSE")
        rm "$TEMP_RESPONSE"
        
        if [ "$HTTP_CODE" -eq 202 ]; then
            if echo "$RESPONSE_BODY" | grep -q '"session_id"' && echo "$RESPONSE_BODY" | grep -q '"viewer_url"'; then
                print_status 0 "Endpoint /api/v2/run devuelve session_id y viewer_url"
                echo "   Response: $RESPONSE_BODY"
            else
                print_status 1 "Endpoint responde pero falta session_id o viewer_url"
            fi
        else
            echo -e "${RED}❌ Endpoint /api/v2/run falló (HTTP $HTTP_CODE)${NC}"
            echo "   Response: $RESPONSE_BODY"
            exit 1
        fi
    else
        echo -e "${YELLOW}⚠️  API no responde (HTTP $API_HTTP_CODE) - esperado si no está habilitada${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  API no está habilitada en docker-compose (esperado en Fase 1)${NC}"
fi

# Summary
echo ""
echo "======================================"
echo -e "${GREEN}✅ VALIDACIÓN COMPLETA${NC}"
echo "======================================"
echo ""
echo "📋 Próximos pasos:"
echo "   1. Abre http://localhost:6080/vnc.html en tu navegador"
echo "   2. Deberías ver el escritorio virtual (puede estar negro al inicio)"
echo "   3. Logs en tiempo real: make logs"
echo ""

