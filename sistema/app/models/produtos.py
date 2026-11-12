"""Produtos, estoque, custo (só a Elita) e os avisos: acabou, acabando, perto de vencer, parado."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from ..core import util
from . import categorias


def listar(db, busca: str = "") -> list[dict]:
    """Produtos ativos, por nome. A busca procura no nome ou no código de barras exato."""
    q = db.table("produtos").select("*").eq("ativo", True).order("nome")
    if busca.strip():
        b = busca.strip()
        q = q.or_(f"nome.ilike.%{b}%,codigo_barras.eq.{b}")
    return q.execute().data


TEM_PARA_VENDER = "quantidade.gt.0,servico.is.true"  # tem no estoque, ou é SERVIÇO (não tem estoque)


def em_estoque(db, campos: str = "id, nome, preco, quantidade, categoria_id, servico") -> list[dict]:
    """Os produtos que dá para vender: os que têm no estoque e os serviços."""
    return (db.table("produtos").select(campos).eq("ativo", True)
            .or_(TEM_PARA_VENDER).order("nome").execute().data)


def para_venda(db, cats: list[dict] | None = None, so_em_estoque: bool = True) -> list[dict]:
    """Produtos em estoque para a tela de vender, com o preço já escrito (89,90), a categoria e
    os ids da categoria e das de cima ('categorias_ids'), para o filtro por categoria.
    A tela só mostra os produtos quando a Elita busca ou escolhe uma categoria.
    Na COMPRA ANTIGA (so_em_estoque=False) entram também os que acabaram."""
    cats = cats if cats is not None else categorias.com_nome(db)
    por_id = {c["id"]: c for c in cats}
    campos = "id, nome, preco, quantidade, categoria_id, codigo_barras, servico"
    produtos = (em_estoque(db, campos) if so_em_estoque else
                db.table("produtos").select(campos).eq("ativo", True).order("nome").execute().data)
    for p in produtos:
        cat = por_id.get(p["categoria_id"])
        p["preco_texto"] = f"{Decimal(str(p['preco'])):.2f}".replace(".", ",")
        p["categoria"] = cat["nome_completo"] if cat else "Sem categoria"
        p["categorias_ids"] = " ".join(c["id"] for c in cat["caminho"]) if cat else ""
    return produtos


def buscar(db, pid: str, campos: str = "*") -> dict | None:
    r = db.table("produtos").select(campos).eq("id", pid).execute().data
    return r[0] if r else None


def validade_recusada(validade: str, atual: str | None = None) -> bool:
    """A validade não pode ser antes de hoje. Hoje vale. Produto já vencido pode continuar com a
    data que tem, para ainda dar para mudar o preço ou o estoque dele."""
    if not validade or validade == atual:
        return False
    try:
        return util.para_data(validade) < util.hoje()
    except ValueError:  # data que não existe
        return True


def dono_do_codigo(db, codigo: str, exceto: str | None = None) -> dict | None:
    """O produto que já usa este código de barras, fora o 'exceto'. O código é único."""
    q = db.table("produtos").select("id, nome").eq("codigo_barras", codigo)
    if exceto:
        q = q.neq("id", exceto)
    r = q.limit(1).execute().data
    return r[0] if r else None


def custo(db, pid: str):
    r = db.table("produtos_custo").select("preco_custo").eq("produto_id", pid).execute().data
    return r[0]["preco_custo"] if r else None


def salvar(db, pid: str | None, dados: dict) -> str:
    """Cria (sem pid) ou atualiza o produto. Devolve o id."""
    if pid:
        db.table("produtos").update(dados).eq("id", pid).execute()
        return pid
    return db.table("produtos").insert(dados).execute().data[0]["id"]


def custo_pela_porcentagem(preco: Decimal, texto_pct: str) -> Decimal | None:
    """PRODUTO: a Elita escreve quanto ganha em cima do preço de venda (ex.: 30%) e o custo é o
    resto: R$ 100 com 30% -> custo R$ 70. None se a porcentagem estiver errada (fora de 0 a 100)."""
    pct = util.ler_reais((texto_pct or "").replace("%", ""))
    if pct is None or pct < 0 or pct > 100:
        return None
    return (preco - preco * pct / 100).quantize(util.CENTAVO)


def ganho_em_pct(preco, custo) -> str:
    """O contrário: com o preço e o custo guardados, quantos % ela ganha ('30' ou '27,5'). Vazio sem custo."""
    if custo is None or not preco or Decimal(str(preco)) <= 0:
        return ""
    pct = ((Decimal(str(preco)) - Decimal(str(custo))) * 100 / Decimal(str(preco))).quantize(Decimal("0.1"))
    return f"{pct:.1f}".replace(".0", "").replace(".", ",") if pct >= 0 else "0"


def salvar_custo(db, pid: str, valor: Decimal) -> None:
    db.table("produtos_custo").upsert({"produto_id": pid, "preco_custo": str(valor)}).execute()


def vezes_vendido(db, pid: str) -> int:
    return db.table("venda_itens").select("id", count="exact").eq("produto_id", pid).execute().count or 0


def apagar(db, pid: str) -> dict | None:
    """Só a dona consegue (o banco confere). Devolve o produto apagado ou None. Leva as fotos junto."""
    caminhos = [f["caminho"] for f in fotos(db, pid, com_link=False)]
    r = db.table("produtos").delete().eq("id", pid).execute().data
    if r and caminhos:
        _apagar_arquivos(db, caminhos)
    return r[0] if r else None


# ---------------------------------------------------------------------------
# Fotos: até 3 por produto (a de ordem 1 é a principal, a da vitrine).
# O arquivo fica no Storage (pasta "fotos", privada); a tabela produto_fotos diz de quem é.
# ---------------------------------------------------------------------------
MAX_FOTOS = 3
PASTA_FOTOS = "fotos"
VALIDADE_LINK = 6 * 3600  # o link da foto vale 6 horas (a pasta é privada)


def _links(db, caminhos: list[str]) -> dict[str, str]:
    """Link temporário de cada foto (caminho -> endereço). Se o Storage falhar, fica sem foto."""
    if not caminhos:
        return {}
    try:
        r = db.storage.from_(PASTA_FOTOS).create_signed_urls(caminhos, VALIDADE_LINK)
    except Exception:
        return {}
    return {x["path"]: x["signedURL"] for x in r if x.get("signedURL") and not x.get("error")}


def _apagar_arquivos(db, caminhos: list[str]) -> None:
    try:
        db.storage.from_(PASTA_FOTOS).remove(caminhos)
    except Exception:
        pass  # o produto já saiu; um arquivo esquecido não atrapalha a loja


def fotos(db, pid: str, com_link: bool = True) -> list[dict]:
    """As fotos do produto, a principal primeiro. Cada uma com 'url' (se com_link)."""
    lista = (db.table("produto_fotos").select("id, caminho, ordem").eq("produto_id", pid)
             .order("ordem").execute().data)
    if com_link:
        links = _links(db, [f["caminho"] for f in lista])
        for f in lista:
            f["url"] = links.get(f["caminho"], "")
    return lista


def marcar_fotos(db, produtos: list[dict]) -> None:
    """Põe em cada produto os links das fotos, a principal primeiro (campo 'fotos'; vazio = sem foto)."""
    ids = [p["id"] for p in produtos]
    todas = []
    for i in range(0, len(ids), 150):  # em pedaços, para o endereço não ficar enorme
        todas += (db.table("produto_fotos").select("produto_id, caminho, ordem")
                  .in_("produto_id", ids[i:i + 150]).order("ordem").execute().data)
    links = _links(db, [f["caminho"] for f in todas])
    por_produto: dict[str, list[str]] = {}
    for f in todas:
        if links.get(f["caminho"]):
            por_produto.setdefault(f["produto_id"], []).append(links[f["caminho"]])
    for p in produtos:
        p["fotos"] = por_produto.get(p["id"], [])


def arquivo_foto_principal(db, pid: str) -> bytes | None:
    """O arquivo (JPEG) da foto principal, para mandar no WhatsApp ou baixar. None = sem foto."""
    r = (db.table("produto_fotos").select("caminho").eq("produto_id", pid).eq("ordem", 1)
         .execute().data)
    if not r:
        return None
    try:
        return db.storage.from_(PASTA_FOTOS).download(r[0]["caminho"])
    except Exception:
        return None


def adicionar_foto(db, pid: str, jpeg: bytes) -> bool:
    """Guarda a foto (já ajustada) no próximo lugar livre. False se já tem as 3."""
    usadas = [f["ordem"] for f in fotos(db, pid, com_link=False)]
    livres = [o for o in range(1, MAX_FOTOS + 1) if o not in usadas]
    if not livres:
        return False
    caminho = f"produtos/{pid}/{uuid4().hex}.jpg"
    db.storage.from_(PASTA_FOTOS).upload(caminho, jpeg, {"content-type": "image/jpeg"})
    try:
        db.table("produto_fotos").insert({"produto_id": pid, "caminho": caminho, "ordem": livres[0]}).execute()
    except Exception:
        _apagar_arquivos(db, [caminho])
        raise
    return True


def foto_principal(db, pid: str, fid: str) -> bool:
    """Essa foto vira a principal (troca de lugar com a que era a 1ª)."""
    lista = fotos(db, pid, com_link=False)
    escolhida = next((f for f in lista if f["id"] == fid), None)
    if not escolhida:
        return False
    primeira = lista[0]
    if primeira["id"] != fid:  # troca só o arquivo de cada lugar (a ordem 1..3 não pode repetir)
        db.table("produto_fotos").update({"caminho": escolhida["caminho"]}).eq("id", primeira["id"]).execute()
        db.table("produto_fotos").update({"caminho": primeira["caminho"]}).eq("id", escolhida["id"]).execute()
    return True


def apagar_foto(db, pid: str, fid: str) -> bool:
    """Só a dona consegue (o banco confere). As de trás andam uma casa para a frente."""
    lista = fotos(db, pid, com_link=False)
    foto = next((f for f in lista if f["id"] == fid), None)
    if not foto or not db.table("produto_fotos").delete().eq("id", fid).execute().data:
        return False
    _apagar_arquivos(db, [foto["caminho"]])
    for f in lista:
        if f["ordem"] > foto["ordem"]:
            db.table("produto_fotos").update({"ordem": f["ordem"] - 1}).eq("id", f["id"]).execute()
    return True


# ---------------------------------------------------------------------------
# Avisos de estoque
# ---------------------------------------------------------------------------
ROTULOS_AVISO = (("acabou", "Acabou"), ("acabando", "Acabando"),
                 ("vencendo", "Perto de vencer"), ("parados", "Parado"))


def avisos_estoque(db, cfg: dict) -> dict:
    # SERVIÇO não tem estoque: não acaba, não vence e não fica parado
    produtos = (db.table("produtos").select("id, nome, preco, quantidade, estoque_minimo, validade, entrou_em, categoria_id")
                .eq("ativo", True).eq("servico", False).order("nome").execute().data)
    padrao = cfg.get("estoque_minimo_padrao", 3)
    limite_validade = util.hoje() + timedelta(days=cfg.get("dias_aviso_validade", 30))
    corte_parado = util.dias_atras(cfg.get("dias_parado", 60))
    vendidos = (db.table("venda_itens").select("produto_id, vendas!inner(vendida_em)")
                .gte("vendas.vendida_em", corte_parado.isoformat()).execute().data)
    vendidos_ids = {v["produto_id"] for v in vendidos}

    acabou, acabando, vencendo, parados = [], [], [], []
    for p in produtos:
        minimo = p["estoque_minimo"] if p["estoque_minimo"] is not None else padrao
        if p["quantidade"] == 0:
            acabou.append(p)
        elif p["quantidade"] <= minimo:
            acabando.append(p)
        if p["quantidade"] > 0 and p["validade"] and util.para_data(p["validade"]) <= limite_validade:
            vencendo.append(p)
        if (p["quantidade"] > 0 and util.para_data(p["entrou_em"]) <= corte_parado
                and p["id"] not in vendidos_ids):
            parados.append(p)
    return {"acabou": acabou, "acabando": acabando, "vencendo": vencendo, "parados": parados}


def marcar_avisos(produtos: list[dict], avisos: dict) -> None:
    """Põe em cada produto a lista de etiquetas de aviso (campo 'avisos')."""
    marca: dict = {}
    for tipo, rotulo in ROTULOS_AVISO:
        for p in avisos[tipo]:
            marca.setdefault(p["id"], []).append(rotulo)
    for p in produtos:
        p["avisos"] = marca.get(p["id"], [])


# ---------------------------------------------------------------------------
# Mensagens de WhatsApp
# ---------------------------------------------------------------------------
def mensagem_produto(p: dict) -> str:
    return f"✨ {p['nome']}\nPor {util.reais(p['preco'])}\nTenho na loja! Quer que eu separe? 😊"


def para_mandar(db, ids: list[str]) -> list[dict]:
    """Os produtos escolhidos para mandar (só os que ainda têm no estoque), por nome."""
    if not ids:
        return []
    return (db.table("produtos").select("id, nome, preco, categoria_id").in_("id", ids[:200])
            .eq("ativo", True).or_(TEM_PARA_VENDER).order("nome").execute().data)


def mensagem_o_que_tenho(loja: str, grupos: dict[str, list]) -> str:
    """O texto do MANDAR O QUE TENHO: só o nome e o preço de cada produto. O caminho da categoria
    (ex.: Cosméticos › Sabonetes › NATURA) NÃO vai para a cliente (pedido do Tiago, 04/11/2026);
    os produtos continuam na ordem das categorias, para os parecidos ficarem juntos."""
    itens = [p for _, lista in sorted(grupos.items()) for p in lista]
    linhas = [f"🛍️ {loja}: o que tenho hoje", ""]
    linhas += [f"• {p['nome']}: {util.reais(p['preco'])}" for p in itens]
    linhas += ["", "Quer que eu separe algum? 😊"]
    return "\n".join(linhas)
