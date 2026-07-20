"""Ponto de entrada: busca as janelas validas, registra o historico, avalia
as regras de alerta e envia as notificacoes para o Telegram.

Dois modos de execucao (MODO_EXECUCAO):
- "completo" (padrao, 2x/dia): varre TODAS as janelas monitoradas e manda
  sempre duas mensagens -- Detalhe (top N mais baratas, com selo 🚨 e
  motivos nas que baterem alguma regra) e Resumo (as mesmas top N + o menor
  preco ja registrado em todo o historico).
- "rapido" (varias vezes ao dia, opcional): revisita so as
  QUANTIDADE_JANELAS_RAPIDAS janelas que estavam mais baratas na ultima
  leva completa, pra pegar quedas de preco entre as execucoes completas sem
  repetir a varredura toda (economiza requisicoes ao Google Voos). So manda
  mensagem se alguma regra de alerta disparar; senao fica em silencio.
"""

import os
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from bot_passagens import alerta, dashboard, historico
from bot_passagens.alerta import Alerta
from bot_passagens.config import Config, carregar_config
from bot_passagens.dates import Janela, gerar_combinacoes
from bot_passagens.formatacao import formatar_preco
from bot_passagens.models import Voo
from bot_passagens.providers.base import ProviderError
from bot_passagens.providers.fast_flights_provider import FastFlightsProvider
from bot_passagens.telegram import enviar_mensagem, enviar_mensagem_longa

DELAY_ENTRE_BUSCAS_SEGUNDOS = 2.5
TOP_N = 3
QUANTIDADE_JANELAS_RAPIDAS = 3
MEDALHAS = ["🥇", "🥈", "🥉"]
FUSO_HORARIO_LOCAL = ZoneInfo("America/Cuiaba")


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


def _buscar_janelas_especificas(config: Config, janelas: List[dict]) -> tuple[list[Voo], list[str]]:
    provider = FastFlightsProvider()
    todos_os_voos: list[Voo] = []
    erros: list[str] = []

    for j in janelas:
        try:
            voos = provider.buscar(config.origem, j["destino"], j["ida"], j["volta"], config.passageiros)
            todos_os_voos.extend(voos)
        except ProviderError as erro:
            print(f"[aviso] {erro}", file=sys.stderr)
            erros.append(str(erro))
        time.sleep(DELAY_ENTRE_BUSCAS_SEGUNDOS)

    return todos_os_voos, erros


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


def _formatar_mensagem_detalhe(
    voos_top: List[Voo],
    motivos_por_janela: Dict[Tuple[str, date, date], List[str]],
    medias_por_janela: Dict[Tuple[str, date, date], Optional[float]],
) -> str:
    if not voos_top:
        return "📋 *Detalhe das buscas*\n\n🤷 Nenhum voo encontrado nas janelas monitoradas desta vez."

    linhas = [f"📋 *Detalhe das buscas* — top {len(voos_top)} janelas mais baratas", ""]
    for i, voo in enumerate(voos_top):
        chave_janela = (voo.destino, voo.ida, voo.volta)
        motivos = motivos_por_janela.get(chave_janela, [])
        rotulo = _rotulo_posicao(i)
        if motivos:
            rotulo = f"🚨 {rotulo}"
        linhas.append(_bloco_voo(rotulo, voo))
        for motivo in motivos:
            linhas.append(f"    • {motivo}")
        media_janela = medias_por_janela.get(chave_janela)
        if media_janela is not None:
            diferenca_pct = (media_janela - voo.preco) / media_janela * 100
            direcao = "abaixo" if diferenca_pct >= 0 else "acima"
            linhas.append(
                f"    📊 {abs(diferenca_pct):.0f}% {direcao} da média dessa janela nos últimos 30 dias "
                f"({formatar_preco(media_janela)})"
            )
        linhas.append("")
    return "\n".join(linhas).rstrip()


def _formatar_mensagem_resumo(
    voos_top: List[Voo], total_buscas: int, menor_geral: Optional[dict], erros: List[str]
) -> str:
    agora = datetime.now(timezone.utc).astimezone(FUSO_HORARIO_LOCAL).strftime("%d/%m/%Y %H:%M")

    if not voos_top:
        linhas = ["📈 *Resumo*", "", "🤷 Nenhum voo encontrado nas janelas monitoradas desta vez."]
    else:
        linhas = [f"📈 *Resumo* — top {len(voos_top)} janelas mais baratas", ""]
        for i, voo in enumerate(voos_top):
            linhas.append(_bloco_voo(_rotulo_posicao(i), voo))
            linhas.append("")

        if menor_geral is not None:
            ida_fmt = date.fromisoformat(menor_geral["ida"]).strftime("%d/%m")
            volta_fmt = date.fromisoformat(menor_geral["volta"]).strftime("%d/%m")
            encontrado_em_fmt = (
                datetime.fromisoformat(menor_geral["encontrado_em"]).astimezone(FUSO_HORARIO_LOCAL).strftime("%d/%m/%Y")
            )
            linhas.append(
                f"🏆 Menor preço já registrado: *{formatar_preco(menor_geral['preco'])}* — "
                f"{menor_geral['origem']} → {menor_geral['destino']} · {ida_fmt} → {volta_fmt} "
                f"(encontrado em {encontrado_em_fmt})"
            )
            linhas.append("")

    linhas.append(f"🔎 {total_buscas} janelas verificadas · 🕒 {agora} (Cuiabá)")

    if erros:
        linhas.append(f"⚠️ {len(erros)} busca(s) falharam nesta execução (ver logs do Actions).")

    return "\n".join(linhas)


