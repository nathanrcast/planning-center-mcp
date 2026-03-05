FROM python:3.12.9-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir . && \
    adduser --disabled-password --no-create-home appuser

COPY src/ src/

USER appuser

EXPOSE 8080

CMD ["python", "-m", "src.server"]
