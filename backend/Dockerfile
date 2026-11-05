FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /service
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd -u 10001 -r -m appuser && mkdir -p /data && chown -R appuser:appuser /data /service
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser sample_data ./sample_data
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
