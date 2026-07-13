from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Voo:
    """Um resultado de busca ida+volta, ja normalizado, vindo de qualquer provider.

    preco e sempre o valor total ida+volta. escalas se refere ao trecho de ida
    (e a informacao que as fontes gratuitas atualmente disponibilizam de forma
    confiavel para buscas ida+volta).
    """

    origem: str
    destino: str
    ida: date
    volta: date
    companhia: str
    preco: float
    escalas: int
    link: str
