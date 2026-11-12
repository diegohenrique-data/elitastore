"""ENCOMENDAS: Pedido > Chegou (AVISAR no WhatsApp) > Entregue (abre a Nova venda)."""

from decimal import Decimal
from urllib.parse import quote

from fastapi import APIRouter, Request

from ..core import util
from ..core.web import Membro, Texto, ir, ir_com_erro, pagina
from ..models import clientes, configuracoes, encomendas

router = APIRouter()


@router.get("/encomendas")
def lista(request: Request, s: Membro):
    cfg = configuracoes.ler(s.db)
    todas = encomendas.listar(s.db)
    for e in todas:
        pessoa = e.get("clientes") or {}
        e["link_avisar"] = util.link_whatsapp(pessoa.get("whatsapp"), encomendas.mensagem_chegou(cfg, pessoa.get("nome")))
        # ENTREGUE abre a Nova venda já com a cliente, o que ela pediu e o que falta pagar
        e["link_entregar"] = (f"/vender?cliente={e['cliente_id']}&encomenda={e['id']}"
                              f"&descricao={quote(e['descricao'])}&preco={quote(str(e['falta']).replace('.', ','))}")
    return pagina(request, "encomendas/lista.html", grupos=encomendas.por_etapa(todas))


@router.get("/encomendas/nova")
def nova_tela(request: Request, s: Membro, cliente: str = ""):
    return pagina(request, "encomendas/form.html", cliente=cliente, pessoas=clientes.nomes(s.db))


@router.post("/encomendas/nova")
def nova(s: Membro, cliente_id: Texto, descricao: Texto, preco: Texto = "", sinal: Texto = ""):
    if not cliente_id or not descricao.strip():
        return ir_com_erro("/encomendas/nova", "Escolha a pessoa e escreva o que ela pediu.")
    encomendas.criar(s.db, cliente_id, descricao, util.ler_reais(preco), util.ler_reais(sinal) or Decimal(0))
    return ir("/encomendas", "Encomenda anotada!")


@router.post("/encomendas/{eid}/chegou")
def chegou(s: Membro, eid: str):
    encomendas.marcar_chegou(s.db, eid)
    return ir("/encomendas", "Marcada como CHEGOU. Agora é só avisar a pessoa!")
