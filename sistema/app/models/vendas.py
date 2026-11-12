"""Vendas: cadastrar (com as parcelas do fiado), vendas de hoje, apagar e o recibo."""

from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from ..config import FUSO
from ..core import util

FORMAS = {"dinheiro": "💵 Dinheiro", "pix": "📱 Pix", "cartao": "💳 Cartão", "fiado": "📒 Fiado",
          "dividido": "🔀 Mais de uma forma"}
# PAGAMENTO EM MAIS DE UMA FORMA: ex. R$ 20 em dinheiro + R$ 30 no cartão (cada parte numa linha)
FORMAS_PARTES = {"dinheiro": "💵 Dinheiro", "pix": "📱 Pix", "cartao": "💳 Cartão"}


def ler_partes(textos: dict) -> list[tuple[str, Decimal]] | str:
    """As partes do pagamento escritas na tela ({forma: "20,00"}). Em branco ou zero fica de fora.
    Devolve [(forma, valor)] ou a mensagem de erro."""
    partes = []
    for forma, nome in FORMAS_PARTES.items():
        texto = (textos.get(forma) or "").strip()
        if not texto:
            continue
        valor = util.ler_reais(texto)
        if valor is None or valor < 0:
            return f"Confira o valor em {nome.split(' ', 1)[1]}. Ex.: 20,00"
        if valor > 0:
            partes.append((forma, valor))
    return partes or "Escreva quanto foi em cada forma. Ex.: 20,00 no Dinheiro e 30,00 no Pix."


def partes_da_venda(textos: dict, total: Decimal) -> list[tuple[str, Decimal]] | str:
    """Na venda, as partes precisam somar o total certinho."""
    partes = ler_partes(textos)
    if isinstance(partes, str):
        return partes
    soma = sum((v for _, v in partes), Decimal(0))
    if soma != total:
        diferenca = util.reais(abs(total - soma))
        return (f"As formas somam {util.reais(soma)}, mas a venda é {util.reais(total)}. "
                + (f"Falta {diferenca}." if soma < total else f"Passou {diferenca}."))
    return partes


def texto_partes(partes) -> str:
    """'Dinheiro R$ 20,00 + Pix R$ 30,00' (aceita [(forma, valor)] ou [{forma, valor}])."""
    pares = [(p["forma"], p["valor"]) if isinstance(p, dict) else p for p in partes]
    return " + ".join(f"{FORMAS_PARTES[f].split(' ', 1)[1]} {util.reais(v)}" for f, v in pares)
COMPRA_ANTIGA = "Compra antiga (anotada depois)"  # marca, na observação, a compra que entrou pela ficha


def itens_texto(v: dict) -> str:
    return ", ".join((f"{i['quantidade']}x " if i["quantidade"] > 1 else "") + i["descricao"]
                     for i in v.get("venda_itens") or [])


def de_hoje(db) -> list[dict]:
    """Vendas feitas hoje, da mais nova para a mais antiga (com a cliente e os itens)."""
    comeco = datetime.combine(util.hoje(), time.min, tzinfo=ZoneInfo(FUSO))
    lista = (db.table("vendas")
             .select("id, total, forma_pagamento, vezes, vendida_em, clientes(nome), venda_itens(descricao, quantidade)")
             .gte("vendida_em", comeco.isoformat()).order("vendida_em", desc=True).execute().data)
    for v in lista:
        v["cliente_nome"] = (v.get("clientes") or {}).get("nome") or "Balcão"
        v["itens_texto"] = itens_texto(v)
        v["hora"] = datetime.fromisoformat(v["vendida_em"]).astimezone(ZoneInfo(FUSO)).strftime("%H:%M")
    return lista


def da_cliente(db, cid: str) -> list[dict]:
    """HISTÓRICO DE COMPRAS da pessoa, da mais nova para a mais antiga (com as compras antigas)."""
    lista = (db.table("vendas")
             .select("id, total, forma_pagamento, vezes, vendida_em, observacao, venda_itens(descricao, quantidade)")
             .eq("cliente_id", cid).order("vendida_em", desc=True).execute().data)
    for v in lista:
        v["itens_texto"] = itens_texto(v)
        v["data"] = datetime.fromisoformat(v["vendida_em"]).astimezone(ZoneInfo(FUSO)).date()
        v["antiga"] = v.get("observacao") == COMPRA_ANTIGA
    return lista


def total(vendas: list[dict]) -> Decimal:
    return sum((Decimal(str(v["total"])) for v in vendas), Decimal(0))


MAX_ITENS = 50  # itens diferentes no carrinho de uma venda


def total_dos_itens(itens: list[dict], desconto: Decimal = Decimal(0)) -> Decimal:
    """Soma do carrinho: quantidade x preço de cada item, menos o desconto de cada item e o
    desconto da compra toda ('desconto')."""
    soma = sum((i["preco_unitario"] * i["quantidade"] - i.get("desconto", Decimal(0)) for i in itens), Decimal(0))
    return (soma - desconto).quantize(util.CENTAVO)


