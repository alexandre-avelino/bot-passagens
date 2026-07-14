from bot_passagens import telegram


def test_texto_curto_nao_e_dividido():
    texto = "mensagem curta"
    assert telegram._dividir_em_partes(texto, limite=100) == [texto]


def test_texto_longo_e_dividido_em_paragrafos():
    paragrafo = "x" * 50
    texto = "\n\n".join([paragrafo] * 10)  # ~540 caracteres com as quebras
    partes = telegram._dividir_em_partes(texto, limite=120)

    assert len(partes) > 1
    for parte in partes:
        assert len(parte) <= 120

    # nenhum conteudo perdido: cada paragrafo original aparece em alguma parte
    for i in range(10):
        assert any(paragrafo in parte for parte in partes)


def test_paragrafo_isolado_maior_que_limite_nao_quebra_o_codigo():
    paragrafo_gigante = "y" * 500
    partes = telegram._dividir_em_partes(paragrafo_gigante, limite=120)
    # nao ha quebra de paragrafo possivel: melhor mandar inteiro do que travar
    assert partes == [paragrafo_gigante]


def test_enviar_mensagem_longa_manda_uma_chamada_por_parte(monkeypatch):
    chamadas = []
    monkeypatch.setattr(telegram, "enviar_mensagem", lambda token, chat_id, texto: chamadas.append(texto))

    # excede de proposito o LIMITE_CARACTERES padrao (3900) pra forcar a divisao
    paragrafo = "z" * 50
    texto = "\n\n".join([paragrafo] * 100)
    telegram.enviar_mensagem_longa("token", "chat", texto)

    assert len(chamadas) > 1
    assert all(len(c) <= telegram.LIMITE_CARACTERES for c in chamadas)


def test_enviar_mensagem_longa_com_texto_curto_manda_uma_unica_chamada(monkeypatch):
    chamadas = []
    monkeypatch.setattr(telegram, "enviar_mensagem", lambda token, chat_id, texto: chamadas.append(texto))

    telegram.enviar_mensagem_longa("token", "chat", "mensagem curta")

    assert chamadas == ["mensagem curta"]
