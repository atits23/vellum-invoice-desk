FROM node:22-bookworm-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000 DATA_DIR=/data NODE_ENV=production PYTHON_BIN=/opt/venv/bin/python
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv poppler-utils tesseract-ocr tesseract-ocr-hin fonts-dejavu-core ca-certificates tini && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt package.json package-lock.json ./
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt && npm ci --omit=dev --no-fund
COPY app ./app
COPY web ./web
COPY static ./static
COPY scripts ./scripts
COPY tests ./tests
COPY reports ./reports
RUN /opt/venv/bin/python scripts/generate_samples.py && useradd --uid 10001 --create-home vellum && mkdir /data && chown vellum:vellum /data
USER vellum
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD node -e "fetch('http://127.0.0.1:'+process.env.PORT+'/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["node", "web/server.mjs"]
