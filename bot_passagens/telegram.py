"""Envio de mensagens via Telegram Bot API (chamada HTTP direta, sem framework)."""

from typing import List

import requests

API_BASE = "https://api.telegram.org"

# Limite real do Telegram e 4096 caracteres por mensagem; deixamos uma folga.
LIMITE_CARACTERES = 3900


class TelegramError(Exception):
    """Erro ao enviar mensagem via Telegram."""


def enviar_mensagem(token: str, chat_id: str, texto: str) -> None:
    url = f"{API_BASE}/bot{token}/sendMessage"
    resposta = requests.post(
        url,
        data={
            "chat_id": chat_id,
            "text": texto,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    if not resposta.ok:
        raise TelegramError(f"Telegram respondeu {resposta.status_code}: {resposta.text}")


def _dividir_em_partes(texto: str, limite: int = LIMITE_CARACTERES) -> List[str]:
    """Divide o texto em pedacos <= limite, cortando em quebras de paragrafo
    (linha em branco) sempre que possivel, para nao partir um bloco no meio.
    """
    if len(texto) <= limite:
        return [texto]

    partes: List[str] = []
    atual = ""
    for paragrafo in texto.split("\n\n"):
        candidato = f"{atual}\n\n{paragrafo}" if atual else paragrafo
        if len(candidato) > limite and atual:
            partes.append(atual)
            atual = paragrafo
        else:
            atual = candidato
    if atual:
        partes.append(atual)
    return partes


def enviar_mensagem_longa(token: str, chat_id: str, texto: str) -> None:
    """Envia `texto` como uma ou mais mensagens, respeitando o limite do Telegram."""
    for parte in _dividir_em_partes(texto):
        enviar_mensagem(token, chat_id, parte)