def desconto_recusado(itens: list[dict], desconto: Decimal) -> str:
    """O desconto nunca passa do valor: nem o de um produto, nem o da compra toda. Devolve o erro ou ""."""
    for i in itens:
        d = i.get("desconto", Decimal(0))
        if d < 0 or d > i["preco_unitario"] * i["quantidade"]:
            return f"O desconto de {i['descricao']} é maior que o valor dele. Confira o desconto."
    if desconto < 0 or desconto > total_dos_itens(itens):
        return "O desconto da compra toda é maior que o valor da compra. Confira o desconto."
    return ""


def juntar_iguais(itens: list[dict]) -> list[dict]:
    """O mesmo produto pelo mesmo preço vira uma linha só (somando a quantidade e o desconto)."""
    juntos: dict = {}
    for i in itens:
        chave = (i["produto_id"], i["descricao"], i["preco_unitario"])
        if chave in juntos:
            juntos[chave]["quantidade"] += i["quantidade"]
            juntos[chave]["desconto"] = juntos[chave].get("desconto", Decimal(0)) + i.get("desconto", Decimal(0))
        else:
            juntos[chave] = dict(i)
    return list(juntos.values())


def passou_do_estoque(itens: list[dict], estoque: dict) -> str:
    """REGRA: só vende o que tem. Soma cada produto no carrinho (mesmo em linhas de preços diferentes)
    e compara com o estoque ({produto_id: quantidade}). Devolve a mensagem de erro ou ""."""
    no_carrinho: dict = {}
    for i in itens:
        if i["produto_id"]:
            no_carrinho[i["produto_id"]] = no_carrinho.get(i["produto_id"], 0) + i["quantidade"]
    for pid, qtd in no_carrinho.items():
        if pid not in estoque:  # SERVIÇO: não tem estoque, vende quantos quiser
            continue
        tem = estoque[pid]
        if qtd > tem:
            nome = next(i["descricao"] for i in itens if i["produto_id"] == pid)
            return (f"Só tem {tem} de {nome} no estoque. Tire {qtd - tem} do carrinho." if tem > 0
                    else f"{nome} acabou no estoque. Tire do carrinho.")
    return ""


def cadastrar(db, cliente_id: str, itens: list[dict], forma: str, vezes: int = 1, dia: int = 10,
              dia2: int | None = None, vendida_em: date | None = None, ainda_deve: Decimal | None = None,
              desconto: Decimal = Decimal(0), partes: list | None = None) -> dict:
    """Guarda a venda com todos os itens do carrinho e (no fiado) as parcelas.
    No fiado, 'dia2' é o segundo dia do mês para quem paga 2 vezes no mês.
    Cada item: {produto_id (ou None), descricao, quantidade, preco_unitario}.
    O banco baixa o estoque de cada produto sozinho. Devolve a venda guardada.
    COMPRA ANTIGA: 'vendida_em' é o dia em que foi a compra (não mexe no estoque); no fiado,
    'ainda_deve' é o que falta (as parcelas são só desse valor e começam a partir de hoje).
    DESCONTO: cada item pode ter 'desconto' (R$ da linha toda) e 'desconto' é o da compra toda.
    O total guardado já vem com os descontos tirados.
    PAGOU EM MAIS DE UMA FORMA: forma 'dividido' e 'partes' = [(forma, valor)], cada uma numa linha."""
    valor_total = total_dos_itens(itens, desconto)
    venda = {"cliente_id": cliente_id, "forma_pagamento": forma, "total": str(valor_total),
             "desconto": str(desconto.quantize(util.CENTAVO))}
    if vendida_em:
        venda["vendida_em"] = datetime.combine(vendida_em, time(12), tzinfo=ZoneInfo(FUSO)).isoformat()
        venda["observacao"] = COMPRA_ANTIGA
    if forma == "fiado":
        venda.update({"vezes": vezes, "dia_pagamento": dia})
    v = db.table("vendas").insert(venda).execute().data[0]
    if forma == "dividido" and partes:
        db.table("venda_pagamentos").insert([{"venda_id": v["id"], "forma": f, "valor": str(valor)}
                                             for f, valor in partes]).execute()
    guardados = db.table("venda_itens").insert([
        {"venda_id": v["id"], "produto_id": None if vendida_em else i["produto_id"], "descricao": i["descricao"],
         "quantidade": i["quantidade"], "preco_unitario": str(i["preco_unitario"]),
         "desconto": str(i.get("desconto", Decimal(0)))}
        for i in itens
    ]).execute().data
    if vendida_em:
        # COMPRA ANTIGA não mexe no estoque: o banco só baixa o estoque quando o item é criado com
        # o produto, então o produto é ligado ao item só depois de guardado
        for linha, i in zip(guardados, itens):
            if i["produto_id"]:
                db.table("venda_itens").update({"produto_id": i["produto_id"]}).eq("id", linha["id"]).execute()
    if forma == "fiado":
        valores = util.dividir_parcelas(ainda_deve if ainda_deve is not None else valor_total, vezes)
        datas = util.datas_parcelas(vezes, dia, util.hoje(), dia2)
        db.table("parcelas").insert([
            {"venda_id": v["id"], "cliente_id": cliente_id, "numero": i + 1,
             "valor": str(val), "vencimento": d.isoformat()}
            for i, (val, d) in enumerate(zip(valores, datas))
        ]).execute()
    return v


