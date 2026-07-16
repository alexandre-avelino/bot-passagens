"""Persistencia do historico de precos em SQLite.

Cada execucao registra todos os voos encontrados (nao so o top N enviado no
Telegram). O arquivo `historico.db` e commitado de volta no repositorio pelo
workflow do GitHub Actions, entao o historico persiste entre execucoes mesmo
o runner sendo descartado a cada vez.
"""

import sqlite3
from datetime import date, datetime, timezone
from typing import Iterable, Optional

from bot_passagens.models import Voo

CAMINHO_PADRAO = "historico.db"

_CRIAR_TABELA_BUSCAS = """
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

_CRIAR_TABELA_METADADOS = """
CREATE TABLE IF NOT EXISTS metadados (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
)
"""


def conectar(caminho: str = CAMINHO_PADRAO) -> sqlite3.Connection:
    conn = sqlite3.connect(caminho)
    conn.execute(_CRIAR_TABELA_BUSCAS)
    conn.execute(_CRIAR_INDICE)
    conn.execute(_CRIAR_TABELA_METADADOS)
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


def menor_preco_janela(conn: sqlite3.Connection, origem: str, destino: str, ida: date, volta: date) -> Optional[float]:
    """Menor preco ja registrado para essa janela exata (mesma rota e mesmas datas de ida/volta)."""
    linha = conn.execute(
        "SELECT MIN(preco) FROM buscas WHERE origem = ? AND destino = ? AND ida = ? AND volta = ?",
        (origem, destino, ida.isoformat(), volta.isoformat()),
    ).fetchone()
    return linha[0] if linha and linha[0] is not None else None


def ultima_leitura_janela(conn: sqlite3.Connection, origem: str, destino: str, ida: date, volta: date) -> Optional[float]:
    """Menor preco registrado na ultima execucao anterior em que essa janela foi vista."""
    linha = conn.execute(
        """
        SELECT MIN(preco) FROM buscas
        WHERE origem = ? AND destino = ? AND ida = ? AND volta = ?
          AND timestamp = (
              SELECT MAX(timestamp) FROM buscas
              WHERE origem = ? AND destino = ? AND ida = ? AND volta = ?
          )
        """,
        (
            origem, destino, ida.isoformat(), volta.isoformat(),
            origem, destino, ida.isoformat(), volta.isoformat(),
        ),
    ).fetchone()
    return linha[0] if linha and linha[0] is not None else None


def media_geral_recente(conn: sqlite3.Connection, origem: str, desde: datetime) -> Optional[float]:
    """Media dos precos de TODAS as rotas/janelas monitoradas para essa origem desde `desde`.

    Deliberadamente nao filtra por destino/ida/volta: uma janela especifica
    tem poucos registros e preco instavel (baixa disponibilidade em algumas
    datas), o que fazia "% abaixo da media" enganoso (ex.: uma passagem de
    R$1.070 aparentando ser uma pechincha so porque aquela janela especifica
    costuma custar ainda mais). A media geral reflete melhor "isso e barato
    dado tudo que venho vendo", que e o que importa na hora de comparar.
    """
    linha = conn.execute(
        "SELECT AVG(preco) FROM buscas WHERE origem = ? AND timestamp >= ?",
        (origem, desde.isoformat()),
    ).fetchone()
    return linha[0] if linha and linha[0] is not None else None


def menor_preco_geral(conn: sqlite3.Connection, origem: str) -> Optional[dict]:
    """O menor preco ja registrado entre todas as rotas/janelas monitoradas para essa origem."""
    linha = conn.execute(
        "SELECT destino, ida, volta, preco FROM buscas WHERE origem = ? ORDER BY preco ASC LIMIT 1",
        (origem,),
    ).fetchone()
    if linha is None:
        return None
    destino, ida, volta, preco = linha
    return {"origem": origem, "destino": destino, "ida": ida, "volta": volta, "preco": preco}


def obter_metadado(conn: sqlite3.Connection, chave: str) -> Optional[str]:
    linha = conn.execute("SELECT valor FROM metadados WHERE chave = ?", (chave,)).fetchone()
    return linha[0] if linha else None


def definir_metadado(conn: sqlite3.Connection, chave: str, valor: str) -> None:
    conn.execute(
        """
        INSERT INTO metadados (chave, valor) VALUES (?, ?)
        ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor
        """,
        (chave, valor),
    )
    conn.commit()
