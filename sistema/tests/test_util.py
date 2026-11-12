from datetime import date
from decimal import Decimal

from app.core import util


def test_reais():
    assert util.reais(1234.5) == "R$ 1.234,50"
    assert util.reais("33.34") == "R$ 33,34"
    assert util.reais(None) == "R$ 0,00"
    assert util.reais(-5) == "-R$ 5,00"


def test_ler_reais():
    assert util.ler_reais("33,50") == Decimal("33.50")
    assert util.ler_reais("1.234,50") == Decimal("1234.50")
    assert util.ler_reais("R$ 10") == Decimal("10.00")
    assert util.ler_reais("33.5") == Decimal("33.50")
    assert util.ler_reais("") is None
    assert util.ler_reais("abc") is None


def test_dividir_parcelas_como_no_documento():
    # "3 vezes de R$ 33,34" para R$ 100
    assert util.dividir_parcelas(Decimal(100), 3) == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]
    assert sum(util.dividir_parcelas(Decimal("89.90"), 4)) == Decimal("89.90")


def test_datas_parcelas():
    # hoje 16/10, paga dia 10 -> começa em novembro
    assert util.datas_parcelas(3, 10, date(2026, 10, 16)) == [date(2026, 11, 10), date(2026, 12, 10), date(2027, 1, 10)]
    # paga dia 20 -> ainda dá neste mês
    assert util.datas_parcelas(1, 20, date(2026, 10, 16)) == [date(2026, 10, 20)]
    # dia 31 em fevereiro vira o último dia do mês
    assert util.datas_parcelas(2, 31, date(2027, 1, 31)) == [date(2027, 2, 28), date(2027, 3, 31)]
    # paga 2 vezes no mês (dia 5 e dia 15): hoje 10/10 -> 15/10, 05/11, 15/11, 05/12
    assert util.datas_parcelas(4, 5, date(2026, 10, 10), 15) == [
        date(2026, 10, 15), date(2026, 11, 5), date(2026, 11, 15), date(2026, 12, 5)]
    # a ordem dos dias não importa; dia 30 em fevereiro vira 28 (sem repetir data)
    assert util.datas_parcelas(3, 30, date(2027, 1, 31), 14) == [date(2027, 2, 14), date(2027, 2, 28), date(2027, 3, 14)]


def test_whatsapp_coloca_55():
    link = util.link_whatsapp("(11) 99999-8888", "Oi Maria")
    assert link == "https://api.whatsapp.com/send?phone=5511999998888&text=Oi%20Maria"
    assert util.link_whatsapp("", "Oi").startswith("https://api.whatsapp.com/send?text=")
    # emoji vai inteiro (UTF-8), sem virar "�"
    assert "%F0%9F%9B%8D%EF%B8%8F" in util.link_whatsapp("", "🛍️ Loja")


def test_preencher_mensagem():
    msg = util.preencher("Oi {nome}, parcela de {valor}. Pix {pix}", nome="Maria", valor="R$ 50,00", pix="123")
    assert msg == "Oi Maria, parcela de R$ 50,00. Pix 123"


def test_data_curta():
    assert util.data_curta("2026-10-16") == "sexta, 16/10"
    assert util.data_extenso("2026-10-16") == "sexta-feira, 16 de outubro"
    assert util.data_extenso("2026-10-17") == "sábado, 17 de outubro"


def test_nome_de_arquivo_da_foto():
    assert util.nome_de_arquivo("Perfume Árabe Asad 100ml!") == "perfume-arabe-asad-100ml"
    assert util.nome_de_arquivo("") == "foto" and util.nome_de_arquivo(None) == "foto"
