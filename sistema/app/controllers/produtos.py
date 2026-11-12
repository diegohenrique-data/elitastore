"""PRODUTOS: lista com filtro, novo produto (1. categoria > 2. dados), mudar, apagar,
categorias e "Mandar o que tenho" no WhatsApp."""

from urllib.parse import urlencode

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import RedirectResponse, Response

from ..core import imagem, util
from ..core.web import Dona, Membro, Texto, ir, ir_com_erro, numero, pagina, vazio_para_none
from ..models import categorias, configuracoes, produtos

router = APIRouter()


# Situação do estoque no filtro: valor -> (rótulo, avisos que entram)
SITUACOES = {"acabando": ("Acabando", {"Acabou", "Acabando"}), "vencendo": ("Perto de vencer", {"Perto de vencer"}),
             "parado": ("Parado", {"Parado"})}


@router.get("/produtos")
def lista(request: Request, s: Membro, busca: str = "", cat: str = "", f_cat: str = "", f_preco: str = "",
          f_situacao: str = "", todos: str = ""):
    """Abre no painel de filtro (sem a lista). Os produtos só aparecem depois de buscar, filtrar
    ou tocar em VER TODOS. O filtro manda f_cat, f_sub_<categoria> (o tipo), f_preco e f_situacao."""
    todas_cats = categorias.com_nome(s.db)
    itens = produtos.listar(s.db, busca)
    produtos.marcar_avisos(itens, produtos.avisos_estoque(s.db, configuracoes.ler(s.db)))
    cats_filtro = categorias.com_produtos(todas_cats, itens)  # só as que têm produto, com a quantidade
    situacoes = [{"valor": v, "nome": nome, "qtd": sum(1 for p in itens if quais & set(p["avisos"]))}
                 for v, (nome, quais) in SITUACOES.items()]
    resumo = {"produtos": len(itens), "unidades": sum(p["quantidade"] for p in itens)}

    itens, filtro, preco_max = _filtrar(request, todas_cats, itens, cat, f_cat, f_preco)
    situacao = f_situacao if f_situacao in SITUACOES else ""
    if situacao:
        itens = [p for p in itens if SITUACOES[situacao][1] & set(p["avisos"])]
    so_filtro = not (busca.strip() or filtro or preco_max or situacao or todos)
    if not so_filtro:
        produtos.marcar_fotos(s.db, itens)  # a vitrine mostra a foto principal de cada um
    nomes = categorias.nomes(todas_cats)
    grupos: dict[str, list] = {}
    for p in itens:
        grupos.setdefault(nomes.get(p["categoria_id"], "Sem categoria"), []).append(p)

    # etiquetas dos filtros ligados, cada uma com o endereço sem ela (o ✕)
    ligados = {"busca": busca, "cat": filtro["id"] if filtro else "", "f_preco": preco_max or "", "f_situacao": situacao}
    etiquetas = []
    if filtro:
        etiquetas.append((f"{filtro['icone']} {filtro['nome_completo']}", _endereco(**dict(ligados, cat=""))))
    if preco_max:
        etiquetas.append((f"Até R$ {preco_max},00", _endereco(**dict(ligados, f_preco=""))))
    if situacao:
        etiquetas.append((f"⚠️ {SITUACOES[situacao][0]}", _endereco(**dict(ligados, f_situacao=""))))
    return pagina(request, "produtos/lista.html", grupos=dict(sorted(grupos.items())), busca=busca,
                  total=len(itens), unidades=sum(p["quantidade"] for p in itens),
                  categorias=cats_filtro, filtro=filtro, preco_max=preco_max, situacao=situacao,
                  situacoes=situacoes, resumo=resumo, etiquetas=etiquetas,
                  cat_principal=filtro["caminho"][0]["id"] if filtro and filtro.get("caminho") else (filtro or {}).get("id", ""),
                  so_filtro=so_filtro)


