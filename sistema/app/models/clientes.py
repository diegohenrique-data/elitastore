"""Clientes (pessoas) e o fiado de cada uma: saldo, parcelas, pagamentos e ajustes."""

import unicodedata
from datetime import datetime, timezone
from decimal import Decimal

from ..core import util

CLIENTES_RECENTES = 5
PESSOAS_RECENTES = 6  # aba PESSOAS: sem buscar, só as 6 últimas pessoas que a Elita mexeu


# ---------------------------------------------------------------------------
# Cadastro
# ---------------------------------------------------------------------------
def buscar(db, cid: str, campos: str = "*") -> dict | None:
    r = db.table("clientes").select(campos).eq("id", cid).execute().data
    return r[0] if r else None


def nomes(db) -> list[dict]:
    return db.table("clientes").select("id, nome").eq("ativo", True).order("nome").execute().data


def criar(db, nome: str, whatsapp: str = "", endereco: str = "", observacoes: str = "",
          cep: str = "", numero: str = "") -> dict:
    return db.table("clientes").insert({
        "nome": nome.strip(), "whatsapp": whatsapp.strip(), "cep": cep, "numero": numero,
        "endereco": endereco.strip(), "observacoes": observacoes.strip(),
    }).execute().data[0]


def atualizar(db, cid: str, nome: str, whatsapp: str = "", endereco: str = "", observacoes: str = "",
              cep: str = "", numero: str = "") -> None:
    db.table("clientes").update({
        "nome": nome.strip(), "whatsapp": whatsapp.strip(), "cep": cep, "numero": numero,
        "endereco": endereco.strip(), "observacoes": observacoes.strip(),
    }).eq("id", cid).execute()


def inicial(nome: str | None) -> str:
    """Letra do abecedário com que o nome começa, sem acento: 'Ângela' -> 'A'. Sem letra: '#'."""
    simples = unicodedata.normalize("NFD", (nome or "").strip().upper())
    letra = next((ch for ch in simples if ch.isalpha()), "#")
    return letra if "A" <= letra <= "Z" else "#"


def para_venda(db) -> list[dict]:
    """Todas as clientes, com as recentes na frente (a tela de vender mostra só essas até buscar).
    Cada uma leva a letra inicial ('letra'), para o filtro do abecedário."""
    pessoas = (db.table("clientes").select("id, nome, whatsapp, criado_em").eq("ativo", True)
               .order("nome").execute().data)
    for p in pessoas:
        p["letra"] = inicial(p["nome"])
    return recentes_primeiro(db, pessoas)


def mexidas(db) -> dict:
    """Quando a Elita mexeu em cada pessoa pela última vez: cadastrou, vendeu, anotou pagamento
    ou ajustou o fiado. {cliente_id: data e hora (texto ISO, em UTC)}. Abrir a ficha conta também,
    mas fica guardado no aparelho (a tela de PESSOAS junta as duas coisas)."""
    def utc(texto):
        return datetime.fromisoformat(texto).astimezone(timezone.utc).isoformat() if texto else ""
    quando: dict = {}
    def anotar(cid, momento):
        momento = utc(momento)
        if cid and momento > quando.get(cid, ""):
            quando[cid] = momento
    for c in db.table("clientes").select("id, criado_em").execute().data:
        anotar(c["id"], c["criado_em"])
    for tabela, campo in (("vendas", "vendida_em"), ("pagamentos", "criado_em"), ("ajustes", "feito_em")):
        linhas = (db.table(tabela).select(f"cliente_id, {campo}").order(campo, desc=True).limit(300).execute().data)
        for linha in linhas:
            anotar(linha["cliente_id"], linha[campo])
    return quando


