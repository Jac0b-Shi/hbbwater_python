# FastAPI backend image with DM8 client placeholders for Ubuntu deployment.
# Before building, place the Linux DM8 runtime/client files under backend/vendor/dm/.
# Python source packages are read from backend/达梦 Python 接口源码-20260401/python by default.

FROM python:3.12-slim

WORKDIR /app

ENV DM_HOME=/opt/dmdbms
ENV DM_PYTHON_SOURCE_ROOT=/opt/dm-python-src
ENV LD_LIBRARY_PATH=/opt/dmdbms/bin:/opt/dmdbms/drivers/dpi

RUN sed -i \
    -e 's|http://deb.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g' \
    -e 's|http://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g' \
    /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y \
    gcc \
    make \
    libaio1t64 \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY vendor/dm/ ${DM_HOME}/
RUN if [ -f "${DM_HOME}/bin/libdmgmssl.so" ] && [ ! -e "${DM_HOME}/bin/libgmssl.so" ]; then \
        ln -s libdmgmssl.so "${DM_HOME}/bin/libgmssl.so"; \
    fi
COPY ["达梦 Python 接口源码-20260401/python/", "/opt/dm-python-src/"]
COPY scripts/install_dm_drivers.sh /tmp/install_dm_drivers.sh
RUN chmod +x /tmp/install_dm_drivers.sh \
    && DM_HOME="${DM_HOME}" DM_PYTHON_SOURCE_ROOT="${DM_PYTHON_SOURCE_ROOT}" /tmp/install_dm_drivers.sh \
    && rm /tmp/install_dm_drivers.sh

COPY app/ ./app/
RUN mkdir -p /app/runtime

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