def _filtrar(request: Request, todas_cats: list[dict], itens: list[dict], cat: str, f_cat: str, f_preco: str):
    """O filtro "O que eu tenho?" (o mesmo em PRODUTOS e MANDAR O QUE TENHO): categoria (o tipo,
    f_sub_<categoria>, vale mais que a categoria) e preço até. Devolve (itens, categoria, preço máx)."""
    cat = request.query_params.get(f"f_sub_{f_cat}") or f_cat or cat
    filtro = categorias.buscar(todas_cats, cat)
    if filtro:
        ids = set(categorias.com_subcategorias(todas_cats, filtro["id"]))
        itens = [p for p in itens if p["categoria_id"] in ids]
    preco_max = numero(f_preco, 0) or 0
    if preco_max:
        itens = [p for p in itens if float(p["preco"] or 0) <= preco_max]
    return itens, filtro, preco_max


def _endereco(**campos) -> str:
    """Endereço da lista de produtos só com os filtros que sobram (para o ✕ das etiquetas)."""
    resto = {k: v for k, v in campos.items() if v}
    return "/produtos" + (f"?{urlencode(resto)}" if resto else "")


def _form(request, s, p, categoria=None):
    # produto novo numa categoria de serviço (ou com "serviço" no nome) já vem marcado como SERVIÇO
    servico_padrao = bool(categoria) and categorias.e_de_servico(categoria)
    return pagina(request, "produtos/form.html", p=p, cats=categorias.com_nome(s.db), categoria=categoria,
                  max_fotos=produtos.MAX_FOTOS, servico_padrao=servico_padrao)


# Novo produto, passo 1: escolher (ou criar) a categoria. Pode ter quantos níveis quiser.
@router.get("/produtos/novo")
def novo_categoria(request: Request, s: Membro, dentro: str = ""):
    cats = categorias.com_nome(s.db)
    atual = categorias.buscar(cats, dentro)
    filhas = [c for c in cats if c["categoria_pai_id"] == (atual["id"] if atual else None)]
    return pagina(request, "produtos/categoria_escolher.html", atual=atual, filhas=filhas)


@router.post("/categorias/nova")
def categoria_nova(s: Membro, nome: Texto, pai_id: Texto = "", icone: Texto = ""):
    pai = vazio_para_none(pai_id)
    voltar = f"/produtos/novo?dentro={pai}" if pai else "/produtos/novo"
    if not nome.strip():
        return ir_com_erro(voltar, "Escreva o nome da categoria.")
    if icone and icone not in categorias.emojis_validos():
        return ir_com_erro(voltar, "Escolha o ícone na lista de emojis.")
    try:
        categorias.criar(s.db, nome, pai, icone)
    except Exception:
        return ir_com_erro(voltar, "Não consegui criar a categoria agora. Tente de novo.")
    # Fica no mesmo nível, para poder criar várias lado a lado (Natura, Boticário, Importados...).
    return ir(voltar, f"{nome.strip()} criada! Pode criar outra, ou tocar nela para entrar.")


# Ícone da categoria: um emoji da lista (os mesmos do WhatsApp). Vazio = tira (volta ao automático).
@router.post("/categorias/{cid}/icone")
def categoria_icone(s: Membro, cid: str, icone: Texto = ""):
    voltar = f"/produtos/novo?dentro={cid}"
    if icone and icone not in categorias.emojis_validos():
        return ir_com_erro(voltar, "Escolha o ícone na lista de emojis.")
    try:
        mudou = categorias.trocar_icone(s.db, cid, icone)
    except Exception:
        mudou = False
    if not mudou:
        return ir_com_erro(voltar, "Não consegui mudar o ícone agora. Tente de novo.")
    return ir(voltar, f"Ícone {icone} escolhido!" if icone else "Ícone tirado. Fica o ícone automático.")


