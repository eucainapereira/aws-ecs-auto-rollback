import os
import socket
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import List, Dict, Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

# Configuração de logs estruturados
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("clientes-portal")

# ==============================================================================
# Configurações de Ambiente / Flags de Simulação de Rollback
# ==============================================================================
APP_VERSION = os.getenv("APP_VERSION", "v1.0")
SIMULATE_FAILURE_RAW = os.getenv("SIMULATE_FAILURE", "false")
SIMULATE_FAILURE = SIMULATE_FAILURE_RAW.strip().lower() in ("true", "1", "yes")

DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "clientes-resilience-lab")
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
CONTAINER_ID = socket.gethostname()

SEED_CLIENTES: List[Dict[str, str]] = [
    {
        "id": "CLI-001",
        "nome": "TechNova Cloud Solutions",
        "email": "arquitetura@technova.com.br",
        "segmento": "SaaS Enterprise",
        "status": "Ativo",
        "criado_em": "2025-01-15 09:30 UTC",
    },
    {
        "id": "CLI-002",
        "nome": "FinBank Pagamentos Digitais S.A.",
        "email": "sre-team@finbank.com.br",
        "segmento": "Fintech / Banking",
        "status": "Ativo",
        "criado_em": "2025-02-03 14:15 UTC",
    },
    {
        "id": "CLI-003",
        "nome": "LogiBrasil Malha Logística",
        "email": "devops@logibrasil.com.br",
        "segmento": "Supply Chain",
        "status": "Ativo",
        "criado_em": "2025-02-20 11:00 UTC",
    },
]


