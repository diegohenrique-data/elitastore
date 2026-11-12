"""Equipe: a Elita (dona principal) e as ajudantes que ela cadastra, liga, desliga ou exclui."""

import logging

from postgrest.exceptions import APIError

from . import usuarios


class ErroEquipe(Exception):
    """Algo não deu certo; a mensagem é para mostrar na tela."""


def listar(db) -> list[dict]:
    return db.table("perfis").select("*").order("criado_em").execute().data


def buscar(db, uid: str, campos: str = "*") -> dict | None:
    r = db.table("perfis").select(campos).eq("id", uid).execute().data
    return r[0] if r else None


def pode_mexer(perfil: dict | None, uid: str, quem_pede: str) -> bool:
    """Ninguém mexe na dona principal nem no próprio acesso."""
    return bool(perfil) and not perfil.get("principal") and uid != quem_pede


def cadastrar_ajudante(db, nome: str, email: str, senha: str) -> bool:
    """Cria o login da ajudante e já libera o acesso. Devolve se ela precisa confirmar o e-mail."""
    try:
        resp = usuarios.criar_conta(nome, email, senha)
    except Exception as e:
        logging.getLogger("elita").warning("Erro ao cadastrar ajudante: %s", e)  # o detalhe fica só no servidor
        raise ErroEquipe("Não consegui cadastrar agora. Confira o e-mail e a internet e tente de novo.") from e
    usuario = resp.user
    if not usuario or not usuario.identities:
        raise ErroEquipe("Esse e-mail já tem cadastro. Peça para ela entrar com ele e libere o acesso aqui embaixo.")
    liberado = (db.table("perfis").update({"ativo": True, "papel": "ajudante", "nome": nome.strip()})
                .eq("id", usuario.id).execute().data)
    if not liberado:
        raise ErroEquipe("O cadastro foi feito, mas não consegui liberar. Toque em LIBERAR na lista abaixo.")
    return not resp.session


def excluir(db, uid: str) -> None:
    """Apaga o login (e-mail, senha) e o perfil da ajudante (função do banco, só a dona)."""
    try:
        db.rpc("excluir_ajudante", {"alvo": uid}).execute()
    except APIError as e:
        raise ErroEquipe(e.message or "Não consegui excluir. Tente de novo.") from e


def mudar_acesso(db, uid: str, ativo: bool) -> None:
    db.table("perfis").update({"ativo": ativo}).eq("id", uid).execute()