# Apagar categoria: só a dona, com confirmação, e só se estiver vazia.
@router.get("/categorias/{cid}/apagar")
def categoria_apagar_tela(request: Request, s: Dona, cid: str):
    cat, filhas, qtd_produtos = categorias.conteudo(s.db, cid)
    if not cat:
        return ir("/produtos/novo")
    return pagina(request, "produtos/categoria_apagar.html", cat=cat, filhas=filhas, produtos=qtd_produtos)


@router.post("/categorias/{cid}/apagar")
def categoria_apagar(s: Dona, cid: str):
    cat, filhas, qtd_produtos = categorias.conteudo(s.db, cid)
    if not cat:
        return ir("/produtos/novo")
    if filhas or qtd_produtos:
        return ir(f"/categorias/{cid}/apagar")
    if not categorias.apagar(s.db, cid):
        return ir_com_erro(f"/produtos/novo?dentro={cid}", "Não consegui apagar. Só a dona pode apagar.")
    pai = cat["categoria_pai_id"]
    return ir(f"/produtos/novo?dentro={pai}" if pai else "/produtos/novo", f"Categoria {cat['nome']} apagada.")


# Novo produto, passo 2: os dados do produto, já dentro da categoria escolhida.
@router.get("/produtos/novo/dados")
def novo_dados(request: Request, s: Membro, categoria: str = ""):
    cat = categorias.buscar(categorias.com_nome(s.db), categoria)
    if not cat:
        return ir_com_erro("/produtos/novo", "Primeiro escolha a categoria do produto.")
    return _form(request, s, {"categoria_id": cat["id"]}, categoria=cat)


@router.get("/produtos/{pid}")
def editar_tela(request: Request, s: Membro, pid: str):
    p = produtos.buscar(s.db, pid)
    if not p:
        return ir("/produtos")
    if s.e_dona:
        p["custo"] = produtos.custo(s.db, pid)
        p["ganho_pct"] = produtos.ganho_em_pct(p["preco"], p["custo"])
    p["fotos"] = produtos.fotos(s.db, pid)
    return _form(request, s, p)


@router.post("/produtos/salvar")
def salvar(s: Membro, nome: Texto, preco: Texto, pid: Texto = "",
           quantidade: Texto = "0", somar: Texto = "", categoria_id: Texto = "",
           estoque_minimo: Texto = "", validade: Texto = "", codigo_barras: Texto = "",
           custo: Texto = "", ganho_pct: Texto = "", servico: Texto = "", fotos: list[UploadFile] = File(default=[])):
    cat = vazio_para_none(categoria_id)
    if not cat:
        return ir_com_erro("/produtos/novo", "Primeiro escolha a categoria do produto.")
    destino = f"/produtos/{pid}" if pid else f"/produtos/novo/dados?categoria={cat}"
    valor = util.ler_reais(preco)
    if not nome.strip():
        return ir_com_erro(destino, "Falta o nome do produto.")
    if valor is None or valor < 0:
        return ir_com_erro(destino, "Escreva o preço. Ex.: 89,90")
    # CUSTO em reais ou a % QUE GANHA (a tela preenche um pelo outro). Veio o custo: vale o custo.
    custo_valor = util.ler_reais(custo) if custo.strip() else None
    if custo_valor is None and ganho_pct.strip():  # só a %: ela vira o custo
        custo_valor = produtos.custo_pela_porcentagem(valor, ganho_pct)
        if custo_valor is None:
            return ir_com_erro(destino, "A porcentagem que você ganha vai de 0 a 100. Ex.: 30")
    atual = (produtos.buscar(s.db, pid) or {}).get("validade") if pid else None
    if not servico and produtos.validade_recusada(validade, atual):
        return ir_com_erro(destino, "A validade não pode ser uma data que já passou. Use hoje ou uma data futura.")
    codigo = vazio_para_none(codigo_barras)
    outro = produtos.dono_do_codigo(s.db, codigo, pid or None) if codigo and not servico else None
    if outro:
        return ir_com_erro(destino, f"Esse código de barras já é do produto \"{outro['nome']}\". Cada produto tem o seu.")
    dados = {
        "nome": nome.strip(), "preco": str(valor), "categoria_id": cat,
        "quantidade": max(0, numero(quantidade, 0) or 0) + max(0, numero(somar, 0) or 0),
        "estoque_minimo": numero(estoque_minimo) if estoque_minimo.strip() else None,
        "validade": validade or None, "codigo_barras": codigo, "servico": False,
    }
    if servico:  # SERVIÇO (escova, manicure...): sem estoque, sem validade e sem código de barras
        dados.update({"servico": True, "quantidade": 0, "estoque_minimo": None, "validade": None,
                      "codigo_barras": None})
    elif numero(somar, 0):  # chegou mercadoria nova: conta os dias "parado" a partir de hoje
        dados["entrou_em"] = util.hoje().isoformat()
    pid = produtos.salvar(s.db, pid or None, dados)
    if s.e_dona and custo_valor is not None:
        produtos.salvar_custo(s.db, pid, custo_valor)
    guardadas, problema = _guardar_fotos(s, pid, fotos)
    if problema:
        return ir_com_erro(f"/produtos/{pid}", f"Produto guardado, mas {problema}")
    return ir("/produtos", "Produto guardado!" + (" Com foto." if guardadas else ""))


