# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    AICOMIC_CONFIG_DIR=/config \
    AICOMIC_ASSETS_DIR=/config/assets \
    AICOMIC_BIND_HOST=0.0.0.0 \
    AICOMIC_BIND_PORT=7860

# opencv-python-headless still needs a couple of shared libs at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libjpeg62-turbo \
        libpng16-16 \
        libwebp7 \
        tini \
        gosu \
    && rm -rf /var/lib/apt/lists/*

# Create an 'aicomic' user matching Unraid's default nobody:users (99:100) so
# the /config bind-mount on /mnt/user/appdata ends up with correct ownership.
# The `users` group (GID 100) typically already ships in Debian base images,
# so only create it if it's missing. Same for the user.
RUN (getent group users >/dev/null || groupadd -g 100 users) \
    && (getent passwd aicomic >/dev/null || useradd -u 99 -g 100 -M -s /usr/sbin/nologin aicomic)

WORKDIR /app

# Deps first for better layer caching.
COPY pyproject.toml README.md /app/
RUN pip install --upgrade pip \
    && pip install \
        "gradio>=5.0" \
        "pillow>=10.0" \
        "pydantic>=2.0" \
        "sqlalchemy>=2.0" \
        "websocket-client>=1.7" \
        "requests>=2.31" \
        "opencv-python-headless>=4.9" \
        "numpy>=1.26" \
        "pyyaml>=6.0"

# App source.
COPY app.py /app/
COPY config /app/config
COPY comfy /app/comfy
COPY generators /app/generators
COPY library /app/library
COPY bubble /app/bubble
COPY ui /app/ui
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && mkdir -p /config/assets \
    && chown -R aicomic:users /config /app

EXPOSE 7860
VOLUME ["/config"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/', timeout=3).read()" || exit 1

# Run entrypoint as root so it can apply PUID/PGID, then drop to aicomic.
ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
CMD ["python", "app.py"]
