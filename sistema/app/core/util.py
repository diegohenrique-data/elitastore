"""Contas e formatos do dia a dia: reais, datas, parcelas e WhatsApp."""

import calendar
import re
import unicodedata
import urllib.parse
from datetime import date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from ..config import FUSO

DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]
CENTAVO = Decimal("0.01")


def hoje() -> date:
    return datetime.now(ZoneInfo(FUSO)).date()


def agora() -> datetime:
    return datetime.now(ZoneInfo(FUSO))


def reais(valor) -> str:
    """1234.5 -> 'R$ 1.234,50'"""
    try:
        v = Decimal(str(valor or 0)).quantize(CENTAVO)
    except InvalidOperation:
        v = Decimal(0)
    sinal = "-" if v < 0 else ""
    inteiro, centavos = f"{abs(v):.2f}".split(".")
    inteiro = f"{int(inteiro):,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{centavos}"


def ler_reais(texto: str | None) -> Decimal | None:
    """Aceita '33,50', '1.234,50', '33.5', 'R$ 10'. Devolve None se não der para ler."""
    if texto is None:
        return None
    t = texto.replace("R$", "").replace(" ", "").strip()
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        v = Decimal(t).quantize(CENTAVO)
    except InvalidOperation:
        return None
    return v


def para_data(valor) -> date | None:
    if not valor:
        return None
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


def data_curta(valor) -> str:
    """'2026-10-16' -> 'sexta, 16/10'"""
    d = para_data(valor)
    if not d:
        return ""
    return f"{DIAS_SEMANA[d.weekday()]}, {d:%d/%m}"


def data_completa(valor) -> str:
    d = para_data(valor)
    if not d:
        return ""
    return f"{d:%d/%m/%Y}"


def data_com_ano(valor) -> str:
    """Data curta, com o ano quando não é deste ano: 'sexta, 16/10' ou 'sábado, 10/05/2025'."""
    d = para_data(valor)
    if not d:
        return ""
    return data_curta(d) if d.year == hoje().year else f"{DIAS_SEMANA[d.weekday()]}, {d:%d/%m/%Y}"


def data_extenso(valor=None) -> str:
    """-> 'sexta-feira, 16 de outubro'"""
    d = para_data(valor) or hoje()
    dia_semana = DIAS_SEMANA[d.weekday()]
    if d.weekday() < 5:
        dia_semana += "-feira"
    return f"{dia_semana}, {d.day} de {MESES[d.month - 1]}"


def mes_atual() -> str:
    return MESES[hoje().month - 1]


def dividir_parcelas(total: Decimal, vezes: int) -> list[Decimal]:
    """R$ 100 em 3 vezes -> [33,34; 33,33; 33,33] (a sobra vai na 1ª)."""
    base = (total / vezes).quantize(CENTAVO, rounding=ROUND_DOWN)
    valores = [base] * vezes
    valores[0] += total - base * vezes
    return valores


def _no_dia(ano: int, mes: int, dia: int) -> date:
    ultimo = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(dia, ultimo))


def datas_parcelas(vezes: int, dia: int, a_partir: date, dia2: int | None = None) -> list[date]:
    """Primeira parcela no próximo 'dia' depois de hoje; as outras, mês a mês.
    Com 'dia2' (paga 2 vezes no mês, ex.: dia 5 e dia 15), as parcelas
    vão alternando entre os dois dias, sempre na próxima data que vier."""
    dias = sorted({dia, dia2}) if dia2 else [dia]
    ano, mes = a_partir.year, a_partir.month
    datas = []
    while len(datas) < vezes:
        for d in dias:
            data = _no_dia(ano, mes, d)
            if data > a_partir and data not in datas and len(datas) < vezes:
                datas.append(data)
        mes += 1
        if mes > 12:
            mes, ano = 1, ano + 1
    return datas


def so_numeros(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def link_whatsapp(telefone: str | None, mensagem: str) -> str:
    """Abre o WhatsApp da Elita com o texto pronto. Coloca o 55 do Brasil se faltar."""
    numero = so_numeros(telefone)
    if numero and not numero.startswith("55") and len(numero) in (10, 11):
        numero = "55" + numero
    # Endereço direto do WhatsApp: o atalho wa.me estraga alguns emojis (ex.: 🛍️ vira "�").
    texto = urllib.parse.quote(mensagem, safe="")
    if numero:
        return f"https://api.whatsapp.com/send?phone={numero}&text={texto}"
    return f"https://api.whatsapp.com/send?text={texto}"


def preencher(modelo: str, **valores) -> str:
    """'Oi {nome}' + nome='Maria' -> 'Oi Maria' (o que faltar fica em branco)."""
    def troca(m):
        return str(valores.get(m.group(1), ""))
    return re.sub(r"\{(\w+)\}", troca, modelo or "")


def primeiro_nome(nome: str | None) -> str:
    return (nome or "").strip().split(" ")[0]


def inicio_do_mes(d: date | None = None) -> date:
    d = d or hoje()
    return d.replace(day=1)


def fim_do_mes(d: date | None = None) -> date:
    d = d or hoje()
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def dias_atras(n: int) -> date:
    return hoje() - timedelta(days=n)


def nome_de_arquivo(texto: str | None) -> str:
    """'Perfume Asad Lattafa 100ml' -> 'perfume-asad-lattafa-100ml' (sem acento, para nome de foto)."""
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")[:60] or "foto"