# ---------------------------------------------------------------------------
# FOTOS do produto: tirar com a câmera ou escolher da galeria/computador.
# Toda foto é ajustada sozinha (quadrado, fundo branco) antes de guardar.
# ---------------------------------------------------------------------------
def _guardar_fotos(s, pid: str, arquivos: list[UploadFile]) -> tuple[int, str]:
    """Guarda as fotos que vieram. Devolve (quantas entraram, aviso de problema ou "")."""
    guardadas = 0
    for arq in [a for a in arquivos if a and a.filename]:
        try:
            jpeg = imagem.ajustar(arq.file.read())
        except imagem.FotoInvalida as e:
            return guardadas, f"uma foto não entrou: {e} Tente outra."
        try:
            if not produtos.adicionar_foto(s.db, pid, jpeg):
                return guardadas, f"cada produto tem no máximo {produtos.MAX_FOTOS} fotos. Apague uma para pôr outra."
        except Exception:
            return guardadas, "não consegui guardar a foto agora. Tente de novo."
        guardadas += 1
    return guardadas, ""


@router.post("/produtos/{pid}/fotos")
def fotos_adicionar(s: Membro, pid: str, fotos: list[UploadFile] = File(default=[])):
    if not produtos.buscar(s.db, pid, "id"):
        return ir("/produtos")
    guardadas, problema = _guardar_fotos(s, pid, fotos)
    if problema:
        return ir_com_erro(f"/produtos/{pid}", problema[0].upper() + problema[1:])
    if not guardadas:
        return ir_com_erro(f"/produtos/{pid}", "Escolha uma foto primeiro.")
    return ir(f"/produtos/{pid}", "Foto guardada!" if guardadas == 1 else f"{guardadas} fotos guardadas!")


@router.post("/produtos/{pid}/fotos/{fid}/principal")
def fotos_principal(s: Membro, pid: str, fid: str):
    produtos.foto_principal(s.db, pid, fid)
    return ir(f"/produtos/{pid}", "Essa agora é a foto principal.")


@router.post("/produtos/{pid}/fotos/{fid}/apagar")
def fotos_apagar(s: Dona, pid: str, fid: str):
    if not produtos.apagar_foto(s.db, pid, fid):
        return ir_com_erro(f"/produtos/{pid}", "Não consegui apagar a foto. Só a dona pode apagar.")
    return ir(f"/produtos/{pid}", "Foto apagada.")


# Apagar produto: só a dona, com confirmação. As vendas antigas continuam (com o nome guardado).
@router.get("/produtos/{pid}/apagar")
def apagar_tela(request: Request, s: Dona, pid: str):
    p = produtos.buscar(s.db, pid, "id, nome, preco, quantidade, categoria_id, servico")
    if not p:
        return ir("/produtos")
    cat = categorias.buscar(categorias.com_nome(s.db), p["categoria_id"])
    return pagina(request, "produtos/apagar.html", p=p, vendas=produtos.vezes_vendido(s.db, pid),
                  categoria=cat["nome_completo"] if cat else "", icone_categoria=cat["icone"] if cat else "")


