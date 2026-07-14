from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Voo:
    """Um resultado de busca ida+volta, ja normalizado, vindo de qualquer provider.

    preco e sempre o valor total ida+volta. escalas, partida e chegada se
    referem ao trecho de ida (e a informacao que as fontes gratuitas
    atualmente disponibilizam de forma confiavel para buscas ida+volta).
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
