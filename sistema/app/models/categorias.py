"""Categorias e subcategorias dos produtos (quantos níveis quiser: Roupas › Blusas › Manga longa)."""

import json
import unicodedata
from functools import cache

from ..config import PASTA_SISTEMA

# Ícone de cada categoria pelo nome (como os aplicativos do relógio). A 1ª palavra que bater vale.
ICONES = (
    ("lingerie", "👙"), ("calcinha", "👙"), ("sutia", "👙"), ("biquini", "👙"), ("praia", "👙"),
    ("blusa", "👚"), ("camis", "👕"), ("calca", "👖"), ("jeans", "👖"), ("short", "🩳"), ("saia", "👗"),
    ("vestido", "👗"), ("roupa", "👗"), ("pijama", "🛌"), ("infantil", "🧸"), ("crianca", "🧸"),
    ("masculin", "👔"), ("feminin", "👠"), ("sapato", "👠"), ("calcado", "👟"), ("tenis", "👟"), ("sandalia", "👡"),
    ("desodorante", "🌬️"), ("perfum", "🧴"), ("colonia", "🧴"), ("importad", "✈️"), ("nacion", "🏠"),
    ("maquiagem", "💄"), ("batom", "💄"), ("cosmetic", "💄"), ("creme", "🧴"), ("cabelo", "💇"),
    ("anel", "💍"), ("alianca", "💍"), ("colar", "📿"), ("brinco", "✨"), ("pulseira", "📿"), ("prata", "💍"),
    ("ouro", "💛"), ("joia", "💎"), ("bijuteria", "💎"), ("relogio", "⌚"), ("oculos", "🕶️"),
    ("bolsa", "👜"), ("carteira", "👛"), ("acessorio", "👜"), ("cinto", "🎀"), ("presente", "🎁"),
    ("servico", "✂️"), ("liquida", "🏷️"), ("promo", "🏷️"),
)


@cache
def emojis_validos() -> frozenset[str]:
    """Os emojis do teclado (os mesmos do WhatsApp), da lista em static/emojis.json."""
    grupos = json.loads((PASTA_SISTEMA / "app" / "static" / "emojis.json").read_text(encoding="utf-8"))
    return frozenset(e for g in grupos for e, _ in g["emojis"])


def icone(nome: str) -> str:
    """'Perfumes Importados' -> '🧴'. Sem ícone conhecido: a primeira letra do nome."""

    simples = "".join(ch for ch in unicodedata.normalize("NFD", (nome or "").lower()) if unicodedata.category(ch) != "Mn")
    for chave, figura in ICONES:
        if chave in simples:
            return figura
    letra = next((ch for ch in (nome or "") if ch.isalnum()), "?")  # "[TESTE] Flores" -> "T"
    return letra.upper()


def com_nome(db) -> list[dict]:
    """Todas as categorias, com o caminho completo: 'Roupas › Blusas › Manga longa'."""
    cats = db.table("categorias").select("*").order("nome").execute().data
    por_id = {c["id"]: c for c in cats}

    def caminho(c, vistos=()):
        pai = por_id.get(c["categoria_pai_id"])
        if not pai or pai["id"] in vistos:
            return [c]
        return caminho(pai, vistos + (c["id"],)) + [c]

    for c in cats:
        c["caminho"] = caminho(c)
        c["nome_completo"] = " › ".join(x["nome"] for x in c["caminho"])
        c["nivel"] = len(c["caminho"]) - 1
        c["icone_escolhido"] = c.get("icone") or ""  # o que a Elita escolheu (vazio = automático)
        c["icone_auto"] = icone(c["nome"])  # o que o sistema põe sozinho pelo nome
        c["icone"] = c["icone_escolhido"] or c["icone_auto"]
    return sorted(cats, key=lambda c: c["nome_completo"].lower())


def buscar(cats: list[dict], cid: str) -> dict | None:
    return next((c for c in cats if c["id"] == cid), None)


def nomes(cats: list[dict]) -> dict[str, str]:
    """{id: 'Roupas › Blusas'}"""
    return {c["id"]: c["nome_completo"] for c in cats}


def com_subcategorias(cats: list[dict], cid: str) -> list[str]:
    """A categoria e todas as que estão dentro dela (em qualquer nível)."""
    filhas: dict = {}
    for c in cats:
        filhas.setdefault(c["categoria_pai_id"], []).append(c["id"])
    ids, pendentes = [], [cid]
    while pendentes:
        atual = pendentes.pop()
        if atual not in ids:
            ids.append(atual)
            pendentes += filhas.get(atual, [])
    return ids


def contar_produtos(cats: list[dict], produtos: list[dict]) -> None:
    """Põe em cada categoria quantos produtos ela tem, já somando as subcategorias (campo 'qtd')."""
    por_cat: dict = {}
    for p in produtos:
        por_cat[p["categoria_id"]] = por_cat.get(p["categoria_id"], 0) + 1
    for c in cats:
        c["qtd"] = sum(por_cat.get(i, 0) for i in com_subcategorias(cats, c["id"]))


def com_produtos(cats: list[dict], produtos: list[dict]) -> list[dict]:
    """Só as categorias que têm algum desses produtos (contando as subcategorias), para o filtro."""
    contar_produtos(cats, produtos)
    return [c for c in cats if c["qtd"] > 0]


def criar(db, nome: str, pai_id: str | None, figura: str = "") -> None:
    dados = {"nome": nome.strip(), "categoria_pai_id": pai_id}
    if figura:
        dados["icone"] = figura
    db.table("categorias").insert(dados).execute()


def trocar_icone(db, cid: str, figura: str) -> bool:
    """Põe o emoji escolhido na categoria. Vazio = tira (volta ao ícone automático pelo nome)."""
    return bool(db.table("categorias").update({"icone": figura or None}).eq("id", cid).execute().data)


def conteudo(db, cid: str) -> tuple[dict | None, int, int]:
    """(categoria, quantas subcategorias, quantos produtos) para saber se pode apagar."""
    cat = buscar(com_nome(db), cid)
    if not cat:
        return None, 0, 0
    filhas = db.table("categorias").select("id", count="exact").eq("categoria_pai_id", cid).execute().count or 0
    produtos = db.table("produtos").select("id", count="exact").eq("categoria_id", cid).execute().count or 0
    return cat, filhas, produtos


def apagar(db, cid: str) -> bool:
    """Só a dona consegue (o banco confere). Devolve se apagou."""
    return bool(db.table("categorias").delete().eq("id", cid).execute().data)


def _sem_acento(texto: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(ch) != "Mn")


def e_de_servico(cat: dict) -> bool:
    """A categoria (ou uma de cima dela) é de SERVIÇO: marcada no banco ou com "serviço" no nome.
    Produto novo nela já vem marcado como serviço (a Elita pode trocar)."""
    return any(c.get("tipo") == "servico" or "servic" in _sem_acento(c.get("nome", ""))
               for c in cat.get("caminho") or [cat])
