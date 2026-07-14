from datetime import date, datetime, timezone

from bot_passagens import dashboard, historico
from bot_passagens.models import Voo


def _voo(preco: float, destino: str = "GRU") -> Voo:
    return Voo(
        origem="CGB",
        destino=destino,
        ida=date(2026, 10, 3),
        volta=date(2026, 10, 8),
        companhia="Gol",
        preco=preco,
        escalas=0,
        partida="08:00",
        chegada="11:00",
        link="https://exemplo",
    )


def test_menor_preco_por_dia_e_destino_agrupa_corretamente(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        dia1 = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
        dia2 = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
        historico.registrar_voos(conn, [_voo(900.0, "GRU"), _voo(500.0, "CGH")], timestamp=dia1)
        historico.registrar_voos(conn, [_voo(700.0, "GRU"), _voo(600.0, "GRU")], timestamp=dia2)

        resultado = dashboard._menor_preco_por_dia_e_destino(conn)

        assert resultado["GRU"]["2026-07-10"] == 900.0
        assert resultado["GRU"]["2026-07-11"] == 600.0
        assert resultado["CGH"]["2026-07-10"] == 500.0
        assert "2026-07-11" not in resultado["CGH"]
    finally:
        conn.close()


def test_menor_preco_por_dia_e_destino_sem_dados(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        assert dashboard._menor_preco_por_dia_e_destino(conn) == {}
    finally:
        conn.close()


def test_gerar_dashboard_cria_arquivo_com_dados_esperados(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        historico.registrar_voos(conn, [_voo(628.0, "GRU")])
        caminho_saida = tmp_path / "docs" / "index.html"
        dashboard.gerar_dashboard(conn, origem="CGB", caminho_saida=str(caminho_saida))

        assert caminho_saida.exists()
        conteudo = caminho_saida.read_text(encoding="utf-8")
        assert "CGB" in conteudo
        assert "628.0" in conteudo
        assert "chart.js" in conteudo.lower()
    finally:
        conn.close()


def test_gerar_dashboard_cria_pasta_pai_se_nao_existir(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        caminho_saida = tmp_path / "pasta_nova" / "sub" / "index.html"
        dashboard.gerar_dashboard(conn, origem="CGB", caminho_saida=str(caminho_saida))
        assert caminho_saida.exists()
    finally:
        conn.close()
