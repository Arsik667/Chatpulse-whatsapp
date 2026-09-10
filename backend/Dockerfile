FROM python:3.14-slim

# без .pyc-файлов (контейнер read-only) и с логами без буферизации
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY analyzer_core ./analyzer_core
COPY app ./app

# сервер не должен работать от root
RUN useradd --create-home --uid 1000 chatpulse
USER chatpulse

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
