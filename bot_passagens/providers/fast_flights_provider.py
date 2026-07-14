"""Provider que busca precos reais no Google Voos via a biblioteca fast-flights.

Nao usa nenhuma API key: a biblioteca faz scraping da mesma pagina publica de
resultados que um usuario veria no navegador.

Limitacao conhecida: em buscas ida+volta, o Google Voos (e por consequencia a
fast-flights) expoe o preco total e os detalhes do trecho de ida, mas nao os
horarios/escalas do trecho de volta separadamente. Por isso o modelo `Voo`
guarda `escalas`, `partida` e `chegada` apenas do trecho de ida, junto do
preco total.
"""

from datetime import date
from typing import List, Sequence

import fast_flights as ff

from bot_passagens.models import Voo
from bot_passagens.providers.base import FlightProvider, ProviderError


def _formatar_hora(hora_minuto: Sequence[int]) -> str:
    hora = hora_minuto[0]
    minuto = hora_minuto[1] if len(hora_minuto) > 1 else 0
    return f"{hora:02d}:{minuto:02d}"


class FastFlightsProvider(FlightProvider):
    def buscar(self, origem: str, destino: str, ida: date, volta: date, passageiros: int = 1) -> List[Voo]:
        query = ff.create_query(
            flights=[
                ff.FlightQuery(date=ida.isoformat(), from_airport=origem, to_airport=destino),
                ff.FlightQuery(date=volta.isoformat(), from_airport=destino, to_airport=origem),
            ],
            trip="round-trip",
            seat="economy",
            passengers=ff.Passengers(adults=passageiros),
            currency="BRL",
        )

        try:
            resultados = ff.get_flights(query)
        except ff.FlightsNotFound:
            return []
        except Exception as erro:
            # fast-flights faz scraping de HTML: rate limit, mudanca de layout do
            # Google ou instabilidade de rede podem quebrar de formas variadas.
            # Nunca deixamos isso vazar cru -- o chamador decide como avisar.
            raise ProviderError(
                f"falha ao consultar fast-flights para {origem}-{destino} ({ida} / {volta}): {erro}"
            ) from erro

        link = query.url()
        voos: List[Voo] = []
        for resultado in resultados:
            escalas = max(len(resultado.flights) - 1, 0)
            companhia = ", ".join(dict.fromkeys(resultado.airlines)) or resultado.type
            partida = _formatar_hora(resultado.flights[0].departure.time)
            chegada = _formatar_hora(resultado.flights[-1].arrival.time)
            voos.append(
                Voo(
                    origem=origem,
                    destino=destino,
                    ida=ida,
                    volta=volta,
                    companhia=companhia,
                    preco=float(resultado.price),
                    escalas=escalas,
                    partida=partida,
                    chegada=chegada,
                    link=link,
                )
            )
        return voos
