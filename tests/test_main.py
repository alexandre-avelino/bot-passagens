from datetime import date

from bot_passagens.alerta import Alerta
from bot_passagens.config import Alertas, Config, Duracao, HorarioExcluido
from bot_passagens.main import _filtrar_horario_saida, _formatar_mensagem_alerta_rapido, _formatar_mensagem_detalhe
from bot_passagens.models import Voo


def _voo(
    preco: float, destino: str = "GRU", ida: date = date(2026, 10, 3),
    volta: date = date(2026, 10, 8), partida: str = "08:00",
) -> Voo:
    return Voo(
        origem="CGB",
        destino=destino,
        ida=ida,
        volta=volta,
        companhia="Gol",
        preco=preco,
        escalas=0,
        partida=partida,
        chegada="11:00",
        link="https://exemplo",
    )


def _config_com_filtro() -> Config:
    from datetime import time

    return Config(
        tipo_viagem="somente_ida", origem="CGB", destinos=["GRU", "CGH"],
        periodo_inicio=date(2027, 1, 1), periodo_fim=date(2027, 1, 14),
        dias_obrigatorios=[], margem_adjacente=0, duracao=Duracao(0, 0),
        passageiros=1, horario_saida_excluido=HorarioExcluido(time(2), time(6)),
        alertas=Alertas(350, 10, True), resumo_diario="08:00",
    )


def test_filtra_voos_que_saem_entre_02h_e_05h59():
    voos = [
        _voo(200, partida="01:59"),
        _voo(210, partida="02:00"),
        _voo(220, partida="05:59"),
        _voo(230, partida="06:00"),
    ]

    filtrados = _filtrar_horario_saida(voos, _config_com_filtro())

    assert [voo.partida for voo in filtrados] == ["01:59", "06:00"]


def test_detalhe_sem_voos():
    texto = _formatar_mensagem_detalhe([], {}, {})
    assert "Nenhum voo encontrado" in texto


def test_bloco_voo_somente_ida_nao_mostra_noites_nem_seta_de_volta():
    voo = _voo(300.0, ida=date(2027, 1, 5), volta=date(2027, 1, 5))
    texto = _formatar_mensagem_detalhe([voo], {}, {})
    assert "ida em 05/01" in texto
    assert "noites" not in texto


def test_detalhe_sem_motivos_nao_tem_selo_de_alerta():
    voo = _voo(600.0)
    medias = {(voo.destino, voo.ida, voo.volta): 700.0}
    texto = _formatar_mensagem_detalhe([voo], {}, medias)
    assert "🚨" not in texto
    assert "abaixo da média dessa janela" in texto


def test_detalhe_com_motivo_mostra_selo_e_motivo():
    voo = _voo(600.0, destino="CGH", ida=date(2026, 10, 5), volta=date(2026, 10, 10))
    chave = ("CGH", date(2026, 10, 5), date(2026, 10, 10))
    motivos_por_janela = {chave: ["Novo menor preço já visto para essa janela"]}
    medias = {chave: 700.0}
    texto = _formatar_mensagem_detalhe([voo], motivos_por_janela, medias)
    assert "🚨" in texto
    assert "Novo menor preço já visto para essa janela" in texto


def test_detalhe_sem_media_nao_quebra():
    voo = _voo(600.0)
    texto = _formatar_mensagem_detalhe([voo], {}, {})
    assert "média" not in texto
    assert "R$ 600,00" in texto


def test_detalhe_media_e_por_janela_nao_compartilhada():
    voo1 = _voo(600.0, destino="GRU")
    voo2 = _voo(1000.0, destino="CGH", ida=date(2026, 11, 1), volta=date(2026, 11, 6))
    medias = {(voo1.destino, voo1.ida, voo1.volta): 700.0}  # so voo1 tem media conhecida
    texto = _formatar_mensagem_detalhe([voo1, voo2], {}, medias)
    assert "abaixo da média dessa janela" in texto
    # voo2 nao deve ganhar a media de voo1 -- so aparece uma linha de media no total
    assert texto.count("📊") == 1


def test_detalhe_direcao_acima_quando_preco_maior_que_media():
    voo = _voo(1000.0)
    medias = {(voo.destino, voo.ida, voo.volta): 700.0}
    texto = _formatar_mensagem_detalhe([voo], {}, medias)
    assert "acima da média dessa janela" in texto


def test_alerta_rapido_mostra_apenas_as_janelas_disparadas():
    alertas = [
        Alerta(voo=_voo(650.0), motivos=["Novo menor preço já visto para essa janela"], media_recente=700.0),
    ]
    texto = _formatar_mensagem_alerta_rapido(alertas)
    assert "Alerta rápido" in texto
    assert "Novo menor preço já visto para essa janela" in texto
    assert "R$ 650,00" in texto


def test_alerta_rapido_ordena_por_preco():
    alertas = [
        Alerta(voo=_voo(900.0, destino="GRU"), motivos=["Abaixo do teto configurado (R$ 1.000,00)"], media_recente=None),
        Alerta(voo=_voo(600.0, destino="CGH"), motivos=["Abaixo do teto configurado (R$ 1.000,00)"], media_recente=None),
    ]
    texto = _formatar_mensagem_alerta_rapido(alertas)
    assert texto.index("R$ 600,00") < texto.index("R$ 900,00")
