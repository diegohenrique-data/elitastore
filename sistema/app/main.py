"""ElitaStore: aplicativo web (FastAPI + Supabase), organizado no padrão MVC.

    models/       M: os dados e as regras do negócio (o único lugar que fala com o banco)
    views/        V: as telas (HTML com Jinja), uma pasta por área
    controllers/  C: as rotas: recebem o pedido, chamam os models e mostram a view
    core/         base: login e banco (db), contas e formatos (util), peças web (web)
    static/       visual: CSS, ícone, manifest e o simulador de celular

Este arquivo só liga as peças: arquivos estáticos, rotas dos controllers e o que fazer em caso de erro.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from postgrest.exceptions import APIError

from .config import VERSAO
from .controllers import ROTAS
from .core.web import PASTA_APP, Aguardando, PrecisaEntrar, SoDona, gravar_cookies, ir, ir_com_erro, pagina

app = FastAPI(title="ElitaStore", version=VERSAO, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=PASTA_APP / "static"), name="static")
for rota in ROTAS:
    app.include_router(rota)


@app.exception_handler(PrecisaEntrar)
def _precisa_entrar(request: Request, exc: PrecisaEntrar):
    return RedirectResponse("/entrar", status_code=303)


@app.exception_handler(Aguardando)
def _aguardando(request: Request, exc: Aguardando):
    return RedirectResponse("/aguardando", status_code=303)


@app.exception_handler(SoDona)
def _so_dona(request: Request, exc: SoDona):
    return ir_com_erro("/", "Essa parte é só da Elita.")


registro = logging.getLogger("elita")


@app.exception_handler(APIError)
def _erro_banco(request: Request, exc: APIError):
    if exc.code == "22P02":  # endereço com código inválido (ex.: link quebrado): volta ao início
        return ir("/")
    registro.warning("Erro do banco em %s: %s", request.url.path, exc.message)  # o detalhe fica só aqui
    return pagina(request, "layout/mensagem.html", titulo="Não deu certo",
                  texto="Não consegui guardar ou buscar essa informação. Confira a internet e tente de novo. "
                        "Se continuar, chame quem cuida do sistema.", status=500)


@app.middleware("http")
async def _renovar_cookies(request: Request, call_next):
    """Se o login foi renovado durante o pedido, grava os tokens novos no navegador."""
    resposta = await call_next(request)
    s = getattr(request.state, "sessao", None)
    if s and s.novos_tokens:
        gravar_cookies(resposta, *s.novos_tokens)
    return resposta
