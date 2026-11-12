"""VENDER: Nova venda em 3 telinhas (1. cliente > 2. produtos no carrinho > 3. pagamento)
e "Venda cadastrada!"."""

from decimal import Decimal
from itertools import zip_longest
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Form, Request

from ..core import util
from ..core.web import Membro, Texto, ir, ir_com_erro, numero, pagina, vazio_para_none
from ..models import categorias, clientes, configuracoes, encomendas, produtos, vendas
from ..models.vendas import FORMAS

router = APIRouter()


@router.get("/vender")
def nova(request: Request, s: Membro, produto: str = "", cliente: str = "",
         descricao: str = "", preco: str = "", encomenda: str = "", desconto: str = ""):
    """kit=...&desconto=... vem da OFERTA (VENDER ESTE KIT): os produtos já entram no carrinho e o
    desconto na compra toda."""
    cats = categorias.com_nome(s.db)
    lista_produtos = produtos.para_venda(s.db, cats)
    escolhido = next((p for p in lista_produtos if p["id"] == produto), None)
    if not escolhido and descricao:
        produto = "outro"
    # endereço desta tela com os mesmos dados, para voltar depois de cadastrar uma cliente nova
    params = [(k, v) for k, v in request.query_params.multi_items() if k not in ("ok", "erro")]
    volta = "/vender" + ("?" + "&".join(f"{k}={quote(v)}" for k, v in params) if params else "")
    hoje_lista = vendas.de_hoje(s.db)
    pessoas = clientes.para_venda(s.db)
    return pagina(request, "vender/nova.html", produtos=lista_produtos, produto=produto,
                  categorias=categorias.com_produtos(cats, lista_produtos),
                  pessoas=pessoas, letras_clientes=clientes.letras_usadas(pessoas), cliente=cliente, descricao=descricao,
                  preco=preco or (escolhido["preco_texto"] if escolhido else ""),
                  encomenda=encomenda, volta=volta, dia_padrao=util.hoje().day,
                  vendas_hoje=hoje_lista, total_hoje=vendas.total(hoje_lista),
                  kit=[k for k in request.query_params.getlist("kit") if k][:50],
                  desconto_kit=desconto if util.ler_reais(desconto) else "")


@router.get("/vender/nova")
def nova_endereco_antigo(request: Request):
    consulta = str(request.url.query)
    return ir("/vender" + ("?" + consulta if consulta else ""))


Lista = Annotated[list[str] | None, Form()]  # campo que se repete (um por item do carrinho)


def ler_itens(db, produtos_ids, descricoes, quantidades, precos, conferir_estoque: bool = True,
              descontos=None) -> list[dict] | str:
    """Monta os itens do carrinho a partir do formulário. Devolve a lista ou a mensagem de erro.
    Produto cadastrado: o nome vem do banco (e o preço também, se a Elita não escreveu outro).
    SERVIÇO não tem estoque: vende quantos quiser. 'descontos' = desconto de cada item, em R$.
    Na compra antiga (conferir_estoque=False) o estoque de hoje não importa."""
    itens, estoque = [], {}
    descontos = list(descontos or [])
    descontos += [""] * (len(produtos_ids) - len(descontos))
    for pid, desc, qtd, preco, desconto in zip_longest(produtos_ids, descricoes, quantidades, precos, descontos,
                                                       fillvalue=""):
        pid = vazio_para_none(pid)
        if pid == "outro":
            pid = None
        preco_produto = None
        if pid:
            p = produtos.buscar(db, pid, "nome, preco, quantidade, servico")
            if not p:
                return "Um dos produtos não existe mais. Tire ele do carrinho."
            desc, preco_produto = p["nome"], Decimal(str(p["preco"]))
            if not p.get("servico"):  # serviço não tem estoque para conferir
                estoque[pid] = p["quantidade"] or 0
        desc = (desc or "").strip()
        if not desc:
            return "Escreva o nome do produto que foi vendido."
        valor = util.ler_reais(preco)
        if valor is None:
            valor = preco_produto
        if valor is None or valor < 0:
            return f"Escreva o preço de {desc}. Ex.: 89,90"
        valor_desconto = util.ler_reais(desconto) if (desconto or "").strip() else Decimal(0)
        if valor_desconto is None or valor_desconto < 0:
            return f"Confira o desconto de {desc}. Ex.: 10,00"
        itens.append({"produto_id": pid, "descricao": desc, "quantidade": max(1, numero(qtd, 1) or 1),
                      "preco_unitario": valor, "desconto": valor_desconto})
    return (conferir_estoque and vendas.passou_do_estoque(itens, estoque)) or vendas.juntar_iguais(itens)


def forma_e_partes(forma: str, total: Decimal, dinheiro: str, pix: str, cartao: str):
    """PAGOU EM MAIS DE UMA FORMA: confere as partes. Devolve (forma, partes, erro).
    Se só uma forma tiver valor, a venda fica com essa forma (não precisa dividir)."""
    if forma != "dividido":
        return forma, None, ""
    partes = vendas.partes_da_venda({"dinheiro": dinheiro, "pix": pix, "cartao": cartao}, total)
    if isinstance(partes, str):
        return forma, None, partes
    if len(partes) == 1:
        return partes[0][0], None, ""
    return forma, partes, ""


