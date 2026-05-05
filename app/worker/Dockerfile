FROM python:3.11-slim

WORKDIR /app

COPY app/worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/worker .
COPY config ./config

CMD ["python", "daily_history.py"]
