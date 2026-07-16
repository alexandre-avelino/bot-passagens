from datetime import datetime

from bot_passagens.main import FUSO_HORARIO_LOCAL, _e_execucao_do_resumo_diario


def _hora_local(hora: int) -> datetime:
    return datetime(2026, 10, 1, hora, 5, tzinfo=FUSO_HORARIO_LOCAL)


def test_execucao_as_8h_e_resumo_diario():
    assert _e_execucao_do_resumo_diario(_hora_local(8)) is True


def test_execucao_atrasada_ate_as_11h_ainda_conta_como_resumo():
    assert _e_execucao_do_resumo_diario(_hora_local(10)) is True
    assert _e_execucao_do_resumo_diario(_hora_local(11)) is True


def test_execucao_as_20h_nao_e_resumo_diario():
    assert _e_execucao_do_resumo_diario(_hora_local(20)) is False


def test_execucao_de_madrugada_nao_e_resumo_diario():
    assert _e_execucao_do_resumo_diario(_hora_local(2)) is False
    assert _e_execucao_do_resumo_diario(_hora_local(5)) is False


def test_execucao_ao_meio_dia_nao_e_resumo_diario():
    assert _e_execucao_do_resumo_diario(_hora_local(12)) is False