def para_lista(db) -> list[dict]:
    """Aba PESSOAS: todas, com o fiado (saldo) de cada uma, a letra inicial, quando foi mexida
    ('mexida') e as 6 últimas mexidas marcadas com 'recente' (a tela mostra só essas até buscar
    ou escolher a letra)."""
    pessoas = [p for p in saldos(db) if p.get("ativo", True)]  # as excluídas da lista não aparecem
    quando = mexidas(db)
    for p in pessoas:
        p["mexida"] = quando.get(p["cliente_id"], "")
    ultimas = sorted(pessoas, key=lambda p: p["mexida"], reverse=True)[:PESSOAS_RECENTES]
    recentes = {p["cliente_id"] for p in ultimas}
    for p in pessoas:
        p["letra"] = inicial(p["nome"])
        p["recente"] = p["cliente_id"] in recentes
    # as 6 últimas na frente, da mais nova para a mais antiga; depois as outras, por nome
    return ultimas + [p for p in pessoas if not p["recente"]]


def letras_usadas(pessoas: list[dict]) -> set[str]:
    """As letras que têm pelo menos uma cliente (as outras ficam apagadas no filtro)."""
    return {p.get("letra") or inicial(p["nome"]) for p in pessoas}


def recentes_primeiro(db, pessoas: list[dict]) -> list[dict]:
    """Coloca na frente as últimas clientes que compraram (ou as mais novas no cadastro),
    marcadas com 'recente'. A tela mostra só essas até a Elita digitar um nome."""
    ultimas = (db.table("vendas").select("cliente_id").not_.is_("cliente_id", "null")
               .order("vendida_em", desc=True).limit(60).execute().data)
    ordem = list(dict.fromkeys(v["cliente_id"] for v in ultimas))
    ordem += [p["id"] for p in sorted(pessoas, key=lambda p: p["criado_em"], reverse=True)]
    ids = list(dict.fromkeys(ordem))[:CLIENTES_RECENTES]
    por_id = {p["id"]: p for p in pessoas}
    frente = [dict(por_id[i], recente=True) for i in ids if i in por_id]
    return frente + [p for p in pessoas if p["id"] not in ids]


# ---------------------------------------------------------------------------
# EXCLUIR PESSOA (só a Elita). Quem nunca comprou é apagada de verdade. Quem já comprou sai da
# lista, mas fica guardada escondida: as vendas e o Meu Dinheiro continuam certos, e dá para
# trazer de volta. Quem ainda deve não sai: primeiro recebe (ou ajusta o valor para zero).
# ---------------------------------------------------------------------------
def tem_historico(db, cid: str) -> bool:
    """Ela já tem venda, pagamento, parcela ou encomenda no sistema?"""
    return any(db.table(t).select("id").eq("cliente_id", cid).limit(1).execute().data
               for t in ("vendas", "pagamentos", "parcelas", "encomendas"))


def excluir(db, cid: str) -> str:
    """Devolve 'deve' (não excluiu), 'apagada' (saiu de vez), 'escondida' (saiu da lista) ou 'nao_existe'."""
    c = buscar(db, cid, "id")
    if not c:
        return "nao_existe"
    if Decimal(str(saldo(db, cid, "falta_total")["falta_total"])) > 0:
        return "deve"
    if not tem_historico(db, cid):
        apagou = db.table("clientes").delete().eq("id", cid).execute().data
        if apagou:
            return "apagada"
    db.table("clientes").update({"ativo": False}).eq("id", cid).execute()
    return "escondida"


def trazer_de_volta(db, cid: str) -> None:
    db.table("clientes").update({"ativo": True}).eq("id", cid).execute()


# ---------------------------------------------------------------------------
# Fiado: saldos (view clientes_saldo) e parcelas (view parcelas_situacao)
# ---------------------------------------------------------------------------
def saldos(db, busca: str = "") -> list[dict]:
    q = db.table("clientes_saldo").select("*").order("nome")
    if busca.strip():
        q = q.ilike("nome", f"%{busca.strip()}%")
    return q.execute().data


def devendo(db, campos: str = "*") -> list[dict]:
    """Quem ainda tem fiado para pagar, pela data da próxima parcela."""
    return (db.table("clientes_saldo").select(campos).gt("falta_total", 0)
            .order("proximo_vencimento").execute().data)


def separar_para_receber(lista: list[dict]) -> tuple[list, list, list]:
    """(atrasados, de hoje, próximos dias)"""
    atrasados, de_hoje, proximos = [], [], []
    for c in lista:
        if Decimal(str(c["atrasado"])) > 0:
            atrasados.append(c)
        elif Decimal(str(c["hoje"])) > 0:
            de_hoje.append(c)
        else:
            proximos.append(c)
    return atrasados, de_hoje, proximos


