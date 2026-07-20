from datetime import date

from bot_passagens.alerta import Alerta
from bot_passagens.main import _formatar_mensagem_alerta_rapido, _formatar_mensagem_detalhe
from bot_passagens.models import Voo


def _voo(preco: float, destino: str = "GRU", ida: date = date(2026, 10, 3), volta: date = date(2026, 10, 8)) -> Voo:
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


def test_detalhe_sem_voos():
    texto = _formatar_mensagem_detalhe([], {}, {})
    assert "Nenhum voo encontrado" in texto


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
