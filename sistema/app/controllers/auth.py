"""Entrar, primeiro acesso, sair e "aguardando a Elita liberar"."""

import logging

from fastapi import APIRouter, Request

from ..core.db import abrir_sessao
from ..core.web import Texto, apagar_cookies, gravar_cookies, ir, pagina
from ..models import usuarios

router = APIRouter()


@router.get("/entrar")
def entrar_tela(request: Request):
    if abrir_sessao(request):
        return ir("/")
    return pagina(request, "auth/entrar.html")


@router.post("/entrar")
def entrar(request: Request, email: Texto, senha: Texto):
    sessao = usuarios.entrar(email, senha)
    if not sessao:
        return pagina(request, "auth/entrar.html", email=email,
                      erro="E-mail ou senha não conferem. Confira e tente de novo.")
    resposta = ir("/")
    gravar_cookies(resposta, sessao.access_token, sessao.refresh_token)
    return resposta


@router.get("/primeiro-acesso")
def primeiro_acesso_tela(request: Request):
    return pagina(request, "auth/primeiro_acesso.html")


@router.post("/primeiro-acesso")
def primeiro_acesso(request: Request, nome: Texto, email: Texto, senha: Texto, senha2: Texto):
    dados = {"nome": nome, "email": email}
    if len(senha) < 8:
        return pagina(request, "auth/primeiro_acesso.html", erro="A senha precisa ter pelo menos 8 letras ou números.", **dados)
    if senha != senha2:
        return pagina(request, "auth/primeiro_acesso.html", erro="As duas senhas estão diferentes.", **dados)
    try:
        resp = usuarios.criar_conta(nome, email, senha)
    except Exception as e:
        logging.getLogger("elita").warning("Erro ao criar a conta: %s", e)  # o detalhe fica só no servidor
        return pagina(request, "auth/primeiro_acesso.html",
                      erro="Não consegui criar a conta agora. Confira a internet e o e-mail e tente de novo.", **dados)
    if resp.session:
        resposta = ir("/")
        gravar_cookies(resposta, resp.session.access_token, resp.session.refresh_token)
        return resposta
    return pagina(request, "layout/mensagem.html", titulo="Confira seu e-mail 📧",
                  texto="Mandamos um e-mail de confirmação. Abra o e-mail, toque no link "
                        "e depois volte aqui para entrar.", link="/entrar", link_texto="ENTRAR")


@router.get("/sair")
def sair():
    resposta = ir("/entrar")
    apagar_cookies(resposta)
    return resposta


@router.get("/aguardando")
def aguardando(request: Request):
    s = abrir_sessao(request)
    if not s:
        return ir("/entrar")
    if s.ativo:
        return ir("/")
    return pagina(request, "layout/mensagem.html", titulo="Quase lá!",
                  texto="Seu cadastro foi feito. Agora a Elita, dona da loja, precisa liberar o seu "
                        "acesso. Assim que ela liberar, é só entrar de novo.", link="/sair", link_texto="SAIR")
