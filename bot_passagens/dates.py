"""Gerador de combinacoes (ida, volta) validas para a viagem monitorada.

Regra central do projeto: a janela [ida, volta] precisa cobrir cada dia
obrigatorio configurado E pelo menos um dia adjacente a ele (antes ou depois,
dentro da margem configurada). Isso evita, por exemplo, uma viagem que pousa
e decola no mesmo dia obrigatorio sem nenhuma folga ao redor.
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
    if not (ida <= dia_obrigatorio <= volta):
        return False
    if margem_adjacente <= 0:
        return True
    for deslocamento in range(1, margem_adjacente + 1):
        vizinho_antes = dia_obrigatorio - timedelta(days=deslocamento)
        vizinho_depois = dia_obrigatorio + timedelta(days=deslocamento)
        if (ida <= vizinho_antes <= volta) or (ida <= vizinho_depois <= volta):
            return True
    return False


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
    - cobrem TODOS os dias em dias_obrigatorios, cada um com pelo menos um
      dia adjacente dentro de margem_adjacente.
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