def saldo(db, cid: str, campos: str = "*") -> dict:
    return db.table("clientes_saldo").select(campos).eq("cliente_id", cid).execute().data[0]


def parcelas(db, cid: str) -> list[dict]:
    return (db.table("parcelas_situacao").select("*").eq("cliente_id", cid)
            .order("vencimento").execute().data)


def parcelas_abertas(db, cid: str) -> list[dict]:
    return (db.table("parcelas_situacao").select("*").eq("cliente_id", cid)
            .neq("situacao", "paga").order("vencimento").execute().data)


def pagamentos(db, cid: str, limite: int = 20) -> list[dict]:
    return (db.table("pagamentos").select("*").eq("cliente_id", cid)
            .order("pago_em", desc=True).limit(limite).execute().data)


def ajustes(db, cid: str, limite: int = 10) -> list[dict]:
    return (db.table("ajustes").select("*").eq("cliente_id", cid)
            .order("feito_em", desc=True).limit(limite).execute().data)


def quanto_cobrar(saldo_cliente: dict, abertas: list[dict]) -> Decimal:
    """O que está atrasado + o de hoje; se não tiver, a próxima parcela."""
    cobrar = Decimal(str(saldo_cliente["atrasado"])) + Decimal(str(saldo_cliente["hoje"]))
    if cobrar <= 0 and abertas:
        cobrar = Decimal(str(abertas[0]["falta"]))
    return cobrar


MSG_ATRASADO = ("Oi {nome}, tudo bem? Passando para lembrar que o pagamento de {valor} está atrasado "
                "desde {desde}. Meu Pix é {pix}. Qualquer coisa, me chama. Obrigada! 😊")


def links_de_cobrar(cfg: dict, lista: list[dict]) -> None:
    """Para a tela RECEBER: põe em cada pessoa o link do WhatsApp com a cobrança pronta ('link_cobrar').
    Atrasada: a mensagem fala do atraso (desde quando) e cobra o atrasado + o de hoje.
    Paga hoje: a mensagem de cobrança da loja (a que a Elita escreveu em MEU DINHEIRO > Loja)."""
    for c in lista:
        atrasado, hoje = Decimal(str(c["atrasado"])), Decimal(str(c["hoje"]))
        if atrasado > 0:
            texto = util.preencher(MSG_ATRASADO, nome=util.primeiro_nome(c["nome"]), valor=util.reais(atrasado + hoje),
                                   desde=util.data_curta(c.get("proximo_vencimento")).split(", ")[-1],
                                   pix=cfg.get("chave_pix") or "(chave Pix)")
        else:
            texto = mensagem_cobranca(cfg, c["nome"], hoje if hoje > 0 else Decimal(str(c["falta_total"])))
        c["link_cobrar"] = util.link_whatsapp(c.get("whatsapp"), texto)


def mensagem_cobranca(cfg: dict, nome: str, valor: Decimal) -> str:
    return util.preencher(cfg.get("msg_cobranca", ""), nome=util.primeiro_nome(nome),
                          valor=util.reais(valor), pix=cfg.get("chave_pix") or "(chave Pix)")


# ---------------------------------------------------------------------------
# Ela pagou / Ajustar valor / Mudar data
# ---------------------------------------------------------------------------
FORMAS_PAGAMENTO = ("dinheiro", "pix", "cartao")


def anotar_pagamento(db, cid: str, valor: Decimal, forma: str) -> None:
    """Cada pagamento numa linha. O banco abate da parcela mais antiga primeiro."""
    if forma not in FORMAS_PAGAMENTO:
        forma = "dinheiro"
    db.table("pagamentos").insert({"cliente_id": cid, "valor": str(valor), "forma": forma}).execute()


def anotar_pagamentos(db, cid: str, partes: list[tuple[str, Decimal]]) -> None:
    """PAGOU DE MAIS DE UM JEITO (ex.: R$ 20 em dinheiro + R$ 30 no Pix): um pagamento por forma."""
    db.table("pagamentos").insert([{"cliente_id": cid, "valor": str(v), "forma": f if f in FORMAS_PAGAMENTO else "dinheiro"}
                                   for f, v in partes]).execute()


