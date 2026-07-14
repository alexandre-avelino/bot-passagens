from datetime import date, datetime, timezone

from bot_passagens import historico
from bot_passagens.models import Voo


def _voo(preco: float, destino: str = "GRU", companhia: str = "Gol") -> Voo:
    return Voo(
        origem="CGB",
        destino=destino,
        ida=date(2026, 10, 3),
        volta=date(2026, 10, 8),
        companhia=companhia,
        preco=preco,
        escalas=0,
        partida="08:00",
        chegada="11:00",
        link="https://exemplo",
    )


def test_registrar_e_ler_voos(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        historico.registrar_voos(conn, [_voo(603.0), _voo(637.0)])
        total = conn.execute("SELECT COUNT(*) FROM buscas").fetchone()[0]
        assert total == 2
    finally:
        conn.close()


def test_registrar_lista_vazia_nao_quebra(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        historico.registrar_voos(conn, [])
        total = conn.execute("SELECT COUNT(*) FROM buscas").fetchone()[0]
        assert total == 0
    finally:
        conn.close()


def test_menor_preco_historico_considera_apenas_a_rota_pedida(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        historico.registrar_voos(conn, [_voo(900.0, destino="GRU"), _voo(500.0, destino="CGH")])
        historico.registrar_voos(conn, [_voo(700.0, destino="GRU")])

        assert historico.menor_preco_historico(conn, "CGB", "GRU") == 700.0
        assert historico.menor_preco_historico(conn, "CGB", "CGH") == 500.0
    finally:
        conn.close()


def test_menor_preco_historico_sem_dados_retorna_none(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        assert historico.menor_preco_historico(conn, "CGB", "GRU") is None
    finally:
        conn.close()


def test_conectar_cria_tabela_de_forma_idempotente(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn1 = historico.conectar(caminho)
    historico.registrar_voos(conn1, [_voo(603.0)])
    conn1.close()

    # reabrir o mesmo arquivo nao deve apagar os dados nem falhar ao recriar a tabela
    conn2 = historico.conectar(caminho)
    try:
        total = conn2.execute("SELECT COUNT(*) FROM buscas").fetchone()[0]
        assert total == 1
    finally:
        conn2.close()


def test_timestamp_customizado_e_gravado(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        momento = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
        historico.registrar_voos(conn, [_voo(603.0)], timestamp=momento)
        salvo = conn.execute("SELECT timestamp FROM buscas").fetchone()[0]
        assert salvo == momento.isoformat()
    finally:
        conn.close()
