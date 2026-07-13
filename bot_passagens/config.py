"""Leitura e validacao do config.yaml."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List

import yaml


@dataclass(frozen=True)
class Alertas:
    preco_maximo: float
    queda_percentual: float
    novo_menor_preco: bool


@dataclass(frozen=True)
class Duracao:
    minima: int
    maxima: int


@dataclass(frozen=True)
class Config:
    origem: str
    destinos: List[str]
    periodo_inicio: date
    periodo_fim: date
    dias_obrigatorios: List[date]
    margem_adjacente: int
    duracao: Duracao
    passageiros: int
    alertas: Alertas
    resumo_diario: str


def carregar_config(caminho: str = "config.yaml") -> Config:
    dados = yaml.safe_load(Path(caminho).read_text(encoding="utf-8"))

    campos_obrigatorios = [
        "origem",
        "destinos",
        "periodo",
        "dias_obrigatorios",
        "margem_adjacente",
        "duracao",
        "passageiros",
        "alertas",
        "resumo_diario",
    ]
    faltando = [campo for campo in campos_obrigatorios if campo not in dados]
    if faltando:
        raise ValueError(f"config.yaml esta faltando os campos: {', '.join(faltando)}")

    if not dados["destinos"]:
        raise ValueError("config.yaml precisa de pelo menos um destino em 'destinos'")

    if not dados["dias_obrigatorios"]:
        raise ValueError("config.yaml precisa de pelo menos um dia em 'dias_obrigatorios'")

    duracao = Duracao(
        minima=int(dados["duracao"]["minima"]),
        maxima=int(dados["duracao"]["maxima"]),
    )
    if duracao.minima > duracao.maxima:
        raise ValueError("duracao.minima nao pode ser maior que duracao.maxima")

    alertas = Alertas(
        preco_maximo=float(dados["alertas"]["preco_maximo"]),
        queda_percentual=float(dados["alertas"]["queda_percentual"]),
        novo_menor_preco=bool(dados["alertas"]["novo_menor_preco"]),
    )

    return Config(
        origem=str(dados["origem"]).upper(),
        destinos=[str(d).upper() for d in dados["destinos"]],
        periodo_inicio=dados["periodo"]["inicio"],
        periodo_fim=dados["periodo"]["fim"],
        dias_obrigatorios=list(dados["dias_obrigatorios"]),
        margem_adjacente=int(dados["margem_adjacente"]),
        duracao=duracao,
        passageiros=int(dados["passageiros"]),
        alertas=alertas,
        resumo_diario=str(dados["resumo_diario"]),
    )
