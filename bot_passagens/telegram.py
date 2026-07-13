"""Envio de mensagens via Telegram Bot API (chamada HTTP direta, sem framework)."""

import requests

API_BASE = "https://api.telegram.org"


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
