"""Dados da loja: nome, chave Pix, mensagens e os dias dos avisos (uma linha só, id = 1)."""

PADRAO = {"chave_pix": "", "msg_cobranca": "", "msg_encomenda": "", "dias_parado": 60,
          "dias_aviso_validade": 30, "estoque_minimo_padrao": 3, "nome_loja": "ElitaStore"}


def ler(db) -> dict:
    dados = db.table("configuracoes").select("*").eq("id", 1).execute().data
    return dados[0] if dados else dict(PADRAO)


def nome_loja(cfg: dict) -> str:
    return cfg.get("nome_loja") or "ElitaStore"


def salvar(db, dados: dict) -> None:
    db.table("configuracoes").update(dados).eq("id", 1).execute()
