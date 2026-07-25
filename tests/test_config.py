from datetime import date

import pytest

from bot_passagens.config import carregar_config

CONFIG_BASE = """
origem: CGB
destinos:
  - GRU
periodo:
  inicio: 2026-11-09
  fim: 2026-11-30
dias_obrigatorios: {dias_obrigatorios}
margem_adjacente: 1
duracao:
  minima: 5
  maxima: 7
passageiros: 1
alertas:
  preco_maximo: 500
  queda_percentual: 10
  novo_menor_preco: true
resumo_diario: "08:00"
"""


def test_dias_obrigatorios_vazio_e_aceito(tmp_path):
    caminho = tmp_path / "config.yaml"
    caminho.write_text(CONFIG_BASE.format(dias_obrigatorios="[]"), encoding="utf-8")

    config = carregar_config(str(caminho))
    assert config.dias_obrigatorios == []


def test_dias_obrigatorios_com_data_ainda_funciona(tmp_path):
    caminho = tmp_path / "config.yaml"
    caminho.write_text(CONFIG_BASE.format(dias_obrigatorios="[2026-11-15]"), encoding="utf-8")

    config = carregar_config(str(caminho))
    assert config.dias_obrigatorios == [date(2026, 11, 15)]


def test_destinos_vazio_leva_a_erro(tmp_path):
    caminho = tmp_path / "config.yaml"
    caminho.write_text(CONFIG_BASE.format(dias_obrigatorios="[]").replace("  - GRU", ""), encoding="utf-8")

    with pytest.raises(ValueError):
        carregar_config(str(caminho))
