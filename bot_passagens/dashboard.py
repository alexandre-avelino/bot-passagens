"""Gera um dashboard estatico (HTML) com o historico de precos.

Publicado de graca via GitHub Pages (pasta docs/ na branch main). O grafico
usa Chart.js via CDN -- nenhuma dependencia nova de Python, so um arquivo
HTML com os dados embutidos como JSON.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

CAMINHO_PADRAO = "docs/index.html"
CORES = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed"]


def _menor_preco_por_dia_e_destino(conn: sqlite3.Connection) -> Dict[str, Dict[str, float]]:
    """Para cada dia (com base no timestamp da busca) e destino, o menor preco visto."""
    linhas = conn.execute(
        """
        SELECT date(timestamp) AS dia, destino, MIN(preco) AS menor_preco
        FROM buscas
        GROUP BY dia, destino
        ORDER BY dia
        """
    ).fetchall()

    por_destino: Dict[str, Dict[str, float]] = {}
    for dia, destino, preco in linhas:
        por_destino.setdefault(destino, {})[dia] = preco
    return por_destino


def _montar_html(origem: str, por_destino: Dict[str, Dict[str, float]], total_registros: int) -> str:
    todos_os_dias: List[str] = sorted({dia for dias in por_destino.values() for dia in dias})

    datasets = []
    for i, (destino, dias) in enumerate(sorted(por_destino.items())):
        datasets.append(
            {
                "label": f"{origem} → {destino}",
                "data": [dias.get(dia) for dia in todos_os_dias],
                "borderColor": CORES[i % len(CORES)],
                "spanGaps": True,
                "tension": 0.2,
            }
        )

    atualizado_em = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    return f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monitor de passagens — {origem}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 16px; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 24px; }}
  .grafico-container {{ position: relative; width: 100%; height: 420px; }}
</style>
</head>
<body>
  <h1>✈️ Monitor de passagens — {origem}</h1>
  <p class="meta">{total_registros} buscas registradas · atualizado em {atualizado_em}</p>
  <div class="grafico-container">
    <canvas id="grafico"></canvas>
  </div>
  <script>
    new Chart(document.getElementById('grafico'), {{
      type: 'line',
      data: {{
        labels: {json.dumps(todos_os_dias)},
        datasets: {json.dumps(datasets)}
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        scales: {{ y: {{ title: {{ display: true, text: 'Menor preco do dia (R$)' }} }} }}
      }}
    }});
  </script>
</body>
</html>
"""


def gerar_dashboard(conn: sqlite3.Connection, origem: str, caminho_saida: str = CAMINHO_PADRAO) -> None:
    por_destino = _menor_preco_por_dia_e_destino(conn)
    total_registros = conn.execute("SELECT COUNT(*) FROM buscas").fetchone()[0]
    html = _montar_html(origem, por_destino, total_registros)

    caminho = Path(caminho_saida)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(html, encoding="utf-8")
