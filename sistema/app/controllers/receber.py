"""RECEBER: quem está atrasado, quem paga hoje e os próximos dias."""

from fastapi import APIRouter, Request

from ..core.web import Membro, pagina
from ..models import clientes, configuracoes

router = APIRouter()


@router.get("/receber")
def receber(request: Request, s: Membro):
    devendo = clientes.devendo(s.db)
    clientes.links_de_cobrar(configuracoes.ler(s.db), devendo)  # botão COBRAR no WhatsApp de cada uma
    atrasados, de_hoje, proximos = clientes.separar_para_receber(devendo)
    return pagina(request, "receber/receber.html", atrasados=atrasados, de_hoje=de_hoje, proximos=proximos)
