"""Tela principal: avisos do dia, VENDER em destaque e os botões."""

from decimal import Decimal

from fastapi import APIRouter, Request

from ..core import util
from ..core.web import Membro, pagina
from ..models import clientes, configuracoes, encomendas, produtos, vendas

router = APIRouter()


def saudacao() -> str:
    hora = util.agora().hour
    return "Bom dia" if hora < 12 else "Boa tarde" if hora < 18 else "Boa noite"


@router.get("/")
def inicio(request: Request, s: Membro):
    cfg = configuracoes.ler(s.db)
    devendo = clientes.devendo(s.db)
    hoje_lista = [c for c in devendo if Decimal(str(c["hoje"])) > 0]
    atrasados = [c for c in devendo if Decimal(str(c["atrasado"])) > 0]
    chegaram = encomendas.quantas_chegaram(s.db)
    hoje_vendas = vendas.de_hoje(s.db)
    return pagina(
        request, "inicio/inicio.html", saudacao=saudacao(),
        hoje_qtd=len(hoje_lista), hoje_valor=sum(Decimal(str(c["hoje"])) for c in hoje_lista),
        atrasados_qtd=len(atrasados), atrasados_valor=sum(Decimal(str(c["atrasado"])) for c in atrasados),
        chegaram=chegaram, estoque=produtos.avisos_estoque(s.db, cfg),
        vendas_qtd=len(hoje_vendas), vendas_valor=vendas.total(hoje_vendas),
    )