@router.post("/produtos/{pid}/apagar")
def apagar(s: Dona, pid: str):
    apagado = produtos.apagar(s.db, pid)
    if not apagado:
        return ir_com_erro(f"/produtos/{pid}", "Não consegui apagar. Só a dona pode apagar.")
    return ir("/produtos", f"Produto {apagado['nome']} apagado.")


@router.get("/produtos/{pid}/whatsapp")
def whatsapp(s: Membro, pid: str):
    p = produtos.buscar(s.db, pid, "nome, preco")
    if not p:
        return ir("/produtos")
    return RedirectResponse(util.link_whatsapp("", produtos.mensagem_produto(p)), status_code=303)


# MANDAR O QUE TENHO: 1) escolhe as categorias  2) marca os produtos (vê a foto de cada um)
# 3) confere e manda: com as fotos (compartilhar do celular) ou só o texto (WhatsApp).
# Dá para juntar produtos de várias categorias: os escolhidos vão no endereço (prod=...) e
# aparecem na "cesta" (a janelinha de baixo) enquanto ela troca de categoria.
MAX_MANDAR = 30  # fotos demais de uma vez enchem a conversa da cliente


@router.get("/mandar-o-que-tenho")
def mandar_o_que_tenho(request: Request, s: Membro, passo: str = "", busca: str = "", cat: str = "",
                       f_cat: str = "", f_preco: str = "", todos: str = ""):
    """1) o filtro "O que vou mandar?" (o mesmo da tela PRODUTOS)  2) marcar os produtos
    3) conferir e mandar. Os escolhidos (prod=...) vão na cesta de uma tela para outra."""
    marcados = list(dict.fromkeys(p for p in request.query_params.getlist("prod") if p))
    tem_filtro = bool(busca.strip() or cat or f_cat or f_preco or todos)
    if not passo:  # com filtro = marcar; só com produto (veio da tela do produto) = conferir
        passo = "2" if tem_filtro else ("3" if marcados else "1")
    todas_cats = categorias.com_nome(s.db)
    nomes = categorias.nomes(todas_cats)
    cesta = produtos.para_mandar(s.db, marcados)  # os já escolhidos que ainda têm no estoque
    produtos.marcar_fotos(s.db, cesta)
    ids_cesta = [p["id"] for p in cesta]
    # o filtro que está valendo, para voltar à mesma lista depois
    filtro_campos = {"busca": busca.strip(), "cat": request.query_params.get(f"f_sub_{f_cat}") or f_cat or cat,
                     "f_preco": f_preco, "todos": todos}

    if passo == "3":  # conferir e mandar
        voltar = _endereco_mandar(filtro_campos, ids_cesta, "2") if tem_filtro else _endereco_mandar({}, ids_cesta, "1")
        if not cesta:
            return ir_com_erro(_endereco_mandar(filtro_campos if tem_filtro else {}, [], "2" if tem_filtro else "1"),
                               "Toque em pelo menos um produto.")
        if len(cesta) > MAX_MANDAR:
            return ir_com_erro(voltar, f"Escolha no máximo {MAX_MANDAR} produtos de cada vez.")
        grupos: dict[str, list] = {}
        for p in cesta:
            grupos.setdefault(nomes.get(p["categoria_id"], "Sem categoria"), []).append(p)
        msg = produtos.mensagem_o_que_tenho(configuracoes.nome_loja(configuracoes.ler(s.db)), grupos)
        return pagina(request, "produtos/mandar_ver.html", msg=msg, link=util.link_whatsapp("", msg),
                      itens=cesta, com_foto=[p for p in cesta if p["fotos"]], total=len(cesta),
                      voltar=voltar, escolhidas=tem_filtro, outras=_endereco_mandar({}, ids_cesta, "1"))

    em_estoque = produtos.em_estoque(s.db)
    if passo != "2":  # 1) o filtro (a cesta continua embaixo)
        return pagina(request, "produtos/mandar_escolher.html", categorias=categorias.com_produtos(todas_cats, em_estoque),
                      resumo={"produtos": len(em_estoque), "unidades": sum(p["quantidade"] for p in em_estoque)},
                      cesta=cesta, max_mandar=MAX_MANDAR, ver_todos=_endereco_mandar({"todos": "1"}, ids_cesta, "2"))

    # 2) marcar os produtos que o filtro achou (só os que têm no estoque)
    itens = ([p for p in produtos.listar(s.db, busca) if p["quantidade"] > 0 or p.get("servico")] if busca.strip()
             else em_estoque)
    itens, filtro, preco_max = _filtrar(request, todas_cats, itens, cat, f_cat, f_preco)
    if not itens:
        return ir_com_erro(_endereco_mandar({}, ids_cesta, "1"), "Nada no estoque com esse filtro. Tente outro.")
    produtos.marcar_fotos(s.db, itens)
    grupos = {}
    for p in sorted(itens, key=lambda p: (nomes.get(p["categoria_id"], "~"), p["nome"].lower())):
        grupos.setdefault(nomes.get(p["categoria_id"], "Sem categoria"), []).append(p)
    campos = dict(filtro_campos, cat=filtro["id"] if filtro else "", f_preco=preco_max or "", todos="1")
    # etiquetas dos filtros ligados, cada uma com o endereço sem ela (o ✕), igual à tela PRODUTOS
    etiquetas = [(texto, _endereco_mandar(dict(campos, **{chave: ""}), ids_cesta, "2"))
                 for texto, chave in ((f'🔎 "{busca.strip()}"', "busca"),
                                      (f"{filtro['icone']} {filtro['nome_completo']}" if filtro else "", "cat"),
                                      (f"Até R$ {preco_max},00" if preco_max else "", "f_preco"))
                 if campos[chave] and texto]
    aqui = {p["id"] for p in itens}
    return pagina(request, "produtos/mandar_marcar.html", grupos=grupos, total=len(itens), etiquetas=etiquetas,
                  filtro_campos=campos,
                  max_mandar=MAX_MANDAR, cesta=cesta, marcados={i for i in ids_cesta if i in aqui},
                  cat_principal=filtro["caminho"][0]["id"] if filtro and filtro.get("caminho") else "",
                  voltar=_endereco_mandar({}, ids_cesta, "1"))


