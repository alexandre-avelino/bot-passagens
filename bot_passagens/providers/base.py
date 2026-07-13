from abc import ABC, abstractmethod
from datetime import date
from typing import List

from bot_passagens.models import Voo


class ProviderError(Exception):
    """Erro ao consultar um provider de passagens (rate limit, mudanca na fonte, etc.)."""


class FlightProvider(ABC):
    """Interface que qualquer fonte de precos de passagens deve implementar.

    O restante do sistema so conhece esta interface, nunca a origem real dos
    dados -- isso permite trocar ou somar providers (ex.: fast-flights hoje,
    outra fonte amanha) sem tocar em regras de data, alerta ou notificacao.
    """

    @abstractmethod
    def buscar(self, origem: str, destino: str, ida: date, volta: date, passageiros: int = 1) -> List[Voo]:
        """Retorna voos ida+volta normalizados para a rota e datas dadas.

        Deve levantar ProviderError em caso de falha (nunca deixar excecoes
        internas da biblioteca vazarem), para que o chamador decida como
        avisar sobre a falha sem quebrar o restante da execucao.
        """
        raise NotImplementedError
