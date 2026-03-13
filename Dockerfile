FROM python:3.12.9-slim

WORKDIR /app

COPY pyproject.toml .
COPY planning_center_mcp/__init__.py planning_center_mcp/__init__.py
RUN pip install --no-cache-dir . && \
    adduser --disabled-password --no-create-home appuser

COPY planning_center_mcp/ planning_center_mcp/

USER appuser

EXPOSE 8080

CMD ["python", "-m", "planning_center_mcp.server"]