def _endereco_mandar(filtro: dict, marcados: list[str], passo: str) -> str:
    """Endereço do Mandar o que tenho levando o filtro, os produtos escolhidos e o passo."""
    campos = [(k, v) for k, v in filtro.items() if v] + [("prod", p) for p in marcados] + ([("passo", passo)] if passo else [])
    return "/mandar-o-que-tenho" + (f"?{urlencode(campos)}" if campos else "")


@router.get("/produtos/{pid}/foto.jpg")
def foto_principal_arquivo(s: Membro, pid: str, baixar: str = ""):
    """A foto principal do produto, do nosso endereço (para o celular compartilhar no WhatsApp)."""
    p = produtos.buscar(s.db, pid, "nome")
    conteudo = produtos.arquivo_foto_principal(s.db, pid) if p else None
    if not conteudo:
        return Response(status_code=404)
    nome = util.nome_de_arquivo(p["nome"]) + ".jpg"
    jeito = "attachment" if baixar else "inline"
    return Response(conteudo, media_type="image/jpeg", headers={
        "Content-Disposition": f"{jeito}; filename=\"{nome}\"", "Cache-Control": "private, max-age=600"})


@router.get("/produtos-lista-whatsapp")
def lista_whatsapp_endereco_antigo(s: Membro):
    return ir("/mandar-o-que-tenho")
