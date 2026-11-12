"""Peças da parte web usadas por todos os controllers.

- pagina(): monta uma tela (view) com os dados que o controller mandar.
- ir(): manda o navegador para outro endereço (com recado de "Pronto!" se quiser).
- Membro / Dona: exigem login (e, no caso de Dona, que seja a Elita).
- Texto: campo vindo de um formulário.
"""

from typing import Annotated
from urllib.parse import quote

from fastapi import Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import COOKIE_SEGURO, PASTA_SISTEMA, VERSAO
from ..models.vendas import FORMAS, FORMAS_PARTES
from . import util
from .db import COOKIE_ACESSO, COOKIE_RENOVA, Sessao, abrir_sessao

PASTA_APP = PASTA_SISTEMA / "app"

# Views: as telas HTML ficam em app/views/<assunto>/
templates = Jinja2Templates(directory=PASTA_APP / "views")
templates.env.filters["reais"] = util.reais
templates.env.filters["data_curta"] = util.data_curta
templates.env.filters["data_completa"] = util.data_completa
templates.env.globals["versao"] = VERSAO
templates.env.globals["FORMAS"] = FORMAS
templates.env.globals["FORMAS_PARTES"] = FORMAS_PARTES
# Muda sempre que o CSS muda, para o celular não ficar com o visual antigo guardado.
templates.env.globals["estilo_v"] = 0  # trocado a cada tela por _versao_visual()


def _versao_visual() -> int:
    """Muda sempre que o CSS ou o JS mudam: o celular baixa o visual novo na hora (sem cache velho)."""
    static = PASTA_APP / "static"
    return int(max((static / "estilo.css").stat().st_mtime, (static / "efeitos.js").stat().st_mtime,
                   (static / "fotos.js").stat().st_mtime, (static / "filtro.js").stat().st_mtime,
                   (static / "emojis.js").stat().st_mtime))

Texto = Annotated[str, Form()]


# ---------------------------------------------------------------------------
# Login e permissões
# ---------------------------------------------------------------------------
class PrecisaEntrar(Exception):
    pass


class Aguardando(Exception):
    pass


class SoDona(Exception):
    pass


def membro(request: Request) -> Sessao:
    s = abrir_sessao(request)
    if not s:
        raise PrecisaEntrar()
    if not s.ativo:
        raise Aguardando()
    return s


def dona(request: Request) -> Sessao:
    s = membro(request)
    if not s.e_dona:
        raise SoDona()
    return s


Membro = Annotated[Sessao, Depends(membro)]
Dona = Annotated[Sessao, Depends(dona)]


def gravar_cookies(resposta, acesso: str, renova: str) -> None:
    for nome, valor in ((COOKIE_ACESSO, acesso), (COOKIE_RENOVA, renova)):
        resposta.set_cookie(nome, valor, max_age=400 * 24 * 3600, httponly=True,
                            samesite="lax", secure=COOKIE_SEGURO)


def apagar_cookies(resposta) -> None:
    resposta.delete_cookie(COOKIE_ACESSO)
    resposta.delete_cookie(COOKIE_RENOVA)


# ---------------------------------------------------------------------------
# Respostas
# ---------------------------------------------------------------------------
def pagina(request: Request, nome: str, /, status: int = 200, **contexto) -> HTMLResponse:
    """Mostra a view `nome` (ex.: "vender/nova.html") com os dados do controller."""
    contexto.setdefault("s", getattr(request.state, "sessao", None))
    contexto.setdefault("ok", request.query_params.get("ok"))
    contexto.setdefault("erro", request.query_params.get("erro"))
    contexto["u"] = util
    contexto["estilo_v"] = _versao_visual()
    resposta = templates.TemplateResponse(request, nome, contexto, status_code=status)
    resposta.headers["Cache-Control"] = "no-cache"  # a tela sempre confere se tem versão nova
    return resposta


def ir(url: str, ok: str | None = None) -> RedirectResponse:
    if ok:
        url += ("&" if "?" in url else "?") + "ok=" + quote(ok)
    return RedirectResponse(url, status_code=303)


def ir_com_erro(url: str, msg: str) -> RedirectResponse:
    return RedirectResponse(url + ("&" if "?" in url else "?") + "erro=" + quote(msg), status_code=303)


# ---------------------------------------------------------------------------
# Leitura dos campos do formulário
# ---------------------------------------------------------------------------
def numero(texto: str, padrao: int | None = None) -> int | None:
    try:
        return int(str(texto).strip())
    except (TypeError, ValueError):
        return padrao


def vazio_para_none(texto: str | None) -> str | None:
    t = (texto or "").strip()
    return t or None
