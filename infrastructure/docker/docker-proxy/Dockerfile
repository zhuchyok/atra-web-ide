FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn docker pydantic

COPY main.py .

EXPOSE 2376

CMD ["python", "main.py"]
