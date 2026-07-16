from datetime import date, datetime, timedelta, timezone

from bot_passagens import historico
from bot_passagens.alerta import avaliar
from bot_passagens.config import Alertas
from bot_passagens.models import Voo

IDA = date(2026, 10, 3)
VOLTA = date(2026, 10, 8)
AGORA = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def _voo(preco: float, destino: str = "GRU", ida: date = IDA, volta: date = VOLTA) -> Voo:
    return Voo(
        origem="CGB",
        destino=destino,
        ida=ida,
        volta=volta,
        companhia="Gol",
        preco=preco,
        escalas=0,
        partida="08:00",
        chegada="11:00",
        link="https://exemplo",
    )


def _config_alertas(preco_maximo=900.0, queda_percentual=10.0, novo_menor_preco=True) -> Alertas:
    return Alertas(preco_maximo=preco_maximo, queda_percentual=queda_percentual, novo_menor_preco=novo_menor_preco)


def test_sem_historico_e_preco_acima_do_teto_nao_dispara_nada(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        alertas = avaliar(conn, _config_alertas(preco_maximo=500.0), [_voo(900.0)], AGORA)
        assert alertas == []
    finally:
        conn.close()


def test_preco_abaixo_do_teto_dispara_mesmo_sem_historico(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        alertas = avaliar(conn, _config_alertas(preco_maximo=1000.0), [_voo(900.0)], AGORA)
        assert len(alertas) == 1
        assert any("teto" in motivo for motivo in alertas[0].motivos)
    finally:
        conn.close()


def test_queda_percentual_acima_do_limiar_dispara(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        historico.registrar_voos(conn, [_voo(1000.0)], timestamp=AGORA - timedelta(days=1))
        # cai de 1000 para 800 -> 20% de queda, limiar configurado e 10%
        alertas = avaliar(conn, _config_alertas(preco_maximo=1.0, queda_percentual=10.0, novo_menor_preco=False), [_voo(800.0)], AGORA)
        assert len(alertas) == 1
        assert any("caiu" in motivo.lower() for motivo in alertas[0].motivos)
    finally:
        conn.close()


def test_queda_percentual_abaixo_do_limiar_nao_dispara(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        historico.registrar_voos(conn, [_voo(1000.0)], timestamp=AGORA - timedelta(days=1))
        # cai de 1000 para 950 -> 5% de queda, limiar configurado e 10%
        alertas = avaliar(conn, _config_alertas(preco_maximo=1.0, queda_percentual=10.0, novo_menor_preco=False), [_voo(950.0)], AGORA)
        assert alertas == []
    finally:
        conn.close()


def test_novo_menor_preco_dispara_quando_bate_recorde(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        historico.registrar_voos(conn, [_voo(700.0)], timestamp=AGORA - timedelta(days=5))
        alertas = avaliar(conn, _config_alertas(preco_maximo=1.0, queda_percentual=1000.0, novo_menor_preco=True), [_voo(650.0)], AGORA)
        assert len(alertas) == 1
        assert any("novo menor preço" in motivo.lower() for motivo in alertas[0].motivos)
    finally:
        conn.close()


def test_novo_menor_preco_nao_dispara_se_nao_bate_recorde(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        historico.registrar_voos(conn, [_voo(700.0)], timestamp=AGORA - timedelta(days=5))
        alertas = avaliar(conn, _config_alertas(preco_maximo=1.0, queda_percentual=1000.0, novo_menor_preco=True), [_voo(750.0)], AGORA)
        assert alertas == []
    finally:
        conn.close()


def test_novo_menor_preco_desabilitado_na_config_nao_dispara(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        historico.registrar_voos(conn, [_voo(700.0)], timestamp=AGORA - timedelta(days=5))
        alertas = avaliar(conn, _config_alertas(preco_maximo=1.0, queda_percentual=1000.0, novo_menor_preco=False), [_voo(650.0)], AGORA)
        assert alertas == []
    finally:
        conn.close()


def test_varias_janelas_avaliadas_independentemente(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        voos = [
            _voo(500.0, ida=date(2026, 10, 3), volta=date(2026, 10, 8)),  # abaixo do teto
            _voo(2000.0, ida=date(2026, 10, 5), volta=date(2026, 10, 10)),  # nao dispara nada
        ]
        alertas = avaliar(conn, _config_alertas(preco_maximo=600.0, queda_percentual=1000.0, novo_menor_preco=False), voos, AGORA)
        assert len(alertas) == 1
        assert alertas[0].voo.preco == 500.0
    finally:
        conn.close()


def test_agrupa_pelo_voo_mais_barato_da_janela(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        voos = [_voo(900.0), _voo(500.0), _voo(700.0)]
        alertas = avaliar(conn, _config_alertas(preco_maximo=600.0, queda_percentual=1000.0, novo_menor_preco=False), voos, AGORA)
        assert len(alertas) == 1
        assert alertas[0].voo.preco == 500.0
    finally:
        conn.close()


def test_media_recente_e_incluida_quando_ha_historico(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        historico.registrar_voos(conn, [_voo(600.0)], timestamp=AGORA - timedelta(days=2))
        historico.registrar_voos(conn, [_voo(700.0)], timestamp=AGORA - timedelta(days=1))
        alertas = avaliar(conn, _config_alertas(preco_maximo=650.0, queda_percentual=1000.0, novo_menor_preco=False), [_voo(620.0)], AGORA)
        assert len(alertas) == 1
        assert alertas[0].media_recente == 650.0
    finally:
        conn.close()


def test_media_recente_none_sem_historico(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        alertas = avaliar(conn, _config_alertas(preco_maximo=1000.0), [_voo(900.0)], AGORA)
        assert len(alertas) == 1
        assert alertas[0].media_recente is None
    finally:
        conn.close()


def test_media_recente_e_geral_entre_destinos_e_janelas_diferentes(tmp_path):
    conn = historico.conectar(str(tmp_path / "historico.db"))
    try:
        # historico de duas janelas bem diferentes (destinos e datas distintas)
        historico.registrar_voos(
            conn,
            [_voo(600.0, destino="GRU", ida=date(2026, 10, 3), volta=date(2026, 10, 8))],
            timestamp=AGORA - timedelta(days=2),
        )
        historico.registrar_voos(
            conn,
            [_voo(1000.0, destino="CGH", ida=date(2026, 10, 20), volta=date(2026, 10, 25))],
            timestamp=AGORA - timedelta(days=1),
        )

        # alerta disparado numa TERCEIRA janela, que nunca apareceu antes --
        # a media exibida deve vir do geral (600 e 1000 -> 800), nao ficar None
        # so porque essa janela especifica nao tem historico proprio.
        alertas = avaliar(
            conn,
            _config_alertas(preco_maximo=700.0, queda_percentual=1000.0, novo_menor_preco=False),
            [_voo(650.0, destino="GRU", ida=date(2026, 10, 5), volta=date(2026, 10, 12))],
            AGORA,
        )
        assert len(alertas) == 1
        assert alertas[0].media_recente == 800.0
    finally:
        conn.close()
