"""Ponto de entrada: busca as janelas validas, registra o historico, avalia
as regras de alerta e envia as notificacoes adequadas para o Telegram.

Duas notificacoes independentes por execucao:
- alerta imediato: enviado so quando alguma janela bate uma regra (teto,
  queda % ou novo menor preco);
- resumo diario: enviado so na execucao marcada como tal (ver RESUMO_DIARIO
  no workflow), com o top N do dia e o menor preco ja visto no historico.

Se nenhuma das duas se aplica, a execucao nao manda nada no Telegram -- isso
e esperado, nao e uma falha.
"""

import os
import sqlite3
import sys
import time
from datetime import date, datetime, timezone
from typing import List, Optional

from bot_passagens import alerta, historico
from bot_passagens.alerta import Alerta
from bot_passagens.config import Config, carregar_config
from bot_passagens.dates import Janela, gerar_combinacoes
from bot_passagens.formatacao import formatar_preco
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


def _bloco_voo(rotulo: str, voo: Voo) -> str:
    noites = (voo.volta - voo.ida).days
    return (
        f"{rotulo} {voo.origem} → {voo.destino} · "
        f"{voo.ida.strftime('%d/%m')} → {voo.volta.strftime('%d/%m')} ({noites} noites)\n"
        f"💰 *{formatar_preco(voo.preco)}* — {voo.companhia} — {_formatar_escalas(voo.escalas)}\n"
        f"🕐 {voo.partida} → {voo.chegada} (ida)\n"
        f"🔗 [Ver oferta no Google Voos]({voo.link})"
    )


def _formatar_mensagem_alerta(alertas_disparados: List[Alerta]) -> str:
    linhas = ["🚨 *Alerta de preco!*", ""]
    for item in alertas_disparados:
        linhas.append(_bloco_voo("📍", item.voo))
        for motivo in item.motivos:
            linhas.append(f"    • {motivo}")
        if item.media_recente is not None:
            diferenca_pct = (item.media_recente - item.voo.preco) / item.media_recente * 100
            linhas.append(
                f"    📊 {diferenca_pct:.0f}% em relacao a media dos ultimos 30 dias "
                f"({formatar_preco(item.media_recente)})"
            )
        linhas.append("")
    return "\n".join(linhas).rstrip()


def _formatar_mensagem_resumo(
    voos_top: List[Voo], total_buscas: int, menor_geral: Optional[dict], erros: List[str]
) -> str:
    agora = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    if not voos_top:
        linhas = ["📋 *Resumo diario*", "", "🤷 Nenhum voo encontrado nas janelas monitoradas desta vez."]
    else:
        linhas = [f"📋 *Resumo diario* — top {len(voos_top)} janelas mais baratas", ""]
        for i, voo in enumerate(voos_top):
            linhas.append(_bloco_voo(_rotulo_posicao(i), voo))
            linhas.append("")

        if menor_geral is not None:
            ida_fmt = date.fromisoformat(menor_geral["ida"]).strftime("%d/%m")
            volta_fmt = date.fromisoformat(menor_geral["volta"]).strftime("%d/%m")
            linhas.append(
                f"🏆 Menor preco ja registrado: *{formatar_preco(menor_geral['preco'])}* — "
                f"{menor_geral['origem']} → {menor_geral['destino']} · {ida_fmt} → {volta_fmt}"
            )
            linhas.append("")

    linhas.append(f"🔎 {total_buscas} janelas verificadas · 🕒 {agora}")

    if erros:
        linhas.append(f"⚠️ {len(erros)} busca(s) falharam nesta execucao (ver logs do Actions).")

    return "\n".join(linhas)


def _avisar_erros_no_maximo_uma_vez_por_dia(
    conn: sqlite3.Connection, token: str, chat_id: str, erros: List[str], hoje: str
) -> None:
    if not erros:
        return
    if historico.obter_metadado(conn, "ultimo_aviso_erro") == hoje:
        print(f"[info] {len(erros)} erro(s) nesta execucao, mas o aviso de hoje ja foi enviado.")
        return

    mensagem = (
        f"⚠️ *Aviso*\n\n{len(erros)} busca(s) falharam nesta execucao. "
        "Ver logs do GitHub Actions para detalhes."
    )
    enviar_mensagem(token, chat_id, mensagem)
    historico.definir_metadado(conn, "ultimo_aviso_erro", hoje)
    print(mensagem)


def main() -> None:
    config_path = os.environ.get("BOT_PASSAGENS_CONFIG", "config.yaml")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    resumo_diario = os.environ.get("RESUMO_DIARIO", "").lower() == "true"

    if not token or not chat_id:
        raise SystemExit("Defina as variaveis de ambiente TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID antes de rodar.")

    config = carregar_config(config_path)
    agora = datetime.now(timezone.utc)
    todos_os_voos, erros, total_buscas = _buscar_todos_os_voos(config)

    historico_path = os.environ.get("BOT_PASSAGENS_HISTORICO", historico.CAMINHO_PADRAO)
    conn = historico.conectar(historico_path)
    try:
        # avaliar ANTES de registrar: as comparacoes precisam ser contra o
        # que ja estava no historico antes desta execucao.
        alertas_disparados = alerta.avaliar(conn, config.alertas, todos_os_voos, agora)
        historico.registrar_voos(conn, todos_os_voos, timestamp=agora)

        if alertas_disparados:
            mensagem_alerta = _formatar_mensagem_alerta(alertas_disparados)
            enviar_mensagem(token, chat_id, mensagem_alerta)
            print(mensagem_alerta)

        if resumo_diario:
            voos_top = sorted(todos_os_voos, key=lambda v: v.preco)[:TOP_N]
            menor_geral = historico.menor_preco_geral(conn, config.origem)
            mensagem_resumo = _formatar_mensagem_resumo(voos_top, total_buscas, menor_geral, erros)
            enviar_mensagem(token, chat_id, mensagem_resumo)
            print(mensagem_resumo)

        if not alertas_disparados and not resumo_diario:
            print(f"Nenhum alerta e execucao nao e o resumo diario -- nenhuma mensagem enviada ({total_buscas} janelas verificadas).")

        _avisar_erros_no_maximo_uma_vez_por_dia(conn, token, chat_id, erros, hoje=agora.date().isoformat())
    finally:
        conn.close()


if __name__ == "__main__":
    main()
