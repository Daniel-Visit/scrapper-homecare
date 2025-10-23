FROM debian:bookworm-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    websockify \
    python3 \
    python3-pip \
    python3-numpy \
    chromium \
    chromium-driver \
    curl \
    wget \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libgcc1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    xdg-utils \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install noVNC
RUN git clone --depth 1 https://github.com/novnc/noVNC.git /opt/novnc && \
    git clone --depth 1 https://github.com/novnc/websockify /opt/novnc/utils/websockify && \
    ln -s /opt/novnc/vnc.html /opt/novnc/index.html

# Install Playwright
RUN pip3 install playwright --break-system-packages && \
    playwright install chromium && \
    playwright install-deps chromium

# Create startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Expose noVNC port
EXPOSE 6080

# Set display environment variable
ENV DISPLAY=:99

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:6080/ || exit 1

# Start script
CMD ["/start.sh"]

