"""API mínima para gerenciar a fila de renderização.

Esta implementação é deliberadamente simples e serve apenas para validar o
pipeline e as integrações de infraestrutura. Em produção, a lógica de negócio
deve residir em outro repositório / módulo de aplicação.
"""

from fastapi import FastAPI, status


app = FastAPI(title="Spot Render API", version="0.1.0")


@app.get("/healthz", status_code=status.HTTP_200_OK)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics", tags=["observability"])
def prometheus_stub() -> str:
    """Expose métricas mínimas para integração com Prometheus."""

    return "# HELP render_api_up Flag simples\n# TYPE render_api_up gauge\nrender_api_up 1\n"