def ajustar_valor(db, cid: str, novo: Decimal, motivo: str = "") -> Decimal:
    """A Elita decide quanto falta: aumenta (parcela extra) ou diminui (corta das últimas).
    Devolve quanto faltava antes."""
    abertas = parcelas_abertas(db, cid)
    atual = sum((Decimal(str(p["falta"])) for p in abertas), Decimal(0))
    diferenca = novo - atual
    if diferenca > 0:
        venc = abertas[0]["vencimento"] if abertas else util.hoje().isoformat()
        db.table("parcelas").insert({
            "cliente_id": cid, "numero": 0, "valor": str(diferenca), "vencimento": venc,
            "observacao": "ajuste de valor",
        }).execute()
    elif diferenca < 0:
        sobra = -diferenca
        for p in reversed(abertas):
            if sobra <= 0:
                break
            corte = min(Decimal(str(p["falta"])), sobra)
            db.table("parcelas").update({"valor": str(Decimal(str(p["valor"])) - corte)}).eq("id", p["id"]).execute()
            sobra -= corte
    if diferenca != 0:
        db.table("ajustes").insert({
            "cliente_id": cid, "tipo": "valor", "antes": util.reais(atual),
            "depois": util.reais(novo), "motivo": motivo.strip(),
        }).execute()
    return atual


def reparcelar(db, cid: str, vezes: int, dia: int, dia2: int | None = None, motivo: str = "") -> dict | None:
    """REPARCELAR (só a Elita): tudo o que a pessoa ainda deve vira parcelas novas (vezes, dia e,
    se pagar 2 vezes no mês, dia2), a partir de hoje. O total não muda. As parcelas abertas ficam só
    com o que ela já pagou delas (os pagamentos são abatidos da mais antiga para a mais nova).
    Devolve {falta, antes, valores, datas} ou None se ela não deve nada."""
    abertas = parcelas_abertas(db, cid)
    falta = sum((Decimal(str(p["falta"])) for p in abertas), Decimal(0))
    if falta <= 0:
        return None
    hoje = util.hoje()
    valores = util.dividir_parcelas(falta, vezes)
    datas = util.datas_parcelas(vezes, dia, hoje, dia2)
    for p in abertas:  # a parcela antiga fica só com o que já foi pago dela
        db.table("parcelas").update({"valor": str(Decimal(str(p["pago"])))}).eq("id", p["id"]).execute()
    db.table("parcelas").insert([
        {"cliente_id": cid, "numero": i + 1, "valor": str(v), "vencimento": d.isoformat(),
         "observacao": f"reparcelado em {hoje.strftime('%d/%m/%Y')}"}
        for i, (v, d) in enumerate(zip(valores, datas))
    ]).execute()
    antes = f"{len(abertas)} {'parcela' if len(abertas) == 1 else 'parcelas'} ({util.reais(falta)})"
    depois = (f"{vezes}x de {util.reais(valores[-1])}" if vezes > 1 else f"1x de {util.reais(falta)}")
    depois += f", a 1ª em {util.data_curta(datas[0])}"
    db.table("ajustes").insert({"cliente_id": cid, "tipo": "vezes", "antes": antes, "depois": depois,
                                "motivo": motivo.strip()}).execute()
    return {"falta": falta, "antes": antes, "valores": valores, "datas": datas}


def mudar_data(db, cid: str, parcela_id: str, nova) -> bool:
    """Muda o vencimento de uma parcela e guarda no histórico. Devolve se achou a parcela."""
    p = db.table("parcelas").select("*").eq("id", parcela_id).eq("cliente_id", cid).execute().data
    if not p:
        return False
    db.table("parcelas").update({"vencimento": nova.isoformat()}).eq("id", parcela_id).execute()
    db.table("ajustes").insert({
        "cliente_id": cid, "parcela_id": parcela_id, "tipo": "data",
        "antes": util.data_completa(p[0]["vencimento"]), "depois": util.data_completa(nova),
    }).execute()
    return True
