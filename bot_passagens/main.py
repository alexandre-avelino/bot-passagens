"""Ponto de entrada: busca as janelas validas, registra o historico e envia
as mais baratas para o Telegram.
"""

import os
import sys
import time
from datetime import datetime, timezone

from bot_passagens import historico
from bot_passagens.config import Config, carregar_config
from bot_passagens.dates import Janela, gerar_combinacoes
from bot_passagens.models import Voo
from bot_passagens.providers.base import ProviderError
from bot_passagens.providers.fast_flights_provider import FastFlightsProvider
from bot_passagens.telegram import enviar_mensagem

DELAY_ENTRE_BUSCAS_SEGUNDOS = 2.5
TOP_N = 3
MEDALHAS = ["🥇", "🥈", "🥉"]


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


def _formatar_escalas(escalas: int) -> str:
    if escalas == 0:
        return "voo direto ✈️"
    if escalas == 1:
        return "1 escala"
    return f"{escalas} escalas"


def _rotulo_posicao(indice: int) -> str:
    if indice < len(MEDALHAS):
        return MEDALHAS[indice]
    return f"{indice + 1}º"


def _formatar_mensagem(voos_top: list[Voo], total_buscas: int, erros: list[str]) -> str:
    agora = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    if not voos_top:
        linhas = ["✈️ *Bot de passagens*", "", "🤷 Nenhum voo encontrado nas janelas monitoradas desta vez."]
    else:
        linhas = [f"✈️ *Top {len(voos_top)} janelas mais baratas*", ""]
        for i, voo in enumerate(voos_top):
            noites = (voo.volta - voo.ida).days
            linhas.append(
                f"{_rotulo_posicao(i)} {voo.origem} → {voo.destino} · "
                f"{voo.ida.strftime('%d/%m')} → {voo.volta.strftime('%d/%m')} ({noites} noites)\n"
                f"💰 *{_formatar_preco(voo.preco)}* — {voo.companhia} — {_formatar_escalas(voo.escalas)}\n"
                f"🕐 {voo.partida} → {voo.chegada} (ida)\n"
                f"🔗 [Ver oferta no Google Voos]({voo.link})"
            )
            linhas.append("")

    linhas.append(f"🔎 {total_buscas} janelas verificadas · 🕒 {agora}")

    if erros:
        linhas.append(f"⚠️ {len(erros)} busca(s) falharam nesta execucao (ver logs do Actions).")

    return "\n".join(linhas)


def main() -> None:
    config_path = os.environ.get("BOT_PASSAGENS_CONFIG", "config.yaml")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise SystemExit("Defina as variaveis de ambiente TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID antes de rodar.")

    config = carregar_config(config_path)
    todos_os_voos, erros, total_buscas = _buscar_todos_os_voos(config)

    historico_path = os.environ.get("BOT_PASSAGENS_HISTORICO", historico.CAMINHO_PADRAO)
    conn = historico.conectar(historico_path)
    try:
        historico.registrar_voos(conn, todos_os_voos)
    finally:
        conn.close()

    voos_top = sorted(todos_os_voos, key=lambda v: v.preco)[:TOP_N]

    mensagem = _formatar_mensagem(voos_top, total_buscas=total_buscas, erros=erros)
    enviar_mensagem(token, chat_id, mensagem)
    print(mensagem)


if __name__ == "__main__":
    main()
