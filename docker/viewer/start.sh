#!/bin/bash
set -e

echo "🚀 Starting viewer container..."

# Start Xvfb (virtual display)
echo "📺 Starting Xvfb on display :99..."
Xvfb :99 -screen 0 1280x720x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Wait for X server to start
sleep 2

# Start x11vnc (VNC server)
echo "🔌 Starting x11vnc on port 5900..."
x11vnc -display :99 -forever -shared -rfbport 5900 -nopw -xkb &
X11VNC_PID=$!

# Wait for VNC server to start
sleep 2

# Start noVNC (web viewer)
echo "🌐 Starting noVNC on port 6080..."
/opt/novnc/utils/novnc_proxy --vnc localhost:5900 --listen 6080 &
NOVNC_PID=$!

echo "✅ All services started!"
echo "   - Xvfb: display :99 (PID: $XVFB_PID)"
echo "   - x11vnc: port 5900 (PID: $X11VNC_PID)"
echo "   - noVNC: http://localhost:6080 (PID: $NOVNC_PID)"

# Keep container alive and monitor processes
while kill -0 $XVFB_PID 2>/dev/null && \
      kill -0 $X11VNC_PID 2>/dev/null && \
      kill -0 $NOVNC_PID 2>/dev/null; do
    sleep 5
done

echo "❌ One or more services died, exiting..."
exit 1

