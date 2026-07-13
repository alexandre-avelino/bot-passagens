from datetime import date

import pytest

from bot_passagens.dates import Janela, gerar_combinacoes


def test_combinacoes_do_config_padrao_cobrem_regra():
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
        assert janela.ida <= date(2026, 10, 6) <= janela.volta
        # cobre pelo menos um dia adjacente ao 06/10
        assert (janela.ida <= date(2026, 10, 5)) or (janela.volta >= date(2026, 10, 7))


def test_janela_minima_valida_5_a_9_de_outubro():
    combinacoes = gerar_combinacoes(
        periodo_inicio=date(2026, 9, 29),
        periodo_fim=date(2026, 10, 13),
        dias_obrigatorios=[date(2026, 10, 6)],
        margem_adjacente=1,
        duracao_minima=4,
        duracao_maxima=7,
    )
    assert Janela(ida=date(2026, 10, 5), volta=date(2026, 10, 9)) in combinacoes
    assert Janela(ida=date(2026, 10, 6), volta=date(2026, 10, 10)) in combinacoes


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


def test_janela_que_cobre_dia_obrigatorio_sem_folga_adjacente_e_excluida():
    # ida e volta no mesmo dia obrigatorio (duracao 0) nunca aparece pois fere duracao minima,
    # mas testamos diretamente a regra de adjacencia com margem_adjacente=1 e uma janela contigua
    # que so toca o dia obrigatorio na borda sem sobra de nenhum lado dentro do periodo.
    combinacoes = gerar_combinacoes(
        periodo_inicio=date(2026, 10, 6),
        periodo_fim=date(2026, 10, 9),
        dias_obrigatorios=[date(2026, 10, 6)],
        margem_adjacente=1,
        duracao_minima=1,
        duracao_maxima=1,
    )
    # unica janela possivel: 06 -> 07, que cobre o dia obrigatorio (06) e o adjacente (07)
    assert combinacoes == [Janela(ida=date(2026, 10, 6), volta=date(2026, 10, 7))]


def test_margem_adjacente_zero_so_exige_o_dia_obrigatorio():
    combinacoes = gerar_combinacoes(
        periodo_inicio=date(2026, 10, 6),
        periodo_fim=date(2026, 10, 9),
        dias_obrigatorios=[date(2026, 10, 6)],
        margem_adjacente=0,
        duracao_minima=0,
        duracao_maxima=0,
    )
    assert combinacoes == [Janela(ida=date(2026, 10, 6), volta=date(2026, 10, 6))]


def test_multiplos_dias_obrigatorios_precisam_ser_todos_cobertos():
    combinacoes = gerar_combinacoes(
        periodo_inicio=date(2026, 10, 1),
        periodo_fim=date(2026, 10, 15),
        dias_obrigatorios=[date(2026, 10, 6), date(2026, 10, 12)],
        margem_adjacente=1,
        duracao_minima=4,
        duracao_maxima=7,
    )
    for janela in combinacoes:
        assert janela.ida <= date(2026, 10, 6) <= janela.volta
        assert janela.ida <= date(2026, 10, 12) <= janela.volta


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
