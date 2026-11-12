"""Encomendas: Pedido > Chegou (avisar a cliente) > Entregue (vira venda)."""

from decimal import Decimal

from ..core import util

ETAPAS = ("pedido", "chegou", "entregue")
ENTREGUES_NA_TELA = 20


def listar(db, limite: int = 200) -> list[dict]:
    """As encomendas mais novas primeiro, com a cliente e quanto falta pagar."""
    todas = (db.table("encomendas").select("*, clientes(nome, whatsapp)")
             .order("criado_em", desc=True).limit(limite).execute().data)
    for e in todas:
        falta = Decimal(str(e["preco"] or 0)) - Decimal(str(e["sinal"] or 0))
        e["falta"] = max(falta, Decimal(0))
    return todas


def quantas_chegaram(db) -> int:
    return db.table("encomendas").select("id", count="exact").eq("etapa", "chegou").execute().count or 0


def por_etapa(todas: list[dict]) -> dict[str, list]:
    grupos = {etapa: [e for e in todas if e["etapa"] == etapa] for etapa in ETAPAS}
    grupos["entregue"] = grupos["entregue"][:ENTREGUES_NA_TELA]
    return grupos


def mensagem_chegou(cfg: dict, nome: str | None) -> str:
    return util.preencher(cfg.get("msg_encomenda", ""), nome=util.primeiro_nome(nome))


def criar(db, cliente_id: str, descricao: str, preco: Decimal | None, sinal: Decimal) -> None:
    db.table("encomendas").insert({
        "cliente_id": cliente_id, "descricao": descricao.strip(),
        "preco": str(preco) if preco is not None else None, "sinal": str(sinal),
    }).execute()


def marcar_chegou(db, eid: str) -> None:
    db.table("encomendas").update({"etapa": "chegou", "chegou_em": util.agora().isoformat()}).eq("id", eid).execute()


def marcar_entregue(db, eid: str, venda_id: str) -> None:
    db.table("encomendas").update({
        "etapa": "entregue", "entregue_em": util.agora().isoformat(), "venda_id": venda_id,
    }).eq("id", eid).execute()
