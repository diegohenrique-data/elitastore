"""Pessoas (clientes): lista, cadastro, ficha (com o histórico de compras e a compra antiga)
e o fiado (ela pagou, ajustar valor, mudar data)."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Request

from ..core import util
from ..core.web import Dona, Membro, Texto, ir, ir_com_erro, numero, pagina
from ..models import categorias, clientes, configuracoes, produtos, vendas
from ..models import cep as busca_cep
from ..models.vendas import FORMAS
from .vender import Lista, forma_e_partes, ler_desconto, ler_itens

router = APIRouter()


@router.get("/clientes")
def lista(request: Request, s: Membro, busca: str = ""):
    # todas vêm para a tela; o filtro (busca + abecedário) mostra só as 6 últimas até buscar
    pessoas = clientes.para_lista(s.db)
    return pagina(request, "clientes/lista.html", lista=pessoas, busca=busca,
                  letras_clientes=clientes.letras_usadas(pessoas))


@router.get("/clientes/nova")
def nova_tela(request: Request, s: Membro, volta: str = ""):
    return pagina(request, "clientes/form.html", c={}, volta=volta)


@router.get("/cep/{numero}")
def buscar_cep(s: Membro, numero: str):
    """O formulário de pessoas pergunta aqui, para mostrar a rua assim que digitam o CEP."""
    try:
        dados = busca_cep.buscar(numero)
    except busca_cep.ForaDoAr:
        return {"fora_do_ar": True}
    return {"endereco": busca_cep.rua_e_cidade(dados)} if dados else {"nao_achou": True}


@router.post("/clientes/nova")
def nova(request: Request, s: Membro, nome: Texto, whatsapp: Texto = "", cep: Texto = "",
         numero: Texto = "", sem_cep: Texto = "", endereco: Texto = "", observacoes: Texto = "", volta: Texto = ""):
    campos, erro = busca_cep.resolver(cep, numero, bool(sem_cep), endereco)
    if not erro and not nome.strip():
        erro = "Falta o nome da pessoa."
    if erro:
        return pagina(request, "clientes/form.html", c=dict(campos, nome=nome, whatsapp=whatsapp, observacoes=observacoes,
                      sem_cep=bool(sem_cep), endereco=endereco), volta=volta, erro=erro)
    novo = clientes.criar(s.db, nome, whatsapp, campos["endereco"], observacoes, campos["cep"], campos["numero"])
    if volta.startswith("/"):  # veio de outra tela (ex.: Nova venda): volta para lá já com ela escolhida
        sep = "&" if "?" in volta else "?"
        return ir(f"{volta}{sep}cliente={novo['id']}", "Pessoa cadastrada!")
    return ir(f"/clientes/{novo['id']}", "Pessoa cadastrada!")


@router.get("/clientes/{cid}")
def ficha(request: Request, s: Membro, cid: str):
    c = clientes.buscar(s.db, cid)
    if not c:
        return ir("/clientes")
    saldo = clientes.saldo(s.db, cid)
    compras = vendas.da_cliente(s.db, cid)
    parcelas = clientes.parcelas(s.db, cid)
    abertas = [p for p in parcelas if p["situacao"] != "paga"]
    cobrar = clientes.quanto_cobrar(saldo, abertas)
    msg = clientes.mensagem_cobranca(configuracoes.ler(s.db), c["nome"], cobrar)
    return pagina(request, "clientes/ficha.html", c=c, saldo=saldo, parcelas=parcelas, abertas=abertas,
                  pagamentos=clientes.pagamentos(s.db, cid), ajustes=clientes.ajustes(s.db, cid),
                  compras=compras, total_compras=vendas.total(compras),
                  cobrar=cobrar, link_cobrar=util.link_whatsapp(c["whatsapp"], msg))


# EXCLUIR PESSOA: só a Elita, com confirmação. Quem ainda deve não sai da lista.
@router.get("/clientes/{cid}/excluir")
def excluir_tela(request: Request, s: Dona, cid: str):
    c = clientes.buscar(s.db, cid, "id, nome, whatsapp")
    if not c:
        return ir("/clientes")
    return pagina(request, "clientes/excluir.html", c=c, falta=clientes.saldo(s.db, cid, "falta_total")["falta_total"],
                  compras=len(vendas.da_cliente(s.db, cid)))


@router.post("/clientes/{cid}/excluir")
def excluir(s: Dona, cid: str):
    c = clientes.buscar(s.db, cid, "id, nome")
    resultado = clientes.excluir(s.db, cid)
    if resultado == "nao_existe" or not c:
        return ir("/clientes")
    if resultado == "deve":
        return ir_com_erro(f"/clientes/{cid}", "Ela ainda deve. Primeiro anote o pagamento (ou ajuste o valor para zero) e depois exclua.")
    return ir("/clientes", f"{c['nome']} saiu da sua lista de pessoas.")


@router.post("/clientes/{cid}/voltar-para-lista")
def voltar_para_lista(s: Dona, cid: str):
    clientes.trazer_de_volta(s.db, cid)
    return ir(f"/clientes/{cid}", "Pronto! Ela voltou para a sua lista de pessoas.")


@router.get("/clientes/{cid}/editar")
def editar_tela(request: Request, s: Membro, cid: str):
    c = clientes.buscar(s.db, cid)
    if not c:
        return ir("/clientes")
    return pagina(request, "clientes/form.html", c=c, volta="")


@router.post("/clientes/{cid}/editar")
def editar(request: Request, s: Membro, cid: str, nome: Texto, whatsapp: Texto = "", cep: Texto = "",
           numero: Texto = "", sem_cep: Texto = "", endereco: Texto = "", observacoes: Texto = ""):
    campos, erro = busca_cep.resolver(cep, numero, bool(sem_cep), endereco)
    if not erro and not nome.strip():
        erro = "Falta o nome da pessoa."
    if erro:
        return pagina(request, "clientes/form.html", c=dict(campos, id=cid, nome=nome, whatsapp=whatsapp,
                      observacoes=observacoes, sem_cep=bool(sem_cep), endereco=endereco), volta="", erro=erro)
    clientes.atualizar(s.db, cid, nome, whatsapp, campos["endereco"], observacoes, campos["cep"], campos["numero"])
    return ir(f"/clientes/{cid}", "Dados atualizados!")


@router.post("/clientes/{cid}/pagou")
def pagou(s: Membro, cid: str, valor: Texto = "", forma: Texto = "dinheiro", dividir: Texto = "",
          parte_dinheiro: Texto = "", parte_pix: Texto = "", parte_cartao: Texto = ""):
    if dividir:  # PAGOU DE MAIS DE UM JEITO: cada forma vira um pagamento (uma linha cada)
        partes = vendas.ler_partes({"dinheiro": parte_dinheiro, "pix": parte_pix, "cartao": parte_cartao})
        if isinstance(partes, str):
            return ir_com_erro(f"/clientes/{cid}", partes)
        clientes.anotar_pagamentos(s.db, cid, partes)
        total = sum((v for _, v in partes), Decimal(0))
        return ir(f"/clientes/{cid}", f"Pronto! Pagamento de {util.reais(total)} anotado ({vendas.texto_partes(partes)}).")
    v = util.ler_reais(valor)
    if not v or v <= 0:
        return ir_com_erro(f"/clientes/{cid}", "Escreva quanto ela pagou. Ex.: 50,00")
    clientes.anotar_pagamento(s.db, cid, v, forma)
    return ir(f"/clientes/{cid}", f"Pronto! Pagamento de {util.reais(v)} anotado.")


@router.get("/clientes/{cid}/ajustar")
def ajustar_tela(request: Request, s: Dona, cid: str):
    c = clientes.buscar(s.db, cid, "id, nome")
    if not c:
        return ir("/clientes")
    falta = clientes.saldo(s.db, cid, "falta_total")["falta_total"]
    return pagina(request, "clientes/ajustar.html", c=c, falta=falta)


@router.post("/clientes/{cid}/ajustar")
def ajustar(s: Dona, cid: str, novo_valor: Texto, motivo: Texto = ""):
    novo = util.ler_reais(novo_valor)
    if novo is None or novo < 0:
        return ir_com_erro(f"/clientes/{cid}/ajustar", "Escreva o novo valor. Ex.: 40,00")
    antes = clientes.ajustar_valor(s.db, cid, novo, motivo)
    return ir(f"/clientes/{cid}", f"Valor ajustado: antes {util.reais(antes)} → agora {util.reais(novo)}")


# REPARCELAR (só a Elita): o que ela ainda deve vira parcelas novas, em quantas vezes e no dia que combinarem.
@router.get("/clientes/{cid}/reparcelar")
def reparcelar_tela(request: Request, s: Dona, cid: str):
    c = clientes.buscar(s.db, cid, "id, nome")
    if not c:
        return ir("/clientes")
    abertas = clientes.parcelas_abertas(s.db, cid)
    falta = sum((Decimal(str(p["falta"])) for p in abertas), Decimal(0))
    if falta <= 0:
        return ir_com_erro(f"/clientes/{cid}", "Ela não deve nada. Não tem o que reparcelar.")
    return pagina(request, "clientes/reparcelar.html", c=c, abertas=abertas, falta=falta, dia_padrao=util.hoje().day)


@router.post("/clientes/{cid}/reparcelar")
def reparcelar(s: Dona, cid: str, vezes: Texto = "1", dia: Texto = "10", por_mes: Texto = "1", dia2: Texto = "",
               motivo: Texto = ""):
    volta = f"/clientes/{cid}/reparcelar"
    n = max(1, min(24, numero(vezes, 1) or 1))
    dia_1 = max(1, min(31, numero(dia, 10) or 10))
    dia_2 = max(1, min(31, numero(dia2, dia_1) or dia_1)) if por_mes == "2" else None
    if dia_2 == dia_1 and n > 1:
        return ir_com_erro(volta, "Quem paga 2 vezes no mês precisa de dois dias diferentes. Ex.: dia 5 e dia 15.")
    feito = clientes.reparcelar(s.db, cid, n, dia_1, dia_2 if n > 1 else None, motivo)
    if not feito:
        return ir_com_erro(f"/clientes/{cid}", "Ela não deve nada. Não tem o que reparcelar.")
    vezes_texto = f"{n}x de {util.reais(feito['valores'][-1])}" if n > 1 else f"1 vez de {util.reais(feito['falta'])}"
    return ir(f"/clientes/{cid}", f"Reparcelado! {util.reais(feito['falta'])} em {vezes_texto}. "
                                  f"A 1ª parcela é {util.data_curta(feito['datas'][0])}.")


@router.get("/clientes/{cid}/mudar-data")
def mudar_data_tela(request: Request, s: Membro, cid: str):
    c = clientes.buscar(s.db, cid, "id, nome")
    if not c:
        return ir("/clientes")
    return pagina(request, "clientes/mudar_data.html", c=c, abertas=clientes.parcelas_abertas(s.db, cid))


@router.post("/clientes/{cid}/mudar-data")
def mudar_data(s: Membro, cid: str, parcela_id: Texto, nova_data: Texto):
    nova = util.para_data(nova_data) if nova_data else None
    if not nova or not clientes.mudar_data(s.db, cid, parcela_id, nova):
        return ir_com_erro(f"/clientes/{cid}/mudar-data", "Escolha a nova data.")
    return ir(f"/clientes/{cid}", f"Data mudada para {util.data_curta(nova)}")


# ---------------------------------------------------------------------------
# COMPRA ANTIGA: uma compra que a pessoa fez antes do sistema (ou que ficou sem anotar).
# É a MESMA tela da Nova venda (produtos com o filtro, carrinho e pagamento), com a cliente já
# escolhida e, no pagamento, o dia da compra e (no fiado) quanto ela ainda deve.
# Entra no histórico com a data dela. Não mexe no estoque. O que ela ainda deve vira parcelas
# a partir de hoje.
# ---------------------------------------------------------------------------
@router.get("/clientes/{cid}/compra-antiga")
def compra_antiga_tela(request: Request, s: Membro, cid: str):
    c = clientes.buscar(s.db, cid, "id, nome, whatsapp")
    if not c:
        return ir("/clientes")
    cats = categorias.com_nome(s.db)
    lista_produtos = produtos.para_venda(s.db, cats, so_em_estoque=False)
    pessoa = dict(c, letra=clientes.inicial(c["nome"]), recente=True)
    return pagina(request, "vender/nova.html", antiga=c, hoje=util.hoje(),
                  produtos=lista_produtos, produto="", categorias=categorias.com_produtos(cats, lista_produtos),
                  pessoas=[pessoa], letras_clientes={pessoa["letra"]}, cliente=cid, descricao="", preco="",
                  encomenda="", volta=f"/clientes/{cid}/compra-antiga", dia_padrao=util.hoje().day,
                  vendas_hoje=[], total_hoje=0)


@router.post("/clientes/{cid}/compra-antiga")
def compra_antiga(s: Membro, cid: str, quando: Texto = "", forma: Texto = "dinheiro",
                  item_produto: Lista = None, item_descricao: Lista = None, item_qtd: Lista = None,
                  item_preco: Lista = None, item_desconto: Lista = None, desconto: Texto = "",
                  parte_dinheiro: Texto = "", parte_pix: Texto = "", parte_cartao: Texto = "",
                  ainda_deve: Texto = "", vezes: Texto = "1", dia: Texto = "10",
                  por_mes: Texto = "1", dia2: Texto = ""):
    volta = f"/clientes/{cid}/compra-antiga"
    if not clientes.buscar(s.db, cid, "id"):
        return ir("/clientes")
    try:
        data = util.para_data(quando) if quando else None
    except ValueError:
        data = None
    if not data:
        return ir_com_erro(volta, "Escolha o dia em que foi a compra.")
    if data > util.hoje():
        return ir_com_erro(volta, "A compra antiga não pode ser numa data que ainda não chegou.")
    if data < date(2000, 1, 1):
        return ir_com_erro(volta, "Confira o ano da compra.")
    if not item_produto:
        return ir_com_erro(volta, "Coloque pelo menos um produto no carrinho.")
    if len(item_produto) > vendas.MAX_ITENS:
        return ir_com_erro(volta, f"No máximo {vendas.MAX_ITENS} produtos diferentes por compra.")
    itens = ler_itens(s.db, item_produto, item_descricao or [], item_qtd or [], item_preco or [],
                      conferir_estoque=False, descontos=item_desconto)
    if isinstance(itens, str):
        return ir_com_erro(volta, itens)
    valor_desconto = ler_desconto(desconto)
    erro_desconto = "Confira o desconto. Ex.: 10,00" if valor_desconto is None else vendas.desconto_recusado(itens, valor_desconto)
    if erro_desconto:
        return ir_com_erro(volta, erro_desconto)
    if forma not in FORMAS:
        return ir_com_erro(volta, "Escolha como ela pagou.")
    total = vendas.total_dos_itens(itens, valor_desconto)
    forma, partes, erro_partes = forma_e_partes(forma, total, parte_dinheiro, parte_pix, parte_cartao)
    if erro_partes:
        return ir_com_erro(volta, erro_partes)
    deve = None
    dia_1 = max(1, min(31, numero(dia, 10) or 10))
    dia_2 = None
    if forma == "fiado":
        deve = util.ler_reais(ainda_deve) if ainda_deve.strip() else total
        if deve is None or deve <= 0:
            return ir_com_erro(volta, "Escreva quanto ela ainda deve. Se já pagou tudo, escolha Dinheiro, Pix ou Cartão.")
        if deve > total:
            return ir_com_erro(volta, "O que ela ainda deve não pode ser mais que o valor da compra.")
        dia_2 = max(1, min(31, numero(dia2, dia_1) or dia_1)) if por_mes == "2" else None
        if dia_2 == dia_1 and (numero(vezes, 1) or 1) > 1:
            return ir_com_erro(volta, "Quem paga 2 vezes no mês precisa de dois dias diferentes. Ex.: dia 5 e dia 15.")
    vendas.cadastrar(s.db, cid, itens, forma, vezes=max(1, min(24, numero(vezes, 1) or 1)),
                     dia=dia_1, dia2=dia_2, vendida_em=data, ainda_deve=deve, desconto=valor_desconto,
                     partes=partes)
    return ir(f"/clientes/{cid}", f"Compra antiga de {util.data_com_ano(data)} anotada!")