def get_dynamodb_table():
    """Retorna a referência da tabela DynamoDB."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    return dynamodb.Table(DYNAMODB_TABLE)


def ensure_seed_data() -> tuple[List[Dict[str, Any]], str]:
    """
    Busca clientes da tabela DynamoDB.
    Se a tabela estiver vazia, realiza o seed automático de 3 clientes fictícios.
    Retorna (lista_de_clientes, status_conexao).
    """
    try:
        table = get_dynamodb_table()
        response = table.scan()
        items = response.get("Items", [])

        if not items:
            logger.info("Tabela '%s' vazia. Executando seed automático de 3 clientes...", DYNAMODB_TABLE)
            with table.batch_writer() as batch:
                for cliente in SEED_CLIENTES:
                    batch.put_item(Item=cliente)
            items = list(SEED_CLIENTES)
            db_status = f"Conectado ({DYNAMODB_TABLE}) • Seed automático aplicado"
        else:
            db_status = f"Conectado ({DYNAMODB_TABLE})"

        items_sorted = sorted(items, key=lambda x: x.get("id", ""))
        return items_sorted, db_status

    except (BotoCoreError, ClientError) as exc:
        logger.warning("Aviso ao acessar DynamoDB (%s): %s", DYNAMODB_TABLE, exc)
        return SEED_CLIENTES, f"Modo Demonstração / Fallback ({type(exc).__name__})"
    except Exception as exc:
        logger.error("Erro inesperado ao consultar DynamoDB: %s", exc)
        return SEED_CLIENTES, f"Erro DynamoDB ({type(exc).__name__})"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Iniciando Portal de Clientes | version=%s | simulate_failure=%s | table=%s | container=%s",
        APP_VERSION,
        SIMULATE_FAILURE,
        DYNAMODB_TABLE,
        CONTAINER_ID,
    )
    if not SIMULATE_FAILURE:
        ensure_seed_data()
    else:
        logger.error(
            "ALERTA DE SIMULAÇÃO: SIMULATE_FAILURE=true ativo! A rota /health retornará HTTP 500 para acionar o ECS Deployment Circuit Breaker."
        )
    yield


app = FastAPI(
    title="Portal de Clientes - Resilience Lab",
    description="Aplicação de demonstração para Zero-Downtime Deployment e Auto-Rollback no Amazon ECS Fargate",
    version=APP_VERSION,
    lifespan=lifespan,
)


# ==============================================================================
# Rota Crítica: Health Check para ALB e ECS Deployment Circuit Breaker
# ==============================================================================
@app.get("/health")
async def health_check():
    """
    Endpoint monitorado pelo Application Load Balancer (ALB) e pelo ECS.
    - SIMULATE_FAILURE=false -> HTTP 200 OK (Deploy concluído com sucesso)
    - SIMULATE_FAILURE=true  -> HTTP 500 Internal Server Error (Aciona Circuit Breaker e Rollback)
    """
    if SIMULATE_FAILURE:
        logger.error(
            "Health check REPROVADO em %s (version=%s, SIMULATE_FAILURE=true)",
            CONTAINER_ID,
            APP_VERSION,
        )
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": "Simulated critical bug",
                "version": APP_VERSION,
                "container_id": CONTAINER_ID,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "version": APP_VERSION,
            "container_id": CONTAINER_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


# ==============================================================================
# Rotas Auxiliares para Interação com o DynamoDB (Seed e Cadastro)
# ==============================================================================
@app.post("/seed")
async def trigger_seed():
    """Popula ou restaura os 3 clientes padrões na tabela DynamoDB."""
    try:
        table = get_dynamodb_table()
        with table.batch_writer() as batch:
            for cliente in SEED_CLIENTES:
                batch.put_item(Item=cliente)
        logger.info("Seed manual executado com sucesso na tabela %s.", DYNAMODB_TABLE)
    except Exception as exc:
        logger.error("Falha ao executar seed manual: %s", exc)
    return RedirectResponse(url="/", status_code=303)


@app.post("/clientes")
async def adicionar_cliente(
    cliente_id: str = Form(...),
    nome: str = Form(...),
    email: str = Form(...),
    segmento: str = Form("Enterprise"),
):
    """Insere um novo cliente na tabela DynamoDB em tempo real."""
    try:
        table = get_dynamodb_table()
        table.put_item(
            Item={
                "id": cliente_id.strip().upper(),
                "nome": nome.strip(),
                "email": email.strip(),
                "segmento": segmento.strip(),
                "status": "Ativo",
                "criado_em": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            }
        )
        logger.info("Novo cliente %s adicionado com sucesso.", cliente_id)
    except Exception as exc:
        logger.error("Erro ao inserir cliente no DynamoDB: %s", exc)
    return RedirectResponse(url="/", status_code=303)


# ==============================================================================
# Rota Principal: Interface Web do Portal de Clientes
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    clientes, db_status = ensure_seed_data()

    is_buggy = SIMULATE_FAILURE or "v2" in APP_VERSION.lower() or "bug" in APP_VERSION.lower()
    if is_buggy:
        badge_text = f"{APP_VERSION} - CANARY / BUG"
        badge_bg = "linear-gradient(135deg, #dc2626, #ea580c)"
        badge_border = "#f87171"
        health_badge = "HTTP 500 (UNHEALTHY - ROLLBACK TRIGGERED)"
        health_color = "#ef4444"
    else:
        badge_text = f"{APP_VERSION} - ESTÁVEL"
        badge_bg = "linear-gradient(135deg, #2563eb, #1d4ed8)"
        badge_border = "#60a5fa"
        health_badge = "HTTP 200 OK (HEALTHY)"
        health_color = "#10b981"

    rows_html = ""
    for c in clientes:
        rows_html += f"""
        <tr>
            <td><span class="id-pill">{c.get("id", "-")}</span></td>
            <td class="font-semibold">{c.get("nome", "-")}</td>
            <td>{c.get("email", "-")}</td>
            <td><span class="segment-tag">{c.get("segmento", "Enterprise")}</span></td>
            <td><span class="status-dot"></span>{c.get("status", "Ativo")}</td>
            <td class="text-muted">{c.get("criado_em", "-")}</td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Portal de Clientes - Resilience Lab</title>
    <style>
        :root {{
            --bg-dark: #0f172a;
            --card-bg: #1e293b;
            --border-color: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem 1rem;
        }}
        .container {{
            max-width: 1080px;
            margin: 0 auto;
        }}
        .header {{
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 1.25rem;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 1.75rem 2rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
        }}
        .title-group h1 {{
            font-size: 1.65rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin-bottom: 0.35rem;
        }}
        .title-group p {{
            color: var(--text-secondary);
            font-size: 0.95rem;
        }}
        .version-badge {{
            background: {badge_bg};
            border: 2px solid {badge_border};
            color: #ffffff;
            padding: 0.65rem 1.35rem;
            border-radius: 9999px;
            font-weight: 800;
            font-size: 1rem;
            letter-spacing: 0.04em;
            box-shadow: 0 4px 15px rgba(37, 99, 235, 0.35);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}
        .metric-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.15rem 1.35rem;
        }}
        .metric-label {{
            color: var(--text-secondary);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 0.4rem;
        }}
        .metric-value {{
            font-size: 0.98rem;
            font-weight: 700;
            word-break: break-all;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 1.5rem 2rem;
            margin-bottom: 1.5rem;
        }}
        .card-header {{
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1.25rem;
        }}
        .card-header h2 {{
            font-size: 1.2rem;
            font-weight: 700;
        }}
        .btn {{
            background: #334155;
            color: #f8fafc;
            border: 1px solid #475569;
            padding: 0.55rem 1rem;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
            text-decoration: none;
        }}
        .btn:hover {{
            background: #475569;
        }}
        .btn-primary {{
            background: #2563eb;
            border-color: #3b82f6;
        }}
        .btn-primary:hover {{
            background: #1d4ed8;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}
        th {{
            color: var(--text-secondary);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 0.85rem 0.75rem;
            border-bottom: 1px solid var(--border-color);
        }}
        td {{
            padding: 1rem 0.75rem;
            border-bottom: 1px solid rgba(51, 65, 85, 0.6);
            font-size: 0.92rem;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        .id-pill {{
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.3);
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            font-family: monospace;
            font-weight: 700;
            font-size: 0.82rem;
        }}
        .segment-tag {{
            background: rgba(148, 163, 184, 0.12);
            color: #cbd5e1;
            padding: 0.25rem 0.65rem;
            border-radius: 6px;
            font-size: 0.8rem;
        }}
        .status-dot {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            margin-right: 6px;
        }}
        .font-semibold {{
            font-weight: 600;
        }}
        .text-muted {{
            color: var(--text-secondary);
            font-size: 0.82rem;
        }}
        .form-row {{
            display: grid;
            grid-template-columns: 1fr 2fr 2fr 1.5fr auto;
            gap: 0.75rem;
            margin-top: 1rem;
        }}
        .form-row input {{
            background: #0f172a;
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 0.6rem 0.8rem;
            border-radius: 8px;
            font-size: 0.88rem;
        }}
        @media (max-width: 768px) {{
            .form-row {{
                grid-template-columns: 1fr;
            }}
            table {{
                display: block;
                overflow-x: auto;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div class="title-group">
                <h1>Portal de Clientes - Resilience Lab</h1>
                <p>AWS ECS Fargate • Application Load Balancer • Deployment Circuit Breaker • DynamoDB</p>
            </div>
            <div class="version-badge">
                <span>●</span>
                <span>{badge_text}</span>
            </div>
        </header>

        <section class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Status do Health Check (/health)</div>
                <div class="metric-value" style="color: {health_color};">{health_badge}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Amazon DynamoDB</div>
                <div class="metric-value">{db_status}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Container / Task Host</div>
                <div class="metric-value" style="font-family: monospace;">{CONTAINER_ID}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Proteção de Deploy</div>
                <div class="metric-value">ECS Circuit Breaker (Ativo)</div>
            </div>
        </section>

        <main class="card">
            <div class="card-header">
                <h2>Clientes Ativos no DynamoDB ({len(clientes)})</h2>
                <div style="display: flex; gap: 0.5rem;">
                    <form action="/seed" method="post" style="display: inline;">
                        <button type="submit" class="btn">Restaurar Seed (3 Clientes)</button>
                    </form>
                    <a href="/health" class="btn" target="_blank">Inspecionar JSON /health</a>
                </div>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Cliente / Razão Social</th>
                        <th>E-mail de Contato</th>
                        <th>Segmento</th>
                        <th>Status</th>
                        <th>Criado em</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </main>

        <section class="card">
            <div class="card-header" style="margin-bottom: 0.5rem;">
                <h2>Adicionar Cliente em Tempo Real (DynamoDB PutItem)</h2>
            </div>
            <form action="/clientes" method="post" class="form-row">
                <input type="text" name="cliente_id" placeholder="ID (ex: CLI-004)" required />
                <input type="text" name="nome" placeholder="Nome da Empresa" required />
                <input type="email" name="email" placeholder="contato@empresa.com.br" required />
                <input type="text" name="segmento" placeholder="Segmento (ex: Retail)" value="Cloud Native" />
                <button type="submit" class="btn btn-primary">+ Cadastrar</button>
            </form>
        </section>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html_content, status_code=200)
