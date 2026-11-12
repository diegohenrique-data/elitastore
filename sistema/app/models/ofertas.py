"""OFERTAS (kit / carrinho de ofertas): a Elita junta produtos, de preferência os PARADOS há muito
tempo no estoque, dá um desconto (preço do kit ou %) e manda para a cliente no WhatsApp.
A oferta não fica guardada no banco: vai no endereço da tela (prod=...), igual à cesta do
"Mandar o que tenho". Para vender, o botão VENDER ESTE KIT abre a Nova venda com o carrinho pronto."""

from decimal import Decimal, ROUND_HALF_UP

from ..core import util
from . import produtos

MAX_OFERTA = 20  # produtos num kit


def parados(db, cfg: dict) -> list[dict]:
    """Os produtos parados (sem vender há muito tempo), do mais parado para o menos, com 'dias':
    há quantos dias não vende (desde a última venda, ou desde que chegou se nunca vendeu)."""
    lista = produtos.avisos_estoque(db, cfg)["parados"]
    if not lista:
        return []
    ids = [p["id"] for p in lista]
    ultima: dict = {}
    vendas = (db.table("venda_itens").select("produto_id, vendas!inner(vendida_em)")
              .in_("produto_id", ids[:300]).execute().data)
    for v in vendas:
        dia = util.para_data(v["vendas"]["vendida_em"][:10])
        if dia > ultima.get(v["produto_id"], dia.min):
            ultima[v["produto_id"]] = dia
    hoje = util.hoje()
    for p in lista:
        desde = max(util.para_data(p["entrou_em"]), ultima.get(p["id"], util.para_data(p["entrou_em"])))
        p["dias"] = (hoje - desde).days
    return sorted(lista, key=lambda p: -p["dias"])


def calcular(itens: list[dict], tipo: str, valor: Decimal | None) -> dict | str:
    """O preço da oferta. tipo 'kit' = 'valor' é o preço do kit todo; 'pct' = 'valor' % de desconto.
    Devolve {de, por, economia, pct} ou a mensagem de erro."""
    de = sum((Decimal(str(p["preco"])) for p in itens), Decimal(0)).quantize(util.CENTAVO)
    if valor is None or valor <= 0:
        return "Escreva o preço do kit." if tipo == "kit" else "Escreva quantos % de desconto. Ex.: 20"
    if tipo == "pct":
        if valor >= 100:
            return "O desconto precisa ser menor que 100%."
        por = (de * (100 - valor) / 100).quantize(util.CENTAVO, ROUND_HALF_UP)
    else:
        por = valor.quantize(util.CENTAVO)
        if por >= de:
            return f"O preço do kit precisa ser menor que {util.reais(de)} (a soma dos produtos)."
    economia = de - por
    pct = int((economia * 100 / de).quantize(Decimal(1), ROUND_HALF_UP)) if de else 0
    return {"de": de, "por": por, "economia": economia, "pct": pct}


def mensagem(loja: str, nome: str, itens: list[dict], conta: dict, ate: str = "") -> str:
    """O texto da oferta para o WhatsApp (o ~ risca o preço antigo no WhatsApp)."""
    linhas = [f"🎁 *{nome or 'Oferta especial'}* · {loja}", ""]
    linhas += [f"• {p['nome']}: ~{util.reais(p['preco'])}~" for p in itens]
    linhas += ["", f"De ~{util.reais(conta['de'])}~ por *{util.reais(conta['por'])}*",
               f"Você economiza {util.reais(conta['economia'])} ({conta['pct']}% de desconto) 🤩"]
    if ate:
        linhas += ["", f"⏰ Só até {util.data_completa(ate)}!"]
    linhas += ["", "Quer que eu separe para você? 😊"]
    return "\n".join(linhas)