def buscar_completa(db, vid: str) -> dict | None:
    """A venda com a cliente, os itens e as parcelas."""
    r = (db.table("vendas")
         .select("*, clientes(id, nome, whatsapp), venda_itens(descricao, quantidade, preco_unitario, desconto), "
                 "parcelas(numero, valor, vencimento), venda_pagamentos(forma, valor)")
         .eq("id", vid).execute().data)
    return r[0] if r else None


def pode_apagar(venda: dict, usuario_id: str, e_dona: bool) -> bool:
    """A Elita apaga qualquer venda; a ajudante, só a que ela mesma vendeu."""
    return e_dona or venda.get("vendido_por") == usuario_id


def pago_da_venda(db, vid: str) -> Decimal:
    """Quanto das parcelas desta venda já foi pago."""
    linhas = db.table("parcelas_situacao").select("pago").eq("venda_id", vid).execute().data
    return sum((Decimal(str(p["pago"])) for p in linhas), Decimal(0))


def apagar(db, vid: str) -> str:
    """Quem pode apagar é conferido no banco. Devolve ok, sem_permissao, tem_pagamento ou nao_existe."""
    return db.rpc("apagar_venda", {"alvo": vid}).execute().data


def do_mes(db, inicio: str, fim: str) -> list[dict]:
    """Todas as vendas do mês, da mais nova para a mais antiga, com quem vendeu (tela da Elita)."""
    lista = (db.table("vendas")
             .select("id, total, forma_pagamento, vezes, vendida_em, clientes(nome), perfis(nome), "
                     "venda_itens(descricao, quantidade)")
             .gte("vendida_em", inicio).lte("vendida_em", fim).order("vendida_em", desc=True).execute().data)
    for v in lista:
        v["cliente_nome"] = (v.get("clientes") or {}).get("nome") or "Balcão"
        v["vendedor"] = (v.get("perfis") or {}).get("nome") or ""
        v["itens_texto"] = itens_texto(v)
        v["data"] = datetime.fromisoformat(v["vendida_em"]).astimezone(ZoneInfo(FUSO)).date()
    return lista


def do_periodo(db, inicio: str, fim: str) -> list[dict]:
    return (db.table("vendas").select("total, forma_pagamento")
            .gte("vendida_em", inicio).lte("vendida_em", fim).execute().data)


def dias_do_fiado(dia: int, parcelas: list[dict]) -> str:
    """'todo dia 10' ou, quando paga 2 vezes no mês, 'nos dias 5 e 15'."""
    if len(parcelas) > 1 and parcelas[0]["vencimento"][:7] == parcelas[1]["vencimento"][:7]:
        d1, d2 = sorted(int(p["vencimento"][8:10]) for p in parcelas[:2])
        return f"nos dias {d1} e {d2}"
    return f"todo dia {dia}"


def recibo(venda: dict, loja: str) -> str:
    """Recibo da venda para mandar no WhatsApp da cliente."""
    nome = util.primeiro_nome((venda.get("clientes") or {}).get("nome"))
    linhas = [f"Oi, {nome}! Aqui está o recibo da sua compra na {loja}.","", "🧾 *Recibo da compra*"]
    for i in venda.get("venda_itens") or []:
        desconto_item = Decimal(str(i.get("desconto") or 0))
        total_item = Decimal(str(i["preco_unitario"])) * i["quantidade"] - desconto_item
        linhas.append(f"• {i['quantidade']}x {i['descricao']}: {util.reais(total_item)}"
                      + (f" (desconto de {util.reais(desconto_item)})" if desconto_item > 0 else ""))
    desconto = Decimal(str(venda.get("desconto") or 0))
    if desconto > 0:
        linhas += ["", f"🏷️ Desconto na compra: − {util.reais(desconto)}"]
    linhas += ["", f"*Total: {util.reais(venda['total'])}*"]
    parcelas = sorted(venda.get("parcelas") or [], key=lambda p: p["numero"])
    if venda["forma_pagamento"] == "fiado" and parcelas:
        linhas.append(f"Pagamento: fiado em {len(parcelas)}x de {util.reais(parcelas[-1]['valor'])}, "
                      + dias_do_fiado(venda["dia_pagamento"], parcelas))
        linhas.append(f"1ª parcela: {util.data_completa(parcelas[0]['vencimento'])}")
    elif venda["forma_pagamento"] == "dividido" and venda.get("venda_pagamentos"):
        linhas.append("Pagamento: " + texto_partes(venda["venda_pagamentos"]) + " (pago ✅)")
    else:
        linhas.append("Pagamento: " + FORMAS[venda["forma_pagamento"]].split(" ", 1)[1] + " (pago ✅)")
    linhas += ["", "Obrigada pela compra! Deus abençoe 🙏"]
    return "\n".join(linhas)
