from datetime import date, datetime, timezone

from bot_passagens import historico
from bot_passagens.models import Voo


def _voo(
    preco: float,
    destino: str = "GRU",
    companhia: str = "Gol",
    ida: date = date(2026, 10, 3),
    volta: date = date(2026, 10, 8),
) -> Voo:
    return Voo(
        origem="CGB",
        destino=destino,
        ida=ida,
        volta=volta,
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


def test_menor_preco_janela_e_especifico_por_datas(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        historico.registrar_voos(conn, [_voo(600.0, ida=date(2026, 10, 3), volta=date(2026, 10, 8))])
        historico.registrar_voos(conn, [_voo(500.0, ida=date(2026, 10, 5), volta=date(2026, 10, 10))])

        assert historico.menor_preco_janela(conn, "CGB", "GRU", date(2026, 10, 3), date(2026, 10, 8)) == 600.0
        assert historico.menor_preco_janela(conn, "CGB", "GRU", date(2026, 10, 5), date(2026, 10, 10)) == 500.0
        assert historico.menor_preco_janela(conn, "CGB", "GRU", date(2026, 10, 1), date(2026, 10, 6)) is None
    finally:
        conn.close()


def test_ultima_leitura_janela_pega_a_execucao_mais_recente(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        t1 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)
        historico.registrar_voos(conn, [_voo(1000.0)], timestamp=t1)
        historico.registrar_voos(conn, [_voo(800.0)], timestamp=t2)

        assert historico.ultima_leitura_janela(conn, "CGB", "GRU", date(2026, 10, 3), date(2026, 10, 8)) == 800.0
    finally:
        conn.close()


def test_ultima_leitura_janela_sem_historico_retorna_none(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        assert historico.ultima_leitura_janela(conn, "CGB", "GRU", date(2026, 10, 3), date(2026, 10, 8)) is None
    finally:
        conn.close()


def test_media_precos_recentes_ignora_registros_antigos(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        antigo = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        recente1 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        recente2 = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
        historico.registrar_voos(conn, [_voo(2000.0)], timestamp=antigo)
        historico.registrar_voos(conn, [_voo(600.0)], timestamp=recente1)
        historico.registrar_voos(conn, [_voo(700.0)], timestamp=recente2)

        media = historico.media_precos_recentes(
            conn, "CGB", "GRU", date(2026, 10, 3), date(2026, 10, 8),
            desde=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )
        assert media == 650.0
    finally:
        conn.close()


def test_media_precos_recentes_e_especifica_por_janela(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        momento = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
        historico.registrar_voos(
            conn,
            [
                _voo(600.0, destino="GRU", ida=date(2026, 10, 3), volta=date(2026, 10, 8)),
                _voo(1000.0, destino="CGH", ida=date(2026, 10, 5), volta=date(2026, 10, 10)),
            ],
            timestamp=momento,
        )

        desde = datetime(2026, 6, 15, tzinfo=timezone.utc)
        assert historico.media_precos_recentes(conn, "CGB", "GRU", date(2026, 10, 3), date(2026, 10, 8), desde) == 600.0
        assert historico.media_precos_recentes(conn, "CGB", "CGH", date(2026, 10, 5), date(2026, 10, 10), desde) == 1000.0
        # janela sem nenhum registro proprio -- nao herda media de outra janela
        assert historico.media_precos_recentes(conn, "CGB", "GRU", date(2026, 11, 1), date(2026, 11, 6), desde) is None
    finally:
        conn.close()


def test_menor_preco_geral_entre_rotas_diferentes(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        momento = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
        historico.registrar_voos(
            conn, [_voo(900.0, destino="GRU"), _voo(550.0, destino="CGH")], timestamp=momento
        )
        resultado = historico.menor_preco_geral(conn, "CGB")
        assert resultado == {
            "origem": "CGB",
            "destino": "CGH",
            "ida": "2026-10-03",
            "volta": "2026-10-08",
            "preco": 550.0,
            "encontrado_em": momento.isoformat(),
        }
    finally:
        conn.close()


def test_menor_preco_geral_sem_dados_retorna_none(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        assert historico.menor_preco_geral(conn, "CGB") is None
    finally:
        conn.close()


def test_metadados_obter_e_definir(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        assert historico.obter_metadado(conn, "ultimo_aviso_erro") is None

        historico.definir_metadado(conn, "ultimo_aviso_erro", "2026-07-13")
        assert historico.obter_metadado(conn, "ultimo_aviso_erro") == "2026-07-13"

        historico.definir_metadado(conn, "ultimo_aviso_erro", "2026-07-14")
        assert historico.obter_metadado(conn, "ultimo_aviso_erro") == "2026-07-14"
    finally:
        conn.close()


def test_janelas_mais_baratas_recentes_usa_so_a_ultima_leva(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        antiga = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        recente = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
        # leva antiga tinha algo bem mais barato, mas nao deve ser considerada
        historico.registrar_voos(conn, [_voo(100.0, destino="GRU", ida=date(2026, 10, 1), volta=date(2026, 10, 6))], timestamp=antiga)
        historico.registrar_voos(
            conn,
            [
                _voo(700.0, destino="GRU", ida=date(2026, 10, 3), volta=date(2026, 10, 8)),
                _voo(600.0, destino="CGH", ida=date(2026, 10, 5), volta=date(2026, 10, 10)),
                _voo(900.0, destino="GRU", ida=date(2026, 10, 6), volta=date(2026, 10, 11)),
            ],
            timestamp=recente,
        )

        janelas = historico.janelas_mais_baratas_recentes(conn, "CGB", quantidade=2)
        assert janelas == [
            {"destino": "CGH", "ida": date(2026, 10, 5), "volta": date(2026, 10, 10)},
            {"destino": "GRU", "ida": date(2026, 10, 3), "volta": date(2026, 10, 8)},
        ]
    finally:
        conn.close()


def test_janelas_mais_baratas_recentes_sem_historico(tmp_path):
    caminho = str(tmp_path / "historico.db")
    conn = historico.conectar(caminho)
    try:
        assert historico.janelas_mais_baratas_recentes(conn, "CGB", quantidade=3) == []
    finally:
        conn.close()
