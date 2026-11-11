FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY data_pipeline ./data_pipeline
COPY tests ./tests

CMD ["python", "-m", "data_pipeline.cli", "run-all"]
