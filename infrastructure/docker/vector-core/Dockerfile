# ATRA VectorCore — лёгкий embedding-сервис на Ollama (без torch/transformers)
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic

COPY main.py .

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python3 -c "import urllib.request;urllib.request.urlopen('http://localhost:8001/health', timeout=3)"

CMD ["python3", "main.py"]