def ler_desconto(texto: str) -> Decimal | None:
    """Desconto da compra toda, em R$ (vazio = sem desconto). None = escrito errado."""
    return util.ler_reais(texto) if (texto or "").strip() else Decimal(0)


@router.post("/vender")
def cadastrar(s: Membro, forma: Texto, cliente_id: Texto = "",
              item_produto: Lista = None, item_descricao: Lista = None, item_qtd: Lista = None, item_preco: Lista = None,
              item_desconto: Lista = None, desconto: Texto = "",
              parte_dinheiro: Texto = "", parte_pix: Texto = "", parte_cartao: Texto = "",
              produto_id: Texto = "", descricao: Texto = "", quantidade: Texto = "1", preco: Texto = "",
              vezes: Texto = "1", dia: Texto = "10", por_mes: Texto = "1", dia2: Texto = "",
              encomenda_id: Texto = "", volta: Texto = "/vender"):
    def voltar_com(msg):
        return ir_com_erro(volta if volta.startswith("/") else "/vender", msg)

    item_produto, item_descricao = item_produto or [], item_descricao or []
    item_qtd, item_preco = item_qtd or [], item_preco or []
    cliente = vazio_para_none(cliente_id)
    if not cliente:
        return voltar_com("Escolha a cliente. Toda venda precisa de uma cliente.")
    if not item_produto and (produto_id or descricao.strip()):  # sem carrinho (sem JavaScript): um produto só
        item_produto, item_descricao, item_qtd, item_preco = [produto_id], [descricao], [quantidade], [preco]
    if not item_produto:
        return voltar_com("Coloque pelo menos um produto no carrinho.")
    if len(item_produto) > vendas.MAX_ITENS:
        return voltar_com(f"No máximo {vendas.MAX_ITENS} produtos diferentes por venda.")
    itens = ler_itens(s.db, item_produto, item_descricao, item_qtd, item_preco, descontos=item_desconto)
    if isinstance(itens, str):
        return voltar_com(itens)
    valor_desconto = ler_desconto(desconto)
    erro_desconto = "Confira o desconto. Ex.: 10,00" if valor_desconto is None else vendas.desconto_recusado(itens, valor_desconto)
    if erro_desconto:
        return voltar_com(erro_desconto)
    if forma not in FORMAS:
        return voltar_com("Escolha como ela vai pagar.")
    forma, partes, erro_partes = forma_e_partes(forma, vendas.total_dos_itens(itens, valor_desconto),
                                                parte_dinheiro, parte_pix, parte_cartao)
    if erro_partes:
        return voltar_com(erro_partes)

    dia_1 = max(1, min(31, numero(dia, 10) or 10))
    dia_2 = max(1, min(31, numero(dia2, dia_1) or dia_1)) if forma == "fiado" and por_mes == "2" else None
    if dia_2 == dia_1 and (numero(vezes, 1) or 1) > 1:
        return voltar_com("Quem paga 2 vezes no mês precisa de dois dias diferentes. Ex.: dia 5 e dia 15.")
    venda = vendas.cadastrar(s.db, cliente, itens, forma,
                             vezes=max(1, min(24, numero(vezes, 1) or 1)), dia=dia_1, dia2=dia_2,
                             desconto=valor_desconto, partes=partes)
    destino = f"/vender/feita/{venda['id']}"
    if vazio_para_none(encomenda_id):
        encomendas.marcar_entregue(s.db, encomenda_id, venda["id"])
        destino += "?encomenda=1"
    return ir(destino)


@router.get("/vender/feita/{vid}")
def feita(request: Request, s: Membro, vid: str, encomenda: str = ""):
    venda = vendas.buscar_completa(s.db, vid)
    if not venda:
        return ir("/vender")
    c = venda.get("clientes") or {}
    recibo = vendas.recibo(venda, configuracoes.nome_loja(configuracoes.ler(s.db)))
    return pagina(request, "vender/feita.html", v=venda, c=c, recibo=recibo,
                  link_recibo=util.link_whatsapp(c.get("whatsapp"), recibo), da_encomenda=bool(encomenda),
                  pode_apagar=vendas.pode_apagar(venda, s.usuario_id, s.e_dona))


# Apagar venda: a ajudante apaga só a dela; a Elita, todas. Quem manda é a regra do banco.
@router.get("/vendas/{vid}/apagar")
def apagar_tela(request: Request, s: Membro, vid: str):
    venda = vendas.buscar_completa(s.db, vid)
    if not venda:
        return ir("/vender")
    if not vendas.pode_apagar(venda, s.usuario_id, s.e_dona):
        return ir_com_erro(f"/vender/feita/{vid}", "Você só pode apagar as vendas que você fez.")
    return pagina(request, "vender/apagar.html", v=venda, c=venda.get("clientes") or {},
                  pago=vendas.pago_da_venda(s.db, vid))


@router.post("/vendas/{vid}/apagar")
def apagar(s: Membro, vid: str):
    resultado = vendas.apagar(s.db, vid)
    if resultado == "ok":
        return ir("/vender", "Venda apagada. Os produtos voltaram para o estoque.")
    return ir_com_erro(f"/vender/feita/{vid}" if resultado != "nao_existe" else "/vender", {
        "sem_permissao": "Você só pode apagar as vendas que você fez.",
        "tem_pagamento": "Essa venda já recebeu pagamento. Só a Elita pode apagar.",
    }.get(resultado, "Essa venda não existe mais."))
