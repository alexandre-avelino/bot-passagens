"""Ponto de entrada: busca as janelas validas e envia as mais baratas para o Telegram.

Fase 1: sem historico ainda (isso chega na Fase 2 com SQLite), entao o resumo
mostra sempre as N janelas mais baratas encontradas nesta execucao.
"""

import os
import sys
import time
from datetime import datetime, timezone

from bot_passagens.config import Config, carregar_config
from bot_passagens.dates import Janela, gerar_combinacoes
from bot_passagens.models import Voo
from bot_passagens.providers.base import ProviderError
from bot_passagens.providers.fast_flights_provider import FastFlightsProvider
from bot_passagens.telegram import enviar_mensagem

DELAY_ENTRE_BUSCAS_SEGUNDOS = 2.5
TOP_N = 3


def _buscar_todos_os_voos(config: Config) -> tuple[list[Voo], list[str], int]:
    provider = FastFlightsProvider()
    janelas: list[Janela] = gerar_combinacoes(
        periodo_inicio=config.periodo_inicio,
        periodo_fim=config.periodo_fim,
        dias_obrigatorios=config.dias_obrigatorios,
        margem_adjacente=config.margem_adjacente,
        duracao_minima=config.duracao.minima,
        duracao_maxima=config.duracao.maxima,
    )

    todos_os_voos: list[Voo] = []
    erros: list[str] = []
    total_buscas = len(config.destinos) * len(janelas)

    for destino in config.destinos:
        for janela in janelas:
            try:
                voos = provider.buscar(config.origem, destino, janela.ida, janela.volta, config.passageiros)
                todos_os_voos.extend(voos)
            except ProviderError as erro:
                print(f"[aviso] {erro}", file=sys.stderr)
                erros.append(str(erro))
            time.sleep(DELAY_ENTRE_BUSCAS_SEGUNDOS)

    return todos_os_voos, erros, total_buscas


def _formatar_preco(valor: float) -> str:
    texto = f"{valor:,.2f}"
    parte_inteira, parte_decimal = texto.split(".")
    parte_inteira = parte_inteira.replace(",", ".")
    return f"R$ {parte_inteira},{parte_decimal}"


def _formatar_mensagem(voos_top: list[Voo], total_buscas: int, erros: list[str]) -> str:
    agora = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    if not voos_top:
        linhas = ["*Bot de passagens*", "", "Nenhum voo encontrado nas janelas monitoradas desta vez."]
    else:
        linhas = [f"*Top {len(voos_top)} janelas mais baratas*", ""]
        for i, voo in enumerate(voos_top, start=1):
            noites = (voo.volta - voo.ida).days
            escalas_texto = "direto" if voo.escalas == 0 else f"{voo.escalas} escala(s)"
            linhas.append(
                f"{i}. {voo.origem} -> {voo.destino} | "
                f"{voo.ida.strftime('%d/%m')} a {voo.volta.strftime('%d/%m')} ({noites} noites)\n"
                f"   {voo.companhia} - {_formatar_preco(voo.preco)} - {escalas_texto} (ida)\n"
                f"   {voo.link}"
            )

    linhas.append("")
    linhas.append(f"_{total_buscas} janelas verificadas em {agora}._")

    if erros:
        linhas.append(f"_Aviso: {len(erros)} busca(s) falharam nesta execucao (ver logs do Actions)._")

    return "\n".join(linhas)


def main() -> None:
    config_path = os.environ.get("BOT_PASSAGENS_CONFIG", "config.yaml")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise SystemExit("Defina as variaveis de ambiente TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID antes de rodar.")

    config = carregar_config(config_path)
    todos_os_voos, erros, total_buscas = _buscar_todos_os_voos(config)
    voos_top = sorted(todos_os_voos, key=lambda v: v.preco)[:TOP_N]

    mensagem = _formatar_mensagem(voos_top, total_buscas=total_buscas, erros=erros)
    enviar_mensagem(token, chat_id, mensagem)
    print(mensagem)


if __name__ == "__main__":
    main()
