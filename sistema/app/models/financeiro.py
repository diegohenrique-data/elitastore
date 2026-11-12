"""Meu dinheiro (só a Elita): o resumo do mês e os gastos."""

import math
from decimal import Decimal

from ..core import util
from . import clientes, vendas


def _soma(linhas, campo) -> Decimal:
    return sum((Decimal(str(x[campo] or 0)) for x in linhas), Decimal(0))


def resumo_do_mes(db) -> dict:
    """Entrou, fiado, vai entrar, gastei, vendi e quanto tenho em mercadoria (pelo custo)."""
    ini, fim = util.inicio_do_mes(), util.fim_do_mes()
    ini_ts, fim_ts = f"{ini.isoformat()}T00:00:00-03:00", f"{fim.isoformat()}T23:59:59-03:00"
    pagos = (db.table("pagamentos").select("valor")
             .gte("pago_em", ini.isoformat()).lte("pago_em", fim.isoformat()).execute().data)
    do_mes = vendas.do_periodo(db, ini_ts, fim_ts)
    na_hora = _soma([v for v in do_mes if v["forma_pagamento"] != "fiado"], "total")
    no_fiado = _soma([v for v in do_mes if v["forma_pagamento"] == "fiado"], "total")
    saldos = clientes.devendo(db, "falta_total, atrasado")
    vai_entrar = (db.table("parcelas_situacao").select("falta").neq("situacao", "paga")
                  .gte("vencimento", util.hoje().isoformat()).lte("vencimento", fim.isoformat()).execute().data)
    gastos = gastos_do_periodo(db, ini.isoformat(), fim.isoformat())
    custos = db.table("produtos_custo").select("preco_custo, produtos(quantidade, ativo)").execute().data
    mercadoria = sum((Decimal(str(c["preco_custo"])) * (c["produtos"] or {}).get("quantidade", 0)
                      for c in custos if (c["produtos"] or {}).get("ativo")), Decimal(0))
    return {
        "mes": util.mes_atual(),
        "entrou": _soma(pagos, "valor") + na_hora, "fiado": _soma(saldos, "falta_total"),
        "atrasado": _soma(saldos, "atrasado"), "pessoas_devendo": len(saldos), "vai_entrar": _soma(vai_entrar, "falta"),
        "gastei": _soma(gastos, "valor"), "vendi": na_hora + no_fiado, "na_hora": na_hora,
        "no_fiado": no_fiado, "mercadoria": mercadoria, "gastos": gastos,
        "lucro": lucro_do_mes(db, gastei=_soma(gastos, "valor")),
    }


def dividas(db) -> dict:
    """DÍVIDAS: tudo o que as pessoas me devem (o fiado que falta), da maior dívida para a menor."""
    pessoas = sorted(clientes.devendo(db), key=lambda p: -Decimal(str(p["falta_total"])))
    return {"pessoas": pessoas, "total": _soma(pessoas, "falta_total"), "atrasado": _soma(pessoas, "atrasado"),
            "atrasadas": sum(1 for p in pessoas if Decimal(str(p["atrasado"])) > 0)}


def gastos_do_periodo(db, inicio: str, fim: str) -> list[dict]:
    return (db.table("gastos").select("*").gte("gasto_em", inicio).lte("gasto_em", fim)
            .order("gasto_em", desc=True).execute().data)


def anotar_gasto(db, valor: Decimal, descricao: str, dia) -> None:
    db.table("gastos").insert({
        "valor": str(valor), "descricao": descricao.strip(), "gasto_em": dia.isoformat(),
    }).execute()


def apagar_gasto(db, gid: str) -> bool:
    return bool(db.table("gastos").delete().eq("id", gid).execute().data)


def apagar_pagamento(db, pid: str) -> bool:
    """O valor volta a faltar nas parcelas da pessoa."""
    return bool(db.table("pagamentos").delete().eq("id", pid).execute().data)


def lancamentos_do_mes(db) -> dict:
    """Vendas e pagamentos do mês, para a Elita conferir e apagar o que estiver errado."""
    ini, fim = util.inicio_do_mes(), util.fim_do_mes()
    pagos = (db.table("pagamentos").select("id, valor, forma, pago_em, clientes(nome)")
             .gte("pago_em", ini.isoformat()).lte("pago_em", fim.isoformat())
             .order("pago_em", desc=True).execute().data)
    return {"mes": util.mes_atual(), "pagamentos": pagos,
            "vendas": vendas.do_mes(db, f"{ini.isoformat()}T00:00:00-03:00", f"{fim.isoformat()}T23:59:59-03:00")}


# ---------------------------------------------------------------------------
# CUSTOS E LUCRO (só a Elita): o lucro do mês e, produto por produto, quanto custou, quanto já
# entrou e se ele JÁ SE PAGOU. Usa o custo anotado HOJE no produto (o sistema não guarda o custo
# antigo). O desconto da compra toda é dividido entre os itens da venda, pelo valor de cada um.
# "Comprei" = o que já vendi + o que ainda tenho no estoque.
# ---------------------------------------------------------------------------
def _paginas(montar, tamanho: int = 1000) -> list[dict]:
    """Busca tudo, de 1000 em 1000 (o Supabase devolve no máximo 1000 linhas por vez)."""
    linhas, inicio = [], 0
    while True:
        pedaco = montar().range(inicio, inicio + tamanho - 1).execute().data
        linhas += pedaco
        if len(pedaco) < tamanho:
            return linhas
        inicio += tamanho


