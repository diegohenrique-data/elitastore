"""OFERTAS: montar um kit (carrinho de ofertas) com os produtos parados há muito tempo, dar um
desconto e mandar para a cliente no WhatsApp. 1) montar  2) conferir e mandar (ou VENDER ESTE KIT)."""

import unicodedata
from urllib.parse import urlencode

from fastapi import APIRouter, Request

from ..core import util
from ..core.web import Membro, ir_com_erro, pagina
from ..models import categorias, configuracoes, ofertas, produtos
from .produtos import _filtrar

router = APIRouter()


def _campos(request: Request) -> dict:
    """O que veio do formulário (fica no endereço, para voltar e mudar a oferta)."""
    q = request.query_params
    return {"prod": list(dict.fromkeys(p for p in q.getlist("prod") if p))[:ofertas.MAX_OFERTA],
            "nome": (q.get("nome") or "").strip()[:60], "tipo": "kit" if q.get("tipo") == "kit" else "pct",
            "valor": (q.get("valor") or "").strip(), "ate": q.get("ate") or ""}


def _endereco(base: str, campos: dict) -> str:
    pares = [("prod", p) for p in campos["prod"]] + [(k, campos[k]) for k in ("nome", "tipo", "valor", "ate") if campos[k]]
    return base + (f"?{urlencode(pares)}" if pares else "")


@router.get("/ofertas")
def montar(request: Request, s: Membro, busca: str = "", cat: str = "", f_cat: str = "", f_preco: str = ""):
    """Os parados primeiro; para juntar outros produtos, o MESMO filtro do sistema (busca + ⚙️ Filtros
    com categoria, tipo e preço). Sem filtro, só aparecem os outros que já estão na oferta."""
    campos = _campos(request)
    marcados = set(campos["prod"])
    cfg = configuracoes.ler(s.db)
    parados = ofertas.parados(s.db, cfg)
    ids_parados = {p["id"] for p in parados}
    em_estoque = produtos.em_estoque(s.db, "id, nome, preco, quantidade, categoria_id, servico, codigo_barras")
    todos_outros = [p for p in em_estoque if p["id"] not in ids_parados]
    todas_cats = categorias.com_nome(s.db)
    filtrando = bool(busca.strip() or cat or f_cat or f_preco)
    achados, filtro, preco_max = [], None, 0
    if filtrando:
        termo = _sem_acento(busca)
        base = [p for p in todos_outros if termo in _sem_acento(p["nome"]) or busca.strip() == (p.get("codigo_barras") or "")]
        achados, filtro, preco_max = _filtrar(request, todas_cats, base, cat, f_cat, f_preco)
    ids_achados = {p["id"] for p in achados}
    # os outros que já estão na oferta continuam à vista (marcados), mesmo fora do filtro
    outros = achados + [p for p in todos_outros if p["id"] in marcados and p["id"] not in ids_achados]
    produtos.marcar_fotos(s.db, parados + outros)
    etiquetas = [(texto, chave) for texto, chave in ((f'🔎 "{busca.strip()}"' if busca.strip() else "", "busca"),
                                                     (f"{filtro['icone']} {filtro['nome_completo']}" if filtro else "", "cat"),
                                                     (f"Até R$ {preco_max},00" if preco_max else "", "f_preco")) if texto]
    return pagina(request, "produtos/ofertas_montar.html", parados=parados, outros=outros, campos=campos,
                  marcados=marcados, dias_parado=cfg.get("dias_parado", 60), max_oferta=ofertas.MAX_OFERTA,
                  hoje=util.hoje(), categorias=categorias.com_produtos(todas_cats, todos_outros), busca=busca.strip(),
                  filtrando=filtrando, achados=len(achados), etiquetas=etiquetas, filtro=filtro, preco_max=preco_max,
                  cat_principal=filtro["caminho"][0]["id"] if filtro and filtro.get("caminho") else "")


def _sem_acento(texto: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", (texto or "").lower().strip()) if unicodedata.category(ch) != "Mn")


@router.get("/ofertas/ver")
def ver(request: Request, s: Membro):
    campos = _campos(request)
    voltar = _endereco("/ofertas", campos)
    itens = produtos.para_mandar(s.db, campos["prod"])  # só os que ainda têm (ou são serviço)
    if not itens:
        return ir_com_erro(voltar, "Toque em pelo menos um produto para pôr na oferta.")
    conta = ofertas.calcular(itens, campos["tipo"], util.ler_reais(campos["valor"]))
    if isinstance(conta, str):
        return ir_com_erro(voltar, conta)
    ate = ""
    if campos["ate"]:
        try:
            data = util.para_data(campos["ate"])
        except ValueError:
            data = None
        if not data or data < util.hoje():
            return ir_com_erro(voltar, "A data do \"vale até\" precisa ser hoje ou depois.")
        ate = data.isoformat()
    produtos.marcar_fotos(s.db, itens)
    msg = ofertas.mensagem(configuracoes.nome_loja(configuracoes.ler(s.db)), campos["nome"], itens, conta, ate)
    vender = "/vender?" + urlencode([("kit", p["id"]) for p in itens]
                                    + [("desconto", f"{conta['economia']:.2f}".replace(".", ","))])
    return pagina(request, "produtos/ofertas_ver.html", itens=itens, conta=conta, msg=msg,
                  link=util.link_whatsapp("", msg), com_foto=[p for p in itens if p["fotos"]],
                  nome_oferta=campos["nome"] or "Oferta especial", voltar=voltar, vender=vender)
