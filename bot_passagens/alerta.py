"""Camada de regras de alerta.

Compara o preco desta execucao com o historico ja registrado e decide quais
janelas merecem um alerta imediato no Telegram. Roda ANTES de gravar os
resultados desta execucao no historico, para que as comparacoes reflitam
sempre "o que ja sabiamos antes de agora".
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from bot_passagens import historico
from bot_passagens.config import Alertas
from bot_passagens.formatacao import formatar_preco
from bot_passagens.models import Voo

DIAS_MEDIA_RECENTE = 30


@dataclass(frozen=True)
class Alerta:
    voo: Voo
    motivos: List[str]
    media_recente: Optional[float]


def avaliar(conn: sqlite3.Connection, config_alertas: Alertas, todos_os_voos: List[Voo], agora: datetime) -> List[Alerta]:
    grupos: Dict[Tuple[str, str, object, object], List[Voo]] = {}
    for voo in todos_os_voos:
        chave = (voo.origem, voo.destino, voo.ida, voo.volta)
        grupos.setdefault(chave, []).append(voo)

    desde = agora - timedelta(days=DIAS_MEDIA_RECENTE)
    alertas: List[Alerta] = []

    for (origem, destino, ida, volta), voos_da_janela in grupos.items():
        mais_barato = min(voos_da_janela, key=lambda v: v.preco)
        motivos: List[str] = []

        if mais_barato.preco <= config_alertas.preco_maximo:
            motivos.append(f"Abaixo do teto configurado ({formatar_preco(config_alertas.preco_maximo)})")

        preco_anterior = historico.ultima_leitura_janela(conn, origem, destino, ida, volta)
        if preco_anterior is not None and preco_anterior > 0:
            queda_pct = (preco_anterior - mais_barato.preco) / preco_anterior * 100
            if queda_pct >= config_alertas.queda_percentual:
                motivos.append(f"Caiu {queda_pct:.0f}% desde a última checagem (estava {formatar_preco(preco_anterior)})")

        if config_alertas.novo_menor_preco:
            menor_ja_visto = historico.menor_preco_janela(conn, origem, destino, ida, volta)
            # so conta como "recorde" se ja existia algo pra bater -- a primeira
            # vez que vemos uma janela nao e um recorde, e so o ponto de partida.
            if menor_ja_visto is not None and mais_barato.preco < menor_ja_visto:
                motivos.append("Novo menor preço já visto para essa janela")

        if motivos:
            media_recente = historico.media_precos_recentes(conn, origem, destino, ida, volta, desde)
            alertas.append(Alerta(voo=mais_barato, motivos=motivos, media_recente=media_recente))

    return alertas
