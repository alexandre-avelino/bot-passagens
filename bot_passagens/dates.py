"""Gerador de combinacoes (ida, volta) validas para a viagem monitorada.

Regra central do projeto: cada dia obrigatorio configurado precisa ser um dia
inteiro no destino, nunca o dia de embarque ou desembarque. Ou seja, a janela
[ida, volta] precisa ter o dia obrigatorio estritamente no meio, com pelo
menos `margem_adjacente` dias de folga tanto antes quanto depois dele. Isso
evita, por exemplo, uma viagem que pousa ou decola no dia que precisa
obrigatoriamente ser passado no destino.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List


@dataclass(frozen=True)
class Janela:
    ida: date
    volta: date

    @property
    def duracao(self) -> int:
        return (self.volta - self.ida).days


def _cobre_dia_obrigatorio(ida: date, volta: date, dia_obrigatorio: date, margem_adjacente: int) -> bool:
    folga = timedelta(days=margem_adjacente)
    return ida <= dia_obrigatorio - folga and volta >= dia_obrigatorio + folga


def gerar_combinacoes(
    periodo_inicio: date,
    periodo_fim: date,
    dias_obrigatorios: List[date],
    margem_adjacente: int,
    duracao_minima: int,
    duracao_maxima: int,
) -> List[Janela]:
    """Retorna todas as janelas (ida, volta) dentro do periodo monitorado que:

    - tem duracao entre duracao_minima e duracao_maxima (inclusive);
    - tem TODOS os dias em dias_obrigatorios estritamente no meio da janela
      (nunca no dia de ida ou de volta), com pelo menos margem_adjacente dias
      de folga antes e depois de cada um.
    """
    if duracao_minima > duracao_maxima:
        raise ValueError("duracao_minima nao pode ser maior que duracao_maxima")
    if periodo_inicio > periodo_fim:
        raise ValueError("periodo_inicio nao pode ser depois de periodo_fim")

    combinacoes: List[Janela] = []
    dia_ida = periodo_inicio
    while dia_ida <= periodo_fim:
        for duracao in range(duracao_minima, duracao_maxima + 1):
            dia_volta = dia_ida + timedelta(days=duracao)
            if dia_volta > periodo_fim:
                continue
            if all(
                _cobre_dia_obrigatorio(dia_ida, dia_volta, obrigatorio, margem_adjacente)
                for obrigatorio in dias_obrigatorios
            ):
                combinacoes.append(Janela(ida=dia_ida, volta=dia_volta))
        dia_ida += timedelta(days=1)

    return combinacoes
