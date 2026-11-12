"""Ligação com o Supabase e o login.

Cada pedido usa o "crachá" (token) de quem está logado. Assim o banco aplica as
regras de segurança (RLS): a ajudante não vê custo nem gastos, e só a dona apaga.
"""

import base64
import json
import threading
import time
from dataclasses import dataclass, field

from fastapi import Request

from supabase import Client, create_client

from ..config import SUPABASE_KEY, SUPABASE_URL

COOKIE_ACESSO = "elita_acesso"
COOKIE_RENOVA = "elita_renova"


def cliente_anonimo() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# Renovação do login sem "briga": se várias telas (abas, celular) pedirem ao mesmo tempo
# com a mesma chave de renovação, só a primeira vai ao Supabase e as outras reaproveitam
# o resultado. Sem isso o Supabase acha que a chave foi roubada e derruba o login.
_renovacoes: dict[str, tuple[float, str, str]] = {}
_trava = threading.Lock()


def _renovar(renova: str) -> tuple[str, str] | None:
    with _trava:
        agora = time.time()
        for chave in [k for k, (quando, _, _) in _renovacoes.items() if agora - quando > 120]:
            del _renovacoes[chave]
        if renova in _renovacoes:
            _, acesso, nova = _renovacoes[renova]
            return acesso, nova
        try:
            resp = cliente_anonimo().auth.refresh_session(renova)
        except Exception:
            return None
        if not resp or not resp.session:
            return None
        _renovacoes[renova] = (agora, resp.session.access_token, resp.session.refresh_token)
        return resp.session.access_token, resp.session.refresh_token


def _ler_token(token: str) -> dict:
    """Lê o conteúdo do token (sem conferir assinatura: quem confere é o Supabase)."""
    try:
        parte = token.split(".")[1]
        parte += "=" * (-len(parte) % 4)
        return json.loads(base64.urlsafe_b64decode(parte))
    except (IndexError, ValueError):
        return {}


@dataclass
class Sessao:
    db: Client
    usuario_id: str
    email: str
    perfil: dict
    novos_tokens: tuple[str, str] | None = field(default=None)

    @property
    def e_dona(self) -> bool:
        return self.perfil.get("papel") == "dona" and bool(self.perfil.get("ativo"))

    @property
    def ativo(self) -> bool:
        return bool(self.perfil.get("ativo"))

    @property
    def nome(self) -> str:
        return self.perfil.get("nome") or ""


def abrir_sessao(request: Request) -> Sessao | None:
    """Devolve a sessão de quem está logado, renovando o token se precisar."""
    if hasattr(request.state, "sessao"):
        return request.state.sessao

    acesso = request.cookies.get(COOKIE_ACESSO)
    renova = request.cookies.get(COOKIE_RENOVA)
    sessao = None
    if renova:
        novos = None
        dados = _ler_token(acesso) if acesso else {}
        if not dados or dados.get("exp", 0) < time.time() + 60:
            renovado = _renovar(renova)
            if renovado:
                acesso, renova = renovado
                novos = (acesso, renova)
                dados = _ler_token(acesso)
            else:
                dados = {}
        if dados.get("sub"):
            db = create_client(SUPABASE_URL, SUPABASE_KEY)
            db.postgrest.auth(acesso)
            db.options.headers["Authorization"] = f"Bearer {acesso}"  # fotos (Storage) com o mesmo crachá
            try:
                resp = db.table("perfis").select("*").eq("id", dados["sub"]).limit(1).execute()
                perfil = resp.data[0] if resp.data else {}
            except Exception:
                perfil = {}
            sessao = Sessao(db=db, usuario_id=dados["sub"], email=dados.get("email", ""),
                            perfil=perfil, novos_tokens=novos)

    request.state.sessao = sessao
    return sessao
