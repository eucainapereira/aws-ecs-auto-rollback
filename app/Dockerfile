FROM python:3.12-slim

LABEL maintainer="Cainã Pereira <DevOps/SRE Portfolio>"
LABEL description="Portal de Clientes - AWS ECS Zero-Downtime & Auto-Rollback Lab"

# Argumentos de build injetados pelo GitHub Actions no momento do deploy
ARG APP_VERSION="v1.0"
ARG SIMULATE_FAILURE="false"

# Variáveis de ambiente em runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION} \
    SIMULATE_FAILURE=${SIMULATE_FAILURE} \
    DYNAMODB_TABLE="clientes-resilience-lab" \
    AWS_REGION="us-east-1" \
    PORT=8000

WORKDIR /app

# Instala dependências primeiro para otimizar cache de camadas Docker
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY main.py .

# Boas práticas de segurança: executa o container com usuário não-root
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Healthcheck nativo do container (além do Health Check do ALB Target Group)
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=2 \
    CMD python -c "import urllib.request, sys; r = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3); sys.exit(0 if r.getcode() == 200 else 1)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
