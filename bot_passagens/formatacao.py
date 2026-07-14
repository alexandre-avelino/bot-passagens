"""Formatacao de valores para exibicao nas mensagens do Telegram."""


def formatar_preco(valor: float) -> str:
    texto = f"{valor:,.2f}"
    parte_inteira, parte_decimal = texto.split(".")
    parte_inteira = parte_inteira.replace(",", ".")
    return f"R$ {parte_inteira},{parte_decimal}"
