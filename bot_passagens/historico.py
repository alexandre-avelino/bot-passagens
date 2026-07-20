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


def media_precos_recentes(
    conn: sqlite3.Connection, origem: str, destino: str, ida: date, volta: date, desde: datetime
) -> Optional[float]:
    """Media dos precos registrados para essa janela especifica (mesma rota e mesmas
    datas de ida/volta) desde `desde` (ex.: ultimos 30 dias).

    Deliberadamente especifica por janela, nao geral: uma media que mistura
    rotas muito diferentes (ex.: uma que costuma ser barata com outra que as
    vezes dispara de preco) produz um numero que nao ajuda a dizer se ESSA
    janela em particular esta boa ou nao.
    """
    linha = conn.execute(
        """
        SELECT AVG(preco) FROM buscas
        WHERE origem = ? AND destino = ? AND ida = ? AND volta = ? AND timestamp >= ?
        """,
        (origem, destino, ida.isoformat(), volta.isoformat(), desde.isoformat()),
    ).fetchone()
    return linha[0] if linha and linha[0] is not None else None


def menor_preco_geral(conn: sqlite3.Connection, origem: str) -> Optional[dict]:
    """O menor preco ja registrado entre todas as rotas/janelas monitoradas para essa origem."""
    linha = conn.execute(
        "SELECT destino, ida, volta, preco, timestamp FROM buscas WHERE origem = ? ORDER BY preco ASC LIMIT 1",
        (origem,),
    ).fetchone()
    if linha is None:
        return None
    destino, ida, volta, preco, timestamp = linha
    return {
        "origem": origem,
        "destino": destino,
        "ida": ida,
        "volta": volta,
        "preco": preco,
        "encontrado_em": timestamp,
    }


def janelas_mais_baratas_recentes(conn: sqlite3.Connection, origem: str, quantidade: int) -> list:
    """As `quantidade` janelas (destino, ida, volta) mais baratas na ultima leva de buscas
    registrada para essa origem -- usado pela checagem rapida pra saber o que vigiar sem
    precisar varrer todas as janelas monitoradas de novo.
    """
    ultimo_timestamp = conn.execute(
        "SELECT MAX(timestamp) FROM buscas WHERE origem = ?", (origem,)
    ).fetchone()[0]
    if ultimo_timestamp is None:
        return []

    linhas = conn.execute(
        """
        SELECT destino, ida, volta, MIN(preco) AS preco
        FROM buscas
        WHERE origem = ? AND timestamp = ?
        GROUP BY destino, ida, volta
        ORDER BY preco ASC
        LIMIT ?
        """,
        (origem, ultimo_timestamp, quantidade),
    ).fetchall()
    return [
        {"destino": destino, "ida": date.fromisoformat(ida), "volta": date.fromisoformat(volta)}
        for destino, ida, volta, _preco in linhas
    ]


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