def _formatar_mensagem_alerta_rapido(alertas_disparados: List[Alerta]) -> str:
    linhas = ["⚡ *Alerta rápido*", ""]
    for item in sorted(alertas_disparados, key=lambda a: a.voo.preco):
        linhas.append(_bloco_voo("🚨", item.voo))
        for motivo in item.motivos:
            linhas.append(f"    • {motivo}")
        linhas.append("")
    return "\n".join(linhas).rstrip()


def _avisar_erros_no_maximo_uma_vez_por_dia(
    conn: sqlite3.Connection, token: str, chat_id: str, erros: List[str], hoje: str
) -> None:
    if not erros:
        return
    if historico.obter_metadado(conn, "ultimo_aviso_erro") == hoje:
        print(f"[info] {len(erros)} erro(s) nesta execucao, mas o aviso de hoje ja foi enviado.")
        return

    mensagem = (
        f"⚠️ *Aviso*\n\n{len(erros)} busca(s) falharam nesta execução. "
        "Ver logs do GitHub Actions para detalhes."
    )
    enviar_mensagem(token, chat_id, mensagem)
    historico.definir_metadado(conn, "ultimo_aviso_erro", hoje)
    print(mensagem)


def _executar_modo_completo(
    config: Config, conn: sqlite3.Connection, token: str, chat_id: str, agora: datetime
) -> tuple[list[str], List[Voo]]:
    todos_os_voos, erros, total_buscas = _buscar_todos_os_voos(config)

    # avaliar ANTES de registrar: as comparacoes precisam ser contra o que ja
    # estava no historico antes desta execucao.
    alertas_disparados = alerta.avaliar(conn, config.alertas, todos_os_voos, agora)
    motivos_por_janela = {
        (item.voo.destino, item.voo.ida, item.voo.volta): item.motivos for item in alertas_disparados
    }

    voos_top = sorted(todos_os_voos, key=lambda v: v.preco)[:TOP_N]
    desde = agora - timedelta(days=alerta.DIAS_MEDIA_RECENTE)
    medias_por_janela = {
        (voo.destino, voo.ida, voo.volta): historico.media_precos_recentes(
            conn, voo.origem, voo.destino, voo.ida, voo.volta, desde
        )
        for voo in voos_top
    }

    historico.registrar_voos(conn, todos_os_voos, timestamp=agora)
    dashboard.gerar_dashboard(conn, config.origem)

    mensagem_detalhe = _formatar_mensagem_detalhe(voos_top, motivos_por_janela, medias_por_janela)
    enviar_mensagem_longa(token, chat_id, mensagem_detalhe)
    print(mensagem_detalhe)

    menor_geral = historico.menor_preco_geral(conn, config.origem)
    mensagem_resumo = _formatar_mensagem_resumo(voos_top, total_buscas, menor_geral, erros)
    enviar_mensagem_longa(token, chat_id, mensagem_resumo)
    print(mensagem_resumo)

    return erros, todos_os_voos


def _executar_modo_rapido(
    config: Config, conn: sqlite3.Connection, token: str, chat_id: str, agora: datetime
) -> list[str]:
    janelas_observadas = historico.janelas_mais_baratas_recentes(conn, config.origem, QUANTIDADE_JANELAS_RAPIDAS)
    if not janelas_observadas:
        print("[info] modo rapido sem historico suficiente ainda (nenhuma execucao completa rodou) -- nada a checar.")
        return []

    todos_os_voos, erros = _buscar_janelas_especificas(config, janelas_observadas)

    alertas_disparados = alerta.avaliar(conn, config.alertas, todos_os_voos, agora)
    historico.registrar_voos(conn, todos_os_voos, timestamp=agora)

    if alertas_disparados:
        mensagem = _formatar_mensagem_alerta_rapido(alertas_disparados)
        enviar_mensagem_longa(token, chat_id, mensagem)
        print(mensagem)
    else:
        print(f"[info] checagem rapida: nenhum alerta disparado ({len(janelas_observadas)} janela(s) verificadas).")

    return erros


def main() -> None:
    config_path = os.environ.get("BOT_PASSAGENS_CONFIG", "config.yaml")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    modo = os.environ.get("MODO_EXECUCAO", "completo").strip().lower()

    if not token or not chat_id:
        raise SystemExit("Defina as variaveis de ambiente TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID antes de rodar.")

    config = carregar_config(config_path)
    agora = datetime.now(timezone.utc)

    historico_path = os.environ.get("BOT_PASSAGENS_HISTORICO", historico.CAMINHO_PADRAO)
    conn = historico.conectar(historico_path)
    try:
        if modo == "rapido":
            erros = _executar_modo_rapido(config, conn, token, chat_id, agora)
        else:
            erros, _ = _executar_modo_completo(config, conn, token, chat_id, agora)

        _avisar_erros_no_maximo_uma_vez_por_dia(conn, token, chat_id, erros, hoje=agora.date().isoformat())
    finally:
        conn.close()


if __name__ == "__main__":
    main()
