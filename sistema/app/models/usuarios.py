"""Login no Supabase: entrar e criar conta (primeiro acesso e ajudante)."""

from ..core.db import cliente_anonimo


def entrar(email: str, senha: str):
    """Devolve a sessão do Supabase (com os tokens) ou None se o e-mail/senha não conferem."""
    try:
        resp = cliente_anonimo().auth.sign_in_with_password({"email": email.strip().lower(), "password": senha})
    except Exception:
        return None
    return resp.session if resp else None


def criar_conta(nome: str, email: str, senha: str):
    """Cria o login. Pode dar erro (o controller mostra a mensagem)."""
    return cliente_anonimo().auth.sign_up({
        "email": email.strip().lower(), "password": senha,
        "options": {"data": {"nome": nome.strip()}},
    })
