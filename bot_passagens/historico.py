"""Persistencia do historico de precos em SQLite.

Cada execucao registra todos os voos encontrados (nao so o top N enviado no
Telegram). O arquivo `historico.db` e commitado de volta no repositorio pelo
workflow do GitHub Actions, entao o historico persiste entre execucoes mesmo
o runner sendo descartado a cada vez.
"""

import sqlite3
from datetime import datetime, timezone
from typing import Iterable, Optional

from bot_passagens.models import Voo

CAMINHO_PADRAO = "historico.db"

_CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS buscas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    origem TEXT NOT NULL,
    destino TEXT NOT NULL,
    ida TEXT NOT NULL,
    volta TEXT NOT NULL,
    companhia TEXT NOT NULL,
    preco REAL NOT NULL,
    escalas INTEGER NOT NULL,
    partida TEXT NOT NULL,
    chegada TEXT NOT NULL,
    link TEXT NOT NULL
)
"""

_CRIAR_INDICE = """
CREATE INDEX IF NOT EXISTS idx_buscas_rota_datas ON buscas (origem, destino, ida, volta)
"""


def conectar(caminho: str = CAMINHO_PADRAO) -> sqlite3.Connection:
    conn = sqlite3.connect(caminho)
    conn.execute(_CRIAR_TABELA)
    conn.execute(_CRIAR_INDICE)
    conn.commit()
    return conn


def registrar_voos(conn: sqlite3.Connection, voos: Iterable[Voo], timestamp: Optional[datetime] = None) -> None:
    momento = (timestamp or datetime.now(timezone.utc)).isoformat()
    linhas = [
        (
            momento,
            voo.origem,
            voo.destino,
            voo.ida.isoformat(),
            voo.volta.isoformat(),
            voo.companhia,
            voo.preco,
            voo.escalas,
            voo.partida,
            voo.chegada,
            voo.link,
        )
        for voo in voos
    ]
    if not linhas:
        return
    conn.executemany(
        """
        INSERT INTO buscas
            (timestamp, origem, destino, ida, volta, companhia, preco, escalas, partida, chegada, link)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        linhas,
    )
    conn.commit()


def menor_preco_historico(conn: sqlite3.Connection, origem: str, destino: str) -> Optional[float]:
    """Menor preco ja registrado para a rota (origem -> destino), em qualquer execucao anterior."""
    linha = conn.execute(
        "SELECT MIN(preco) FROM buscas WHERE origem = ? AND destino = ?",
        (origem, destino),
    ).fetchone()
    return linha[0] if linha and linha[0] is not None else None
