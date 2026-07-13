from datetime import date

import pytest

from bot_passagens.dates import Janela, gerar_combinacoes


def test_combinacoes_do_config_padrao_nunca_tem_dia_obrigatorio_na_borda():
    combinacoes = gerar_combinacoes(
        periodo_inicio=date(2026, 9, 29),
        periodo_fim=date(2026, 10, 13),
        dias_obrigatorios=[date(2026, 10, 6)],
        margem_adjacente=1,
        duracao_minima=4,
        duracao_maxima=7,
    )

    assert len(combinacoes) > 0
    for janela in combinacoes:
        assert 4 <= janela.duracao <= 7
        # dia 06/10 tem que ser dia inteiro no destino: nunca dia de ida ou de volta
        assert janela.ida < date(2026, 10, 6) < janela.volta


def test_janela_5_a_9_de_outubro_e_valida():
    combinacoes = gerar_combinacoes(
        periodo_inicio=date(2026, 9, 29),
        periodo_fim=date(2026, 10, 13),
        dias_obrigatorios=[date(2026, 10, 6)],
        margem_adjacente=1,
        duracao_minima=4,
        duracao_maxima=7,
    )
    assert Janela(ida=date(2026, 10, 5), volta=date(2026, 10, 9)) in combinacoes


def test_janela_com_ida_no_dia_obrigatorio_e_excluida():
    combinacoes = gerar_combinacoes(
        periodo_inicio=date(2026, 9, 29),
        periodo_fim=date(2026, 10, 13),
        dias_obrigatorios=[date(2026, 10, 6)],
        margem_adjacente=1,
        duracao_minima=4,
        duracao_maxima=7,
    )
    # ida no proprio dia 06 -> nao serve, o dia obrigatorio seria dia de embarque
    assert Janela(ida=date(2026, 10, 6), volta=date(2026, 10, 10)) not in combinacoes


def test_janela_com_volta_no_dia_obrigatorio_e_excluida():
    combinacoes = gerar_combinacoes(
        periodo_inicio=date(2026, 9, 29),
        periodo_fim=date(2026, 10, 13),
        dias_obrigatorios=[date(2026, 10, 6)],
        margem_adjacente=1,
        duracao_minima=4,
        duracao_maxima=7,
    )
    # volta no proprio dia 06 -> nao serve, o dia obrigatorio seria dia de desembarque
    assert Janela(ida=date(2026, 10, 2), volta=date(2026, 10, 6)) not in combinacoes


def test_janela_que_nao_cobre_dia_obrigatorio_e_excluida():
    combinacoes = gerar_combinacoes(
        periodo_inicio=date(2026, 9, 29),
        periodo_fim=date(2026, 10, 13),
        dias_obrigatorios=[date(2026, 10, 6)],
        margem_adjacente=1,
        duracao_minima=4,
        duracao_maxima=7,
    )
    assert Janela(ida=date(2026, 9, 29), volta=date(2026, 10, 3)) not in combinacoes


def test_margem_adjacente_zero_permite_dia_obrigatorio_na_borda():
    combinacoes = gerar_combinacoes(
        periodo_inicio=date(2026, 10, 6),
        periodo_fim=date(2026, 10, 6),
        dias_obrigatorios=[date(2026, 10, 6)],
        margem_adjacente=0,
        duracao_minima=0,
        duracao_maxima=0,
    )
    assert combinacoes == [Janela(ida=date(2026, 10, 6), volta=date(2026, 10, 6))]


def test_margem_adjacente_maior_exige_mais_folga_dos_dois_lados():
    combinacoes = gerar_combinacoes(
        periodo_inicio=date(2026, 10, 1),
        periodo_fim=date(2026, 10, 13),
        dias_obrigatorios=[date(2026, 10, 6)],
        margem_adjacente=2,
        duracao_minima=4,
        duracao_maxima=7,
    )
    for janela in combinacoes:
        assert janela.ida <= date(2026, 10, 4)
        assert janela.volta >= date(2026, 10, 8)
    assert Janela(ida=date(2026, 10, 5), volta=date(2026, 10, 9)) not in combinacoes
    assert Janela(ida=date(2026, 10, 4), volta=date(2026, 10, 8)) in combinacoes


def test_multiplos_dias_obrigatorios_precisam_ser_todos_cobertos():
    combinacoes = gerar_combinacoes(
        periodo_inicio=date(2026, 10, 1),
        periodo_fim=date(2026, 10, 15),
        dias_obrigatorios=[date(2026, 10, 6), date(2026, 10, 8)],
        margem_adjacente=1,
        duracao_minima=4,
        duracao_maxima=8,
    )
    assert len(combinacoes) > 0
    for janela in combinacoes:
        assert janela.ida < date(2026, 10, 6) < janela.volta
        assert janela.ida < date(2026, 10, 8) < janela.volta


def test_duracao_minima_maior_que_maxima_leva_a_erro():
    with pytest.raises(ValueError):
        gerar_combinacoes(
            periodo_inicio=date(2026, 10, 1),
            periodo_fim=date(2026, 10, 15),
            dias_obrigatorios=[date(2026, 10, 6)],
            margem_adjacente=1,
            duracao_minima=7,
            duracao_maxima=4,
        )


def test_periodo_invertido_leva_a_erro():
    with pytest.raises(ValueError):
        gerar_combinacoes(
            periodo_inicio=date(2026, 10, 15),
            periodo_fim=date(2026, 10, 1),
            dias_obrigatorios=[date(2026, 10, 6)],
            margem_adjacente=1,
            duracao_minima=4,
            duracao_maxima=7,
        )