def itens_vendidos(db, inicio: str | None = None, fim: str | None = None) -> list[dict]:
    """Cada item vendido com 'valor' = o que entrou de verdade (já sem os descontos)."""
    def montar():
        q = db.table("venda_itens").select("id, venda_id, produto_id, quantidade, preco_unitario, desconto, "
                                           "vendas!inner(vendida_em, desconto)")
        if inicio:
            q = q.gte("vendas.vendida_em", inicio)
        if fim:
            q = q.lte("vendas.vendida_em", fim)
        return q.order("id")
    itens = _paginas(montar)
    soma_da_venda: dict = {}
    for i in itens:
        i["liquido"] = (Decimal(str(i["preco_unitario"])) * i["quantidade"] - Decimal(str(i.get("desconto") or 0)))
        soma_da_venda[i["venda_id"]] = soma_da_venda.get(i["venda_id"], Decimal(0)) + i["liquido"]
    for i in itens:
        desconto_venda = Decimal(str((i.get("vendas") or {}).get("desconto") or 0))
        soma = soma_da_venda[i["venda_id"]]
        parte = (desconto_venda * i["liquido"] / soma) if desconto_venda and soma > 0 else Decimal(0)
        i["valor"] = (i["liquido"] - parte).quantize(util.CENTAVO)
    return itens


def custos(db) -> dict:
    """{produto_id: custo de cada um}"""
    return {c["produto_id"]: Decimal(str(c["preco_custo"]))
            for c in db.table("produtos_custo").select("produto_id, preco_custo").execute().data}


def lucro_do_mes(db, tabela_custos: dict | None = None, gastei: Decimal | None = None) -> dict:
    """O lucro das vendas deste mês (só dos produtos com custo anotado) e o que sobra tirando os gastos."""
    ini, fim = util.inicio_do_mes(), util.fim_do_mes()
    tabela_custos = custos(db) if tabela_custos is None else tabela_custos
    itens = itens_vendidos(db, f"{ini.isoformat()}T00:00:00-03:00", f"{fim.isoformat()}T23:59:59-03:00")
    com_custo = [i for i in itens if i["produto_id"] in tabela_custos]
    vendi = sum((i["valor"] for i in com_custo), Decimal(0))
    custo = sum((tabela_custos[i["produto_id"]] * i["quantidade"] for i in com_custo), Decimal(0))
    sem_custo = sum((i["valor"] for i in itens if i["produto_id"] not in tabela_custos), Decimal(0))
    if gastei is None:
        gastei = _soma(gastos_do_periodo(db, ini.isoformat(), fim.isoformat()), "valor")
    lucro = vendi - custo
    return {"vendi": vendi, "custo": custo, "lucro": lucro, "sem_custo": sem_custo, "gastei": gastei,
            "sobrou": lucro - gastei, "pct": int((lucro * 100 / vendi).quantize(Decimal(1))) if vendi > 0 else 0}


def custos_e_lucro(db) -> dict:
    """A tela CUSTOS E LUCRO: o lucro do mês, cada produto (se já se pagou) e os que estão sem custo."""
    tabela_custos = custos(db)
    lista = (db.table("produtos").select("id, nome, preco, quantidade, servico").eq("ativo", True)
             .order("nome").execute().data)
    vendidos: dict = {}
    for i in itens_vendidos(db):
        if i["produto_id"]:
            qtd, entrou = vendidos.get(i["produto_id"], (0, Decimal(0)))
            vendidos[i["produto_id"]] = (qtd + i["quantidade"], entrou + i["valor"])
    produtos, sem_custo = [], []
    for p in lista:
        if p["id"] not in tabela_custos:
            sem_custo.append(p)
            continue
        custo, preco = tabela_custos[p["id"]], Decimal(str(p["preco"]))
        vendi, entrou = vendidos.get(p["id"], (0, Decimal(0)))
        lucro_cada = preco - custo
        item = {**p, "custo": custo, "lucro_cada": lucro_cada, "vendi": vendi, "entrou": entrou,
                "pct": int((lucro_cada * 100 / preco).quantize(Decimal(1))) if preco > 0 else 0,
                "lucro_ate_agora": entrou - custo * vendi}
        if p.get("servico"):
            item["grupo"] = "servico"
        else:
            comprei = vendi + (p["quantidade"] or 0)
            investi = custo * comprei
            falta = investi - entrou
            item.update(comprei=comprei, investi=investi, falta=max(falta, Decimal(0)),
                        se_pagou=investi > 0 and falta <= 0,
                        andamento=100 if investi <= 0 else min(100, int(entrou * 100 / investi)),
                        faltam_vendas=(math.ceil(falta / preco) if falta > 0 and preco > 0 else 0))
            item["grupo"] = "pagou" if item["se_pagou"] else "falta"
        produtos.append(item)
    # os que ainda não se pagaram primeiro (do que falta mais para o que falta menos), depois os outros
    produtos.sort(key=lambda p: ({"falta": 0, "pagou": 1, "servico": 2}[p["grupo"]], -p.get("falta", 0), p["nome"].lower()))
    return {"mes": util.mes_atual(), "lucro": lucro_do_mes(db, tabela_custos), "produtos": produtos,
            "sem_custo": sem_custo,
            "lucro_total": sum((p["lucro_ate_agora"] for p in produtos), Decimal(0)),
            "qtd": {g: sum(1 for p in produtos if p["grupo"] == g) for g in ("pagou", "falta", "servico")}}
