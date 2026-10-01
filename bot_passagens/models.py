from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Voo:
    """Um resultado de busca normalizado, vindo de qualquer provider.

    Em viagem somente de ida, ``volta`` repete ``ida`` para manter
    compatibilidade com o historico SQLite existente.
    partida/chegada sao horarios locais no formato "HH:MM".
    """

    origem: str
    destino: str
    ida: date
    volta: date
    companhia: str
    preco: float
    escalas: int
    partida: str
    chegada: str
    link: str
