FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt \
    /app/requirements.txt

RUN pip install --upgrade pip \
    && pip install \
        -r /app/requirements.txt

RUN addgroup --system signalai \
    && adduser \
        --system \
        --ingroup signalai \
        --home /home/signalai \
        signalai

COPY --chown=signalai:signalai \
    backend /app

USER signalai

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
