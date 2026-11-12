"""Configuração: lê o arquivo .env (no computador) ou as variáveis do servidor."""

import os
from pathlib import Path

PASTA_SISTEMA = Path(__file__).resolve().parent.parent


def _ler_env() -> None:
    arquivo = PASTA_SISTEMA / ".env"
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip())


_ler_env()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
FUSO = "America/Sao_Paulo"
VERSAO = "1.8"  # mude junto com o VERSOES.txt quando começar uma versão nova
# Em produção (https) o cookie só viaja por conexão segura: no servidor, use COOKIE_SEGURO=1.
COOKIE_SEGURO = os.environ.get("COOKIE_SEGURO") == "1"
