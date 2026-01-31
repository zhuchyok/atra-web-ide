# Сборка из каталога knowledge_os: docker build -f dashboard/Dockerfile .
# Тогда в образ попадают app (evaluator, singularity_9_ab_tester) и дашборд — метрики Singularity 9.0 загружаются.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Модули корпорации (evaluator, singularity_9_ab_tester и др.) — в /app, streamlit_app.py их подхватит
COPY app/*.py ./
COPY dashboard/app.py ./streamlit_app.py

EXPOSE 8501

CMD ["python", "-m", "streamlit", "run", "streamlit_app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
