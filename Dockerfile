# Docker image of the Spectrum Toolkit web service (spectrum_toolkit.api).
#
# Build:  docker build -t spectrum-toolkit .
# Run:    docker run -d --name stk -p 127.0.0.1:8100:8000 \
#             -v ~/stk-secrets/api_key.txt:/run/secrets/stk_api_key:ro --restart unless-stopped spectrum-toolkit
#         (the key file is made once on the VM: see docs/website.md)
# Check:  curl http://127.0.0.1:8000/health
#
# Two stages: the first installs the exact package versions from uv.lock into
# /app/.venv; the second copies only that folder into a clean image, so the
# final image has no build tools in it.

# ---------------------------------------------------------------- 1. build
FROM python:3.13-slim AS build
# uv installs the locked versions; pinned so builds are repeatable.
RUN pip install --no-cache-dir uv==0.11.32
WORKDIR /app
# Copy the dependency list first: Docker reuses this layer while it is unchanged,
# so editing the code does not reinstall numpy, scipy, matplotlib, ...
COPY pyproject.toml uv.lock README.md ./
# --frozen: use uv.lock as is; --no-dev: no pytest/jupyter; the api and plot extras
# add the web service and figures. --no-install-project: the code comes next.
RUN uv sync --frozen --no-dev --extra api --extra plot --no-install-project
COPY src ./src
# --no-editable: copy the package into the environment, so src/ is not needed later.
RUN uv sync --frozen --no-dev --extra api --extra plot --no-editable

# ---------------------------------------------------------------- 2. run
FROM python:3.13-slim
# Liberation fonts have the same letter widths as Arial / Helvetica / Times, so
# figures with the "matlab" style (Arial) look the same as on Windows or a Mac.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
# Run as an ordinary user, not root: a fault in the service cannot change the image.
RUN useradd --create-home --uid 1000 stk
COPY --from=build --chown=stk:stk /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    # print log lines immediately, write no .pyc files
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    # matplotlib keeps its font list here (the user's home is writable)
    MPLCONFIGDIR=/home/stk/.matplotlib \
    # settings of the service; change with docker run -e NAME=value
    # 95 MB: just under Cloudflare's 100 MB limit for one request (free plan)
    STK_MAX_UPLOAD_MB=95 \
    STK_ALLOWED_ORIGINS=https://cheminations.com,https://www.cheminations.com \
    # the secret key shared with the Worker: given as a file (docker run -v ...:/run/secrets/stk_api_key:ro),
    # and required, so the container never starts without it
    STK_API_KEY_FILE=/run/secrets/stk_api_key \
    STK_REQUIRE_KEY=1
USER stk
WORKDIR /home/stk
# Build matplotlib's font list now, so the first figure request is not slow.
RUN python -c "import matplotlib.font_manager"
EXPOSE 8000
# Docker marks the container unhealthy if /health stops answering.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
# 2 worker processes answer requests side by side; --proxy-headers because the
# website's web server (nginx/Caddy) passes requests on to this container.
CMD ["uvicorn", "spectrum_toolkit.api:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
