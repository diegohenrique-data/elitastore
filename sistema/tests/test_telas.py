"""Confere que as telas abrem sem erro (com dados de exemplo, sem tocar no banco)."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core import util
from app.core.web import templates
from app.main import app
from app.core.web import PASTA_APP

PASTA_STATIC = PASTA_APP / "static"
from app.models import vendas as vendas_model
from app.models.vendas import FORMAS
from app.models.vendas import recibo as texto_recibo

cliente_http = TestClient(app)


class PedidoFalso:
    query_params: dict = {}

    def __init__(self):
        self.query_params = {}
        self.url = SimpleNamespace(path="/", query="")


def render(nome, **ctx):
    ctx.setdefault("s", SimpleNamespace(e_dona=True, nome="Elita Teste", usuario_id="u1"))
    ctx.setdefault("ok", None)
    ctx.setdefault("erro", None)
    ctx["u"] = util
    ctx["request"] = PedidoFalso()
    html = templates.env.get_template(nome).render(**ctx)
    assert "</html>" in html
    return html


SALDO = {"cliente_id": "c1", "nome": "Maria Teste", "whatsapp": "11999998888",
         "falta_total": "230.00", "atrasado": "30.00", "hoje": "100.00", "proximo_vencimento": "2026-10-06"}
PARCELA = {"id": "p1", "vencimento": "2026-10-06", "valor": "100", "pago": "70", "falta": "30.00", "situacao": "atrasada"}
PRODUTO = {"id": "x1", "nome": "Perfume", "preco": "89.90", "quantidade": 2, "estoque_minimo": None,
           "validade": None, "codigo_barras": None, "categoria_id": None, "avisos": ["Acabando"]}


def test_sem_login_vai_para_entrar():
    for url in ["/", "/vender", "/receber", "/produtos", "/encomendas", "/meu-dinheiro"]:
        r = cliente_http.get(url, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/entrar", url


def test_tela_entrar_abre():
    r = cliente_http.get("/entrar")
    assert r.status_code == 200 and "ENTRAR" in r.text
    assert cliente_http.get("/primeiro-acesso").status_code == 200
    assert cliente_http.get("/static/estilo.css").status_code == 200


def test_todas_as_telas_renderizam():
    estoque = {"acabou": [], "acabando": [PRODUTO], "vencendo": [], "parados": []}
    assert "MEU DINHEIRO" in render("inicio/inicio.html", saudacao="Bom dia", hoje_qtd=1, hoje_valor=Decimal(100),
                                    atrasados_qtd=1, atrasados_valor=Decimal(30), chegaram=1, estoque=estoque,
                                    vendas_qtd=2, vendas_valor=Decimal(300))
    # PESSOAS: o mesmo filtro da Nova venda (busca + abecedário), só as 6 últimas cadastradas à vista
    html = render("clientes/lista.html", lista=[dict(SALDO, letra="M", recente=True, mexida="2026-10-28T12:00:00+00:00")],
                  busca="", letras_clientes={"M"})
    assert 'id="abrir-letras"' in html and 'id="folha-letras"' in html and "Pessoas com a letra" in html
    assert 'data-mexida="2026-10-28T12:00:00+00:00" data-recente="1"' in html and "Últimas pessoas que você mexeu" in html
    assert 'data-letra="Z" disabled' in html
    render("clientes/form.html", c={}, volta="")
    html = render("clientes/ficha.html", c={"id": "c1", "nome": "Maria Teste", "whatsapp": "1199", "endereco": "Rua A",
                                     "observacoes": ""}, saldo=SALDO, parcelas=[PARCELA], abertas=[PARCELA],
                  pagamentos=[{"pago_em": "2026-10-16", "forma": "pix", "valor": "70"}],
                  ajustes=[{"tipo": "valor", "antes": "R$ 30,00", "depois": "R$ 40,00", "feito_em": "2026-10-16", "motivo": ""}],
                  cobrar=Decimal(130), link_cobrar="https://wa.me/x", FORMAS=FORMAS,
                  compras=[{"id": "v1", "total": "150.00", "forma_pagamento": "fiado", "vezes": 3, "data": date(2025, 3, 10),
                            "itens_texto": "2 blusas", "antiga": True}], total_compras=Decimal(150))
    assert "ELA PAGOU" in html and "AJUSTAR VALOR" in html
    # HISTÓRICO DE COMPRAS e a COMPRA ANTIGA
    assert "Histórico de compras" in html and "2 blusas" in html and "📜 antiga" in html and "/vender/feita/v1" in html
    assert "/clientes/c1/compra-antiga" in html and "10/03/2025" in html  # de outro ano: com o ano
    # a COMPRA ANTIGA é a mesma tela da Nova venda (filtro de produtos + carrinho), com a data e o "ainda deve"
    prod_acabou = dict(PRODUTO, quantidade=0, preco_texto="89,90", categoria="Perfumes", categorias_ids="pf")
    html = render("vender/nova.html", antiga={"id": "c1", "nome": "Maria"}, hoje=date(2026, 10, 28),
                  produtos=[prod_acabou], produto="", pessoas=[{"id": "c1", "nome": "Maria", "whatsapp": "", "letra": "M",
                  "recente": True}], letras_clientes={"M"}, cliente="c1", descricao="", preco="", encomenda="",
                  volta="/clientes/c1/compra-antiga", dia_padrao=28, vendas_hoje=[], total_hoje=0, FORMAS=FORMAS,
                  categorias=[{"id": "pf", "nome": "Perfumes", "nome_completo": "Perfumes", "nivel": 0,
                               "categoria_pai_id": None, "icone": "🧴"}])
    assert 'action="/clientes/c1/compra-antiga"' in html and 'name="quando"' in html and 'max="2026-10-28"' in html
    assert 'name="ainda_deve"' in html and "GUARDAR COMPRA ANTIGA" in html and "Vendas de hoje" not in html
    assert 'id="abrir-filtros"' in html and 'id="folha-filtros"' in html and 'id="carrinho"' in html
    assert 'data-estoque="0"' in html  # não olha o estoque de hoje
    render("clientes/ajustar.html", c={"id": "c1", "nome": "Maria"}, falta="30.00")
    render("clientes/mudar_data.html", c={"id": "c1", "nome": "Maria"}, abertas=[PARCELA])
    prod = dict(PRODUTO, preco_texto="89,90", categoria="Perfumes › Boticário", categorias_ids="pf bo")
    venda_hoje = {"id": "v1", "total": "179.80", "forma_pagamento": "fiado", "vezes": 3, "cliente_nome": "Maria",
                  "itens_texto": "2x Perfume", "hora": "14:30"}
    html = render("vender/nova.html", produtos=[prod], produto="",
                  pessoas=[{"id": "c1", "nome": "Maria", "whatsapp": "1199", "letra": "M"}], letras_clientes={"M"},
                  cliente="c1", descricao="", preco="",
                  encomenda="", volta="/vender", dia_padrao=16, FORMAS=FORMAS,
                  vendas_hoje=[venda_hoje], total_hoje=Decimal("179.80"),
                  categorias=[{"id": "pf", "nome": "Perfumes", "nome_completo": "Perfumes", "nivel": 0, "categoria_pai_id": None,
                               "icone": "🧴"},
                              {"id": "bo", "nome": "Boticário", "nome_completo": "Perfumes › Boticário", "nivel": 1,
                               "categoria_pai_id": "pf", "icone": "B"}])
    # painel de FILTROS (sobe de baixo): categoria, tipo (subcategoria da escolhida) e preço
    assert 'id="abrir-filtros"' in html and 'id="folha-filtros" role="dialog"' in html
    assert 'name="f_cat" value="pf" data-nome="Perfumes"' in html
    assert 'class="filtro-secao filtro-sub oculto" data-pai="pf"' in html and 'value="bo" data-nome="Perfumes › Boticário"' in html
    assert "Até R$ 100" in html and "Ver produtos" in html and "Limpar" in html and "bolha-cat" not in html
    # LEITOR DE CÓDIGO DE BARRAS: o código do produto vai na lista e o aviso da leitura aparece em cima
    assert f'data-codigo="{PRODUTO["codigo_barras"] or ""}"' in html and 'id="aviso-codigo"' in html
    assert "ler o código de barras" in html
    assert 'id="ler-camera"' in html and "/static/camera.js" in html  # câmera do celular
    # reconhece o aparelho (iPhone, Android, Xiaomi...) em todas as telas; cores sempre claras
    assert "window.aparelho" in html and "com-camera" in html and "viewport-fit=cover" in html
    assert 'content="light only"' in html and "so-camera" in html
    # o Ctrl+J do leitor (fim da leitura) não abre os downloads do Chrome: vale em todas as telas
    assert 'e.code === "KeyJ"' in html and "e.preventDefault()" in html
    # ordem: cliente > produto > pagamento
    assert html.index('id="etapa-cliente"') < html.index('id="etapa-produto"') < html.index('id="etapa-pagamento"')
    assert "Nova venda" in html and "CADASTRAR VENDA" in html and "Resumo da venda" in html
    # fiado pago 2 vezes no mês: segundo dia (dia_padrao 16 -> sugere dia 26)
    assert "2 vezes no mês" in html and 'name="dia2"' in html and '<option value="26" selected>dia 26</option>' in html
    assert "CADASTRAR CLIENTE NOVA" not in html  # cliente nova se cadastra só em PESSOAS
    # abecedário: M tem cliente; A não tem (fica apagada)
    assert 'id="folha-letras"' in html and 'data-letra="M">M</button>' in html
    assert 'data-letra="A" disabled' in html and 'data-letra="M"' in html
    assert "Últimos produtos vendidos" not in html and "mais-produtos" in html  # produtos só aparecem buscando
    assert html.count("AVANÇAR ➜") == 2 and html.count("⬅ VOLTAR") == 2  # uma telinha por etapa
    assert "COLOCAR NO CARRINHO" in html and "ADICIONAR MAIS PRODUTOS" in html and 'id="carrinho-lista"' in html
    assert 'name="cliente_id" value="c1" data-nome="Maria" required checked' in html and "Balcão" not in html
    assert 'data-preco="89,90"' in html and "Outro produto" not in html
    assert "Vendas de hoje" in html and "1 venda · R$ 179,80" in html
    html = render("vender/nova.html", produtos=[], produto="outro", pessoas=[], cliente="", descricao="Perfume X",
                  preco="150,00", encomenda="e1", volta="/vender?encomenda=e1", dia_padrao=16, FORMAS=FORMAS,
                  vendas_hoje=[], total_hoje=0, s=SimpleNamespace(e_dona=False, nome="Ana", usuario_id="u2"), categorias=[])
    assert 'id="item-inicial" hidden data-nome="Perfume X" data-preco="150,00"' in html  # encomenda entra no carrinho
    assert "Nenhuma cliente cadastrada" in html and "Nenhuma venda hoje" in html
    venda = {"id": "v1", "total": "179.80", "forma_pagamento": "fiado", "dia_pagamento": 10,
             "clientes": {"id": "c1", "nome": "Maria Teste", "whatsapp": ""},
             "venda_itens": [{"descricao": "Perfume", "quantidade": 2, "preco_unitario": "89.90"}],
             "parcelas": [{"numero": 2, "valor": "59.93", "vencimento": "2026-12-10"},
                          {"numero": 1, "valor": "59.94", "vencimento": "2026-11-10"}]}
    recibo = texto_recibo(venda, "ElitaStore")
    assert "Oi, Maria!" in recibo and "2x Perfume: R$ 179,80" in recibo and "1ª parcela: 10/11/2026" in recibo
    assert "todo dia 10" in recibo
    duas = dict(venda, dia_pagamento=5, parcelas=[{"numero": 1, "valor": "89.90", "vencimento": "2026-11-05"},
                                                 {"numero": 2, "valor": "89.90", "vencimento": "2026-11-15"}])
    assert "nos dias 5 e 15" in texto_recibo(duas, "ElitaStore")
    html = render("vender/feita.html", v=venda, c=venda["clientes"], recibo=recibo, link_recibo="#",
                  da_encomenda=True, FORMAS=FORMAS)
    assert "Venda cadastrada!" in html and "MANDAR RECIBO NO WHATSAPP" in html and "NOVA VENDA" in html
    assert "VOLTAR PARA ENCOMENDAS" in html and html.index("1ª") < html.index("2ª")
    com_link = dict(SALDO, link_cobrar="https://api.whatsapp.com/send?phone=5511999998888&text=oi")
    html = render("receber/receber.html", atrasados=[com_link], de_hoje=[dict(com_link, whatsapp="")], proximos=[SALDO])
    # cada atrasada tem o botão de cobrar no WhatsApp; sem WhatsApp, leva para anotar o número
    assert 'id="atrasados"' in html and "COBRAR NO WHATSAPP" in html and "phone=5511999998888" in html
    assert "Sem WhatsApp: anotar o número" in html and html.count("botao-cobrar") == 2
    fem = {"id": "fe", "nome": "Feminino", "nome_completo": "Perfumes › Feminino", "nivel": 1, "qtd": 2,
           "categoria_pai_id": "pf", "icone": "👠"}
    cats_prod = [{"id": "pf", "nome": "Perfumes", "nome_completo": "Perfumes", "nivel": 0, "qtd": 3,
                  "categoria_pai_id": None, "icone": "🧴"}, fem]
    situacoes = [{"valor": "acabando", "nome": "Acabando", "qtd": 2}, {"valor": "vencendo", "nome": "Perto de vencer", "qtd": 0},
                 {"valor": "parado", "nome": "Parado", "qtd": 1}]
    comum = dict(categorias=cats_prod, situacoes=situacoes, resumo={"produtos": 3, "unidades": 9})
    # abre no FILTRO: sem a lista de produtos
    html = render("produtos/lista.html", grupos={"Perfumes › Feminino": [PRODUTO]}, busca="", total=1, unidades=2,
                  filtro=None, preco_max=0, situacao="", etiquetas=[], so_filtro=True, **comum)
    assert "O que eu tenho?" in html and "3 produtos · 9 unidades na loja" in html and "VER PRODUTOS" in html
    assert "🧴" in html and "Perfumes</strong><small>3 produtos" in html and "Tipo de Perfumes" in html
    assert 'name="todos" value="1"' in html  # VER PRODUTOS sem escolher nada mostra todos
    assert "Feminino (2)" in html and "Acabando (2)" in html and "VER TODOS" in html and 'href="/produtos/x1"' not in html
    # MUITAS categorias: só 3 quadrados à vista (sem histórico: as 3 com mais produtos) + "Ver todas";
    # a lista completa (A a Z, com busca) fica no painel. Tipos: 5 + "Ver todos os tipos".
    muitas = [{"id": f"c{i}", "nome": f"Categoria {i:02d}", "nome_completo": f"Categoria {i:02d}", "nivel": 0,
               "categoria_pai_id": None, "icone": "C", "qtd": i} for i in range(1, 31)]
    muitas += [{"id": f"t{i}", "nome": f"Tipo {i}", "nome_completo": f"Categoria 01 › Tipo {i}", "nivel": 1,
                "categoria_pai_id": "c1", "icone": "T", "qtd": 1} for i in range(8)]
    html = render("produtos/lista.html", grupos={}, busca="", total=0, unidades=0, filtro=None, preco_max=0,
                  situacao="", etiquetas=[], so_filtro=True, **dict(comum, categorias=muitas))
    assert html.count('class="cat-quadro"') == 3 and html.count('class="cat-quadro oculto"') == 27
    assert "Ver todas as categorias (30)" in html and html.count('class="cat-linha"') == 30 and "Procurar categoria" in html
    visiveis = html.split('class="cat-quadro oculto"')[0]
    assert "Categoria 30" in visiveis and "Categoria 28" in visiveis and "Categoria 27" not in visiveis
    assert "/static/filtro.js" in html and "elita:categorias-recentes" in (PASTA_STATIC / "filtro.js").read_text(encoding="utf-8") and "Toque de novo para desmarcar" in html
    assert "Ver todos os tipos (8)" in html and html.count("seg-op extra oculto") == 3
    # depois de filtrar: busca + painel de Filtros (igual ao da Nova venda), etiquetas com ✕ e a lista
    html = render("produtos/lista.html", grupos={"Perfumes › Feminino": [PRODUTO]}, busca="", total=1, unidades=2,
                  filtro=fem, preco_max=100, situacao="acabando", so_filtro=False,
                  etiquetas=[("📁 Perfumes › Feminino", "/produtos?f_preco=100"), ("Até R$ 100,00", "/produtos?cat=fe")],
                  **comum)
    assert 'href="/produtos/x1"' in html and "2 unidades" in html and "VOLTAR PARA O FILTRO" in html
    assert 'class="vitrine"' in html and "Sem foto" in html and "Tenho 2" in html  # vitrine (sem foto ainda)
    # vitrine com fotos: com 3 fotos aparecem as setinhas ‹ › e os pontinhos; com 1 foto, sem setinhas
    com3 = dict(PRODUTO, fotos=["https://x/1.jpg", "https://x/2.jpg", "https://x/3.jpg"])
    com1 = dict(PRODUTO, id="x2", nome="Batom", fotos=["https://x/9.jpg"])
    vit = render("produtos/lista.html", grupos={"Perfumes › Feminino": [com3, com1]}, busca="", total=2, unidades=4,
                  filtro=None, preco_max=0, situacao="", so_filtro=False, etiquetas=[], **comum)
    assert vit.count(' data-carrossel>') == 1 and vit.count('class="vitrine-seta anterior"') == 1
    assert 'aria-label="Próxima foto de Perfume"' in vit and "Próxima foto de Batom" not in vit
    assert vit.count('src="https://x/') == 4 and "Sem foto" not in vit and vit.count('class="atual"') == 1
    assert 'id="abrir-filtros"' in html and 'id="folha-filtros" role="dialog"' in html
    assert 'name="f_cat" value="pf" data-nome="Perfumes"' in html and "Até R$ 100" in html
    assert 'href="/produtos?f_preco=100"' in html and 'name="f_situacao" value="acabando"' in html
    roupas = {"id": "r", "nome": "Roupas", "categoria_pai_id": None, "nome_completo": "Roupas"}
    blusas = {"id": "b", "nome": "Blusas", "categoria_pai_id": "r", "nome_completo": "Roupas › Blusas"}
    roupas["caminho"], blusas["caminho"] = [roupas], [roupas, blusas]
    assert "Criar categoria" in render("produtos/categoria_escolher.html", atual=None, filhas=[])
    html = render("produtos/categoria_escolher.html", atual=blusas, filhas=[])
    assert "COLOCAR O PRODUTO AQUI" in html and "Criar subcategoria dentro de Blusas" in html
    html = render("produtos/categoria_escolher.html", atual=roupas, filhas=[blusas])
    assert "Criar outra subcategoria dentro de Roupas" in html and "Blusas" in html
    html = render("produtos/categoria_escolher.html", atual=blusas, filhas=[])
    assert "APAGAR A CATEGORIA BLUSAS" in html and "⬅ VOLTAR" in html and "🏠 INÍCIO" in html
    html = render("receber/receber.html", atrasados=[], de_hoje=[], proximos=[])
    assert "🏠 INÍCIO" in html and "⬅ VOLTAR" not in html
    assert "APAGAR A CATEGORIA" not in render("produtos/categoria_escolher.html", atual=blusas, filhas=[],
                                              s=SimpleNamespace(e_dona=False, nome="Ana", usuario_id="u2"))
    assert "SIM, APAGAR" in render("produtos/categoria_apagar.html", cat=blusas, filhas=0, produtos=0)
    html = render("produtos/categoria_apagar.html", cat=roupas, filhas=1, produtos=2)
    assert "SIM, APAGAR" not in html and "1 subcategoria" in html and "2 produtos" in html
    html = render("produtos/form.html", p={"categoria_id": "b"}, cats=[roupas, blusas], categoria=blusas,
                  max_fotos=3)
    assert "Roupas › Blusas" in html and "Passo 2 de 2" in html
    assert "Código de barras (opcional)" in html and 'id="codigo-barras"' in html
    assert "LER CÓDIGO DE BARRAS" in html and "/static/camera.js" in html
    # FOTOS no cadastro: tirar foto (celular) ou escolher da galeria/computador, dentro do formulário
    assert 'enctype="multipart/form-data"' in html and "TIRAR FOTO" in html and 'capture="environment"' in html
    assert "ESCOLHER DA GALERIA" in html and "ESCOLHER FOTO DO COMPUTADOR" in html and "/static/fotos.js" in html
    assert 'data-mandar=""' in html and "até 3" in html
    html = render("produtos/form.html", p=dict(PRODUTO, custo="45.00"), cats=[roupas, blusas], categoria=None,
                  max_fotos=3)
    assert "APAGAR ESTE PRODUTO" in html
    assert "ainda não tem foto" in html and 'action="/produtos/x1/fotos"' in html and 'data-mandar="sim"' in html
    # produto com fotos: a 1ª é a principal; as outras podem virar principal; a dona apaga
    fotos = [{"id": f"f{i}", "url": f"https://x/{i}.jpg", "ordem": i} for i in (1, 2)]
    html = render("produtos/form.html", p=dict(PRODUTO, fotos=fotos), cats=[roupas, blusas], categoria=None,
                  max_fotos=3)
    assert "2 de 3" in html and html.count("⭐ Principal") == 1 and html.count("Pôr como principal") == 1
    assert html.count("🗑️ Apagar") == 2 and 'data-max="1"' in html and 'data-tem-principal="sim"' in html
    cheio = [{"id": f"f{i}", "url": "", "ordem": i} for i in (1, 2, 3)]
    html = render("produtos/form.html", p=dict(PRODUTO, fotos=cheio), cats=[roupas, blusas], categoria=None,
                  max_fotos=3, s=SimpleNamespace(e_dona=False, nome="Ana", usuario_id="u2"))
    assert "o máximo" in html and "TIRAR FOTO" not in html and "🗑️ Apagar" not in html
    html = render("produtos/form.html", p=dict(PRODUTO), cats=[roupas, blusas], categoria=None,
                  max_fotos=3, s=SimpleNamespace(e_dona=False, nome="Ana", usuario_id="u2"))
    assert "APAGAR ESTE PRODUTO" not in html
    html = render("produtos/apagar.html", p=PRODUTO, vendas=2, categoria="Perfumes")
    assert "SIM, APAGAR" in html and "2 vezes" in html and "continuam guardadas" in html
    enc = {"id": "e1", "descricao": "Perfume Asad", "etapa": "chegou", "clientes": {"nome": "Maria"},
           "preco": "180", "sinal": "50", "link_avisar": "#", "link_entregar": "#",
           "entregue_em": None}
    render("encomendas/lista.html", grupos={"pedido": [dict(enc, etapa="pedido")], "chegou": [enc],
                                      "entregue": [dict(enc, etapa="entregue", entregue_em="2026-10-16")]})
    # passo 1: o MESMO filtro da tela PRODUTOS (quadrados de categoria, tipo, preço), sem pastinhas
    filtro_mandar = dict(categorias=cats_prod, resumo={"produtos": 3, "unidades": 9}, max_mandar=30,
                         ver_todos="/mandar-o-que-tenho?todos=1&passo=2")
    html = render("produtos/mandar_escolher.html", cesta=[], **filtro_mandar)
    assert "O que vou mandar?" in html and "3 produtos no estoque para escolher" in html and "Passo 1 de 3" in html
    assert 'class="cat-quadro"' in html and "Tipo de Perfumes" in html and "Até R$ 100" in html and "📁" not in html
    assert 'name="f_situacao"' not in html and "/static/filtro.js" in html and "VER TODOS" in html and "cesta" not in html
    # passo 2: marcar produto por produto, vendo a foto (sem foto mostra "Sem foto")
    asad = dict(PRODUTO, id="a1", nome="Asad", fotos=["https://x/a.jpg"])
    yara = dict(PRODUTO, id="y1", nome="Yara", fotos=[])
    filtro_campos = {"busca": "", "cat": "pf", "f_preco": "", "todos": "1"}
    html = render("produtos/mandar_marcar.html", grupos={"Perfumes": [asad, yara]}, total=2, max_mandar=30,
                  cesta=[], marcados=set(), voltar="/mandar-o-que-tenho", filtro_campos=filtro_campos,
                  etiquetas=[("📁 Perfumes", "/mandar-o-que-tenho?todos=1&passo=2")], cat_principal="pf")
    assert 'href="/mandar-o-que-tenho?todos=1&amp;passo=2"' in html and "📁 Perfumes ✕" in html
    assert html.count('type="checkbox" name="prod"') == 2 and 'name="cat" value="pf"' in html and 'src="https://x/a.jpg"' in html
    assert "Sem foto" in html and "Marcar todos" in html and "VER ANTES DE MANDAR" in html and "Passo 2 de 3" in html
    assert "Nenhum produto escolhido ainda" in html and 'class="cesta vazia"' in html and "ESCOLHER OUTROS PRODUTOS" in html
    # CESTA com produtos de várias categorias: o desta tela vem marcado; o de outra categoria vai escondido
    blusa = dict(PRODUTO, id="b1", nome="Blusa", fotos=["https://x/b.jpg"])
    html = render("produtos/mandar_marcar.html", grupos={"Perfumes": [asad, yara]}, total=2, max_mandar=30,
                  cesta=[asad, blusa], marcados={"a1"}, voltar="/mandar-o-que-tenho?prod=a1&prod=b1&passo=1",
                  filtro_campos=filtro_campos, etiquetas=[], cat_principal="")
    assert "2 produtos escolhidos" in html and 'value="a1" checked' in html and 'value="y1">' in html
    assert 'type="hidden" name="prod" value="b1"' in html and 'type="hidden" name="prod" value="a1"' not in html
    assert 'aria-label="Tirar Blusa"' in html and 'name="passo" value="3"' in html and 'name="passo" value="1"' in html
    html = render("produtos/mandar_escolher.html", cesta=[blusa], **filtro_mandar)
    assert "O que mais vai junto?" in html and 'type="hidden" name="prod" value="b1"' in html and "1 produto escolhido" in html
    # passo 3: as fotos que vão junto (foto limpa) + o texto separado; com foto: compartilhar e baixar
    msg = "Loja\n\n*Perfumes*\n• Asad: R$ 180,00\n• Yara: R$ 170,00"
    html = render("produtos/mandar_ver.html", msg=msg, link="https://wa.me/?text=x", itens=[asad, yara], com_foto=[asad],
                  total=2, voltar="/mandar-o-que-tenho?cat=pf", escolhidas=["pf"], outras="/mandar-o-que-tenho?passo=1")
    assert "1 foto vai junto" in html and 'data-foto="/produtos/a1/foto.jpg"' in html and "foto.jpg?baixar=1" in html
    assert "1 sem foto" in html and "MANDAR SÓ O TEXTO" in html and 'id="mandar-com-fotos"' in html and "navigator.share" in html
    assert "MUDAR OS PRODUTOS" in html and "JUNTAR PRODUTOS DE OUTRA CATEGORIA" in html and "Passo 3 de 3" in html and "Yara: R$ 170,00" in html
    # um produto só (vindo da tela do produto), sem foto: só o texto, sem compartilhar
    html = render("produtos/mandar_ver.html", msg=msg, link="https://wa.me/?text=x", itens=[yara], com_foto=[],
                  total=1, voltar="/mandar-o-que-tenho", escolhidas=[], outras="/mandar-o-que-tenho?prod=y1&passo=1")
    assert "MANDAR SÓ O TEXTO" in html and "mandar-com-fotos" not in html and "Passo" not in html
    html = render("encomendas/form.html", cliente="", pessoas=[])
    assert "fornecedor" not in html.lower()  # FORNECEDORES saiu do sistema (28/10/2026)
    render("dinheiro/meu_dinheiro.html", mes="outubro", entrou=Decimal(1), fiado=Decimal(2), atrasado=Decimal(1),
           vai_entrar=Decimal(3), gastei=Decimal(4), vendi=Decimal(5), na_hora=Decimal(2), no_fiado=Decimal(3),
           mercadoria=Decimal(9), gastos=[{"descricao": "frete", "gasto_em": "2026-10-16", "valor": "20"}],
           lucro={"lucro": Decimal("120.50"), "sobrou": Decimal("100.50")})
    html = render("dinheiro/meu_dinheiro.html", mes="outubro", entrou=Decimal(1), fiado=Decimal(2), atrasado=Decimal(1),
                  vai_entrar=Decimal(3), gastei=Decimal(4), vendi=Decimal(5), na_hora=Decimal(2), no_fiado=Decimal(3),
                  mercadoria=Decimal(9), gastos=[], lucro={"lucro": Decimal("120.50"), "sobrou": Decimal("100.50")},
                  pessoas_devendo=3)
    assert "Dívidas: tudo que me devem" in html and "3 pessoas devendo" in html and 'href="/meu-dinheiro/dividas"' in html
    assert "Lucro das vendas este mês" in html and "R$ 120,50" in html and "sobrou R$ 100,50" in html
    assert 'href="/meu-dinheiro/custos"' in html and "CUSTOS E LUCRO DE CADA PRODUTO" in html
    html = render("dinheiro/equipe.html", lista=[{"id": "u1", "nome": "Elita", "papel": "dona", "ativo": True, "principal": True},
                                        {"id": "u2", "nome": "Ana", "papel": "ajudante", "ativo": False, "principal": False}])
    assert "CADASTRAR E LIBERAR" in html and "A ajudante pode" in html and "LIBERAR" in html
    assert "Dona principal da loja" in html and "TORNAR DONA" not in html
    assert html.count("EXCLUIR DA EQUIPE") == 1  # só para a ajudante, nunca para a dona principal
    html = render("dinheiro/equipe_excluir.html", p={"id": "u2", "nome": "Ana"})
    assert "SIM, EXCLUIR" in html and "acesso dela (e-mail e senha)" in html
    render("dinheiro/loja.html", cfg={"nome_loja": "Loja", "chave_pix": "", "msg_cobranca": "", "msg_encomenda": "",
                             "dias_parado": 60, "dias_aviso_validade": 30, "estoque_minimo_padrao": 3})
    render("layout/mensagem.html", titulo="Oi", texto="Teste")


def test_ajudante_nao_ve_meu_dinheiro():
    html = render("inicio/inicio.html", s=SimpleNamespace(e_dona=False, nome="Ana", usuario_id="u2"), saudacao="Oi",
                  hoje_qtd=0, hoje_valor=0, atrasados_qtd=0, atrasados_valor=0, chegaram=0,
                  estoque={"acabou": [], "acabando": [], "vencendo": [], "parados": []})
    assert "MEU DINHEIRO" not in html and "Tudo em dia" in html
    assert "VENDER" in html and "Hoje: 0 vendas" in html and "R$" not in html  # ajudante não vê o total


class BancoFalso:
    """Imita o pedaço do Supabase usado em recentes_primeiro (só a lista de vendas)."""
    def __init__(self, vendas):
        self.vendas = vendas

    def table(self, nome):
        return self

    def __getattr__(self, nome):  # select, is_, order, limit... ("not_" é propriedade no Supabase)
        return self if nome == "not_" else (lambda *a, **k: self)

    def execute(self):
        return SimpleNamespace(data=self.vendas)


def test_clientes_recentes_primeiro():
    from app.models.clientes import recentes_primeiro
    pessoas = [{"id": f"c{i}", "nome": f"Cliente {i}", "whatsapp": "", "criado_em": f"2026-10-{i + 10:02d}"}
               for i in range(1, 9)]
    lista = recentes_primeiro(BancoFalso([{"cliente_id": "c2"}, {"cliente_id": "c2"}, {"cliente_id": "c5"}]), pessoas)
    recentes = [p["id"] for p in lista if p.get("recente")]
    # quem comprou por último vem primeiro; completa com as mais novas no cadastro; no máximo 5
    assert recentes == ["c2", "c5", "c8", "c7", "c6"]
    assert len(lista) == 8 and [p["id"] for p in lista[5:]] == ["c1", "c3", "c4"]


def test_carrinho_soma_e_junta_iguais():
    from app.models.vendas import juntar_iguais, total_dos_itens
    itens = [
        {"produto_id": "p1", "descricao": "Perfume", "quantidade": 1, "preco_unitario": Decimal("89.90")},
        {"produto_id": "p2", "descricao": "Colar", "quantidade": 2, "preco_unitario": Decimal("49.95")},
        {"produto_id": "p1", "descricao": "Perfume", "quantidade": 2, "preco_unitario": Decimal("89.90")},
        {"produto_id": "p1", "descricao": "Perfume", "quantidade": 1, "preco_unitario": Decimal("80.00")},  # outro preço
    ]
    juntos = juntar_iguais(itens)
    assert [(i["produto_id"], i["quantidade"]) for i in juntos] == [("p1", 3), ("p2", 2), ("p1", 1)]
    assert total_dos_itens(juntos) == Decimal("449.60")


def test_carrinho_le_os_itens_do_formulario():
    from app.controllers.vender import ler_itens
    banco = BancoFalso([{"nome": "Perfume Asad", "preco": "180.00", "quantidade": 3}])  # o produto p1, como vem do banco
    itens = ler_itens(banco, ["p1", "outro", "outro"], ["nome que vem do banco", "Blusa azul", "Blusa azul"],
                      ["2", "1", "1"], ["", "49,90", "49,90"])
    assert itens == [
        {"produto_id": "p1", "descricao": "Perfume Asad", "quantidade": 2, "preco_unitario": Decimal("180.00"),
         "desconto": Decimal(0)},
        {"produto_id": None, "descricao": "Blusa azul", "quantidade": 2, "preco_unitario": Decimal("49.90"),
         "desconto": Decimal(0)},
    ]
    assert "nome do produto" in ler_itens(banco, ["outro"], [""], ["1"], ["10,00"])
    assert "preço de Blusa" in ler_itens(banco, ["outro"], ["Blusa"], ["1"], [""])
    # REGRA: só vende o que tem no estoque (3), somando as linhas do mesmo produto
    assert "Só tem 3 de Perfume Asad" in ler_itens(banco, ["p1", "p1"], ["", ""], ["2", "2"], ["", "150,00"])
    assert "Tire 1 do carrinho" in ler_itens(banco, ["p1"], [""], ["4"], [""])
    assert isinstance(ler_itens(banco, ["p1"], [""], ["3"], [""]), list)
    # na compra antiga o estoque de hoje não importa
    assert isinstance(ler_itens(banco, ["p1"], [""], ["9"], [""], conferir_estoque=False), list)
    assert "acabou no estoque" in ler_itens(BancoFalso([{"nome": "Batom", "preco": "10", "quantidade": 0}]),
                                            ["p2"], [""], ["1"], [""])


def test_categorias_para_o_filtro_da_venda():
    from app.models.categorias import com_produtos
    from app.models.produtos import para_venda
    cats = [{"id": "pf", "nome": "Perfumes", "categoria_pai_id": None}, {"id": "bo", "nome": "Boticário", "categoria_pai_id": "pf"},
            {"id": "ro", "nome": "Roupas", "categoria_pai_id": None}]
    for c in cats:  # como categorias.com_nome deixa
        c["caminho"] = [cats[0], c] if c["id"] == "bo" else [c]
        c["nome_completo"] = " › ".join(x["nome"] for x in c["caminho"])
        c["nivel"] = len(c["caminho"]) - 1
    banco = BancoFalso([{"id": "p1", "nome": "Malbec", "preco": "199.90", "quantidade": 3, "categoria_id": "bo",
                         "codigo_barras": None}])
    produtos = para_venda(banco, cats)
    assert produtos[0]["categorias_ids"] == "pf bo" and produtos[0]["categoria"] == "Perfumes › Boticário"
    # Roupas não tem produto em estoque: não vira botão
    assert [c["id"] for c in com_produtos(cats, produtos)] == ["pf", "bo"]


def test_icone_da_categoria():
    from app.models.categorias import icone
    assert icone("Perfumes Importados") == "🧴" and icone("Calças") == "👖" and icone("Pratas") == "💍"
    assert icone("Óculos") == "🕶️" and icone("Aliança") == "💍"  # sem ligar para acento
    assert icone("Zebra") == "Z" and icone("[TESTE] Flores") == "T"  # sem ícone conhecido: a primeira letra


def test_letra_inicial_da_cliente():
    from app.models.clientes import inicial, letras_usadas
    assert inicial("Ângela Souza") == "A" and inicial(" maria") == "M" and inicial("Érica") == "E"
    assert inicial("123 Loja") == "L" and inicial("") == "#"
    assert letras_usadas([{"nome": "Ana"}, {"nome": "Ângela"}, {"nome": "Bia"}]) == {"A", "B"}


ROTAS_DO_SISTEMA = """
GET /cep/{numero}
GET /
GET /aguardando
GET /categorias/{cid}/apagar
GET /clientes
GET /clientes/nova
GET /clientes/{cid}
GET /clientes/{cid}/ajustar
GET /clientes/{cid}/compra-antiga
GET /clientes/{cid}/editar
GET /clientes/{cid}/excluir
GET /clientes/{cid}/mudar-data
GET /clientes/{cid}/reparcelar
GET /encomendas
GET /encomendas/nova
GET /entrar
GET /equipe
GET /equipe/{uid}/excluir
GET /loja
GET /mandar-o-que-tenho
GET /meu-dinheiro
GET /meu-dinheiro/custos
GET /meu-dinheiro/dividas
GET /meu-dinheiro/lancamentos
GET /ofertas
GET /ofertas/ver
GET /primeiro-acesso
GET /produtos
GET /produtos-lista-whatsapp
GET /produtos/novo
GET /produtos/novo/dados
GET /produtos/{pid}
GET /produtos/{pid}/apagar
GET /produtos/{pid}/foto.jpg
GET /produtos/{pid}/whatsapp
GET /receber
GET /sair
GET /vender
GET /vender/feita/{vid}
GET /vendas/{vid}/apagar
GET /vender/nova
POST /categorias/nova
POST /categorias/{cid}/icone
POST /categorias/{cid}/apagar
POST /clientes/nova
POST /clientes/{cid}/ajustar
POST /clientes/{cid}/compra-antiga
POST /clientes/{cid}/editar
POST /clientes/{cid}/excluir
POST /clientes/{cid}/voltar-para-lista
POST /clientes/{cid}/mudar-data
POST /clientes/{cid}/reparcelar
POST /clientes/{cid}/pagou
POST /encomendas/nova
POST /encomendas/{eid}/chegou
POST /entrar
POST /equipe/nova
POST /equipe/{uid}/excluir
POST /equipe/{uid}/{acao}
POST /loja
POST /meu-dinheiro/gasto
POST /vendas/{vid}/apagar
POST /pagamentos/{pid}/apagar
POST /meu-dinheiro/gasto/{gid}/apagar
POST /primeiro-acesso
POST /produtos/salvar
POST /produtos/{pid}/apagar
POST /produtos/{pid}/fotos
POST /produtos/{pid}/fotos/{fid}/apagar
POST /produtos/{pid}/fotos/{fid}/principal
POST /vender
"""


def test_todas_as_rotas_existem():
    """MVC: cada endereço do sistema tem o seu controller (nenhum sumiu na reorganização)."""
    from app.controllers import ROTAS
    rotas = {f"{m} {r.path}" for router in ROTAS for r in router.routes for m in r.methods if m in ("GET", "POST")}
    assert rotas == set(ROTAS_DO_SISTEMA.strip().splitlines())


def test_emoji_escolhido_da_categoria():
    """A Elita escolhe o emoji da categoria (os mesmos do WhatsApp) e pode tirar."""
    import json

    from app.models import categorias
    grupos = json.loads((PASTA_STATIC / "emojis.json").read_text(encoding="utf-8"))
    assert [g["icone"] for g in grupos] == ["😀", "🐻", "🍔", "⚽", "🚗", "💡", "🔣", "🏳️"]
    validos = categorias.emojis_validos()
    assert len(validos) > 1500 and {"👗", "🧴", "💍", "👜", "💄", "🇧🇷", "1️⃣"} <= validos and "a" not in validos
    assert "vestido" in dict(e for g in grupos for e in g["emojis"])["👗"]  # nome em português para a busca
    sem = {"id": "r", "nome": "Roupas", "categoria_pai_id": None, "nome_completo": "Roupas", "icone": "👗",
           "icone_escolhido": "", "icone_auto": "👗"}
    com = dict(sem, id="p", nome="Perfumaria", nome_completo="Perfumaria", icone="🌸", icone_escolhido="🌸", icone_auto="🧴")
    sem["caminho"], com["caminho"] = [sem], [com]
    html = render("produtos/categoria_escolher.html", atual=None, filhas=[sem, com])
    assert "📁" not in html and "👗</span>Roupas" in html and "🌸</span>Perfumaria" in html
    assert 'name="icone" value=""' in html and "Escolher um ícone" in html and "/static/emojis.js" in html
    html = render("produtos/categoria_escolher.html", atual=com, filhas=[])
    assert 'action="/categorias/p/icone"' in html and 'name="icone" value="🌸"' in html and "Trocar o ícone" in html
    assert "✕ Tirar o ícone" in html and "volta o automático (🧴)" in html and 'data-mandar="sim"' in html
    html = render("produtos/categoria_escolher.html", atual=sem, filhas=[])
    assert "ícone automático" in html and 'data-automatico="👗"' in html


def test_codigo_de_barras_de_outro_produto():
    from app.models.produtos import dono_do_codigo
    # o código é único: avisa de quem ele já é
    assert dono_do_codigo(BancoFalso([{"id": "p2", "nome": "Batom"}]), "789", exceto="p1") == {"id": "p2", "nome": "Batom"}
    assert dono_do_codigo(BancoFalso([]), "789") is None


def test_pessoas_seis_ultimas_mexidas():
    from app.models import clientes
    saldos = [{"cliente_id": f"c{i}", "nome": f"Pessoa {i}", "whatsapp": ""} for i in range(1, 9)]
    criadas = [{"id": f"c{i}", "criado_em": f"2026-10-{i + 10:02d}T10:00:00+00:00"} for i in range(1, 9)]
    # a c1 (cadastrada primeiro) comprou hoje e a c2 pagou hoje: são as mexidas mais novas
    tabelas = {"clientes_saldo": saldos, "clientes": criadas,
               "vendas": [{"cliente_id": "c1", "vendida_em": "2026-10-28T15:00:00-03:00"}],
               "pagamentos": [{"cliente_id": "c2", "criado_em": "2026-10-28T09:00:00+00:00"}], "ajustes": []}

    class Banco(BancoFalso):
        def table(self, nome):
            self.vendas = tabelas[nome]
            return self
    lista = clientes.para_lista(Banco([]))
    # sem buscar, só as 6 últimas pessoas mexidas ficam à vista, da mais nova para a mais antiga
    assert [p["cliente_id"] for p in lista if p["recente"]] == ["c1", "c2", "c8", "c7", "c6", "c5"]
    assert all(p["letra"] == "P" for p in lista) and len(lista) == 8


def test_compra_antiga_guarda_data_e_so_o_que_falta():
    from app.models import vendas

    class Banco:
        def __init__(self):
            self.guardado = {}
            self.atual = ""

        def table(self, nome):
            self.atual = nome
            return self

        def insert(self, dados):
            self.guardado.setdefault(self.atual, []).append(dados)
            return self

        def update(self, dados):
            self.guardado.setdefault("ligou", []).append(dados)
            return self

        def eq(self, *a):
            return self

        def execute(self):
            return SimpleNamespace(data=[{"id": "v1"}])
    banco = Banco()
    item = {"produto_id": "p1", "descricao": "Blusa", "quantidade": 1, "preco_unitario": Decimal("150.00")}
    vendas.cadastrar(banco, "c1", [item], "fiado", vezes=2, dia=10, vendida_em=date(2025, 3, 10), ainda_deve=Decimal("100.00"))
    # não mexe no estoque: o item nasce sem o produto (o banco não baixa) e o produto é ligado depois
    assert banco.guardado["venda_itens"][0][0]["produto_id"] is None and banco.guardado["ligou"] == [{"produto_id": "p1"}]
    venda = banco.guardado["vendas"][0]
    assert venda["vendida_em"].startswith("2025-03-10T12:00") and venda["observacao"] == vendas.COMPRA_ANTIGA
    assert venda["total"] == "150.00"
    parcelas = banco.guardado["parcelas"][0]
    assert [p["valor"] for p in parcelas] == ["50.00", "50.00"]  # só o que ela ainda deve


def test_cards_do_inicio_vao_direto():
    estoque = {"acabou": [PRODUTO], "acabando": [], "vencendo": [PRODUTO], "parados": [PRODUTO]}
    html = render("inicio/inicio.html", saudacao="Bom dia", hoje_qtd=1, hoje_valor=Decimal(100), atrasados_qtd=1,
                  atrasados_valor=Decimal(30), chegaram=0, estoque=estoque, vendas_qtd=0, vendas_valor=Decimal(0))
    assert 'href="/receber#atrasados"' in html and 'href="/receber#hoje"' in html
    assert 'href="/produtos?f_situacao=acabando"' in html and 'href="/produtos?f_situacao=vencendo"' in html
    assert 'href="/ofertas"' in html  # parados: monta uma oferta (versão 1.8)
    # celular: a tela fica limpa e os avisos vão para o 🔔 sininho (com quantos são)
    assert 'id="abrir-avisos"' in html and 'class="sino-qtd" aria-hidden="true">5<' in html
    assert 'id="folha-avisos"' in html and 'class="avisos avisos-na-tela"' in html


def test_mensagem_de_atraso_no_whatsapp():
    from app.models import clientes
    lista = [dict(SALDO, proximo_vencimento="2026-10-06"), dict(SALDO, atrasado="0", hoje="100.00")]
    clientes.links_de_cobrar({"chave_pix": "11999", "msg_cobranca": "Oi {nome}, hoje é {valor}"}, lista)
    from urllib.parse import unquote
    atrasada = unquote(lista[0]["link_cobrar"])
    assert "phone=5511999998888" in atrasada and "Oi Maria" in atrasada and "atrasado desde 06/10" in atrasada
    assert "R$ 130,00" in atrasada and "11999" in atrasada  # atrasado + o de hoje
    assert "Oi Maria, hoje é R$ 100,00" in unquote(lista[1]["link_cobrar"])  # paga hoje: a mensagem da loja


def test_revisao_de_ux():
    # não guarda duas vezes: o botão vira "⏳ Guardando..." e o 2º toque não manda de novo
    html = render("clientes/form.html", c={}, volta="")
    assert "Guardando..." in html and "dataset.enviando" in html and "data-confirmar" not in html.split("<body>")[0]
    # ficha: COBRAR só para quem deve; sem WhatsApp, leva para anotar o número; VOLTAR vai para Pessoas
    base = dict(c={"id": "c1", "nome": "Maria", "whatsapp": "", "endereco": "", "observacoes": ""}, parcelas=[],
                abertas=[], pagamentos=[], ajustes=[], compras=[], total_compras=Decimal(0), cobrar=Decimal(0),
                link_cobrar="https://wa.me/x", FORMAS=FORMAS)
    em_dia = dict(SALDO, falta_total="0", atrasado="0", hoje="0")
    html = render("clientes/ficha.html", saldo=em_dia, **base)
    assert "📲 COBRAR" not in html and "Sem WhatsApp" not in html and 'href="/clientes"' in html
    html = render("clientes/ficha.html", saldo=SALDO, **base)
    assert "Sem WhatsApp: anotar" in html and "✅ ELA PAGOU</button>" in html
    # tela de erro: sem texto técnico
    html = render("layout/mensagem.html", titulo="Não deu certo", texto="Tente de novo.", detalhe="PGRST116 erro")
    assert "PGRST116" not in html and "Detalhe" not in html


def test_cep_preenche_o_endereco(monkeypatch):
    from app.models import cep
    sao_paulo = {"cep": "01001-000", "logradouro": "Praça da Sé", "bairro": "Sé", "localidade": "São Paulo", "uf": "SP"}
    monkeypatch.setattr(cep, "buscar", lambda numero: sao_paulo)
    campos, erro = cep.resolver("01001-000", "12", False, "qualquer texto")
    assert erro is None and campos == {"cep": "01001000", "numero": "12",
                                       "endereco": "Praça da Sé - Sé, São Paulo - SP, nº 12, CEP 01001-000"}
    # obrigatórios: CEP com 8 números e o número da casa
    assert "8 números" in cep.resolver("123", "12", False, "")[1]
    assert "número da casa" in cep.resolver("01001000", " ", False, "")[1]
    # sem CEP: vale só o que foi escrito
    assert cep.resolver("01001000", "12", True, " Sítio ") == ({"cep": "", "numero": "", "endereco": "Sítio"}, None)
    monkeypatch.setattr(cep, "buscar", lambda numero: None)
    assert "Não achei" in cep.resolver("99999999", "1", False, "")[1]

    def fora(numero):
        raise cep.ForaDoAr
    monkeypatch.setattr(cep, "buscar", fora)
    assert "Não consegui" in cep.resolver("01001000", "1", False, "")[1]


def test_formulario_de_pessoa_com_cep():
    html = render("clientes/form.html", c={}, volta="")
    assert 'name="cep"' in html and 'name="numero"' in html and 'name="sem_cep"' in html
    assert '<textarea name="endereco" id="endereco"' in html and 'id="bloco-endereco"' in html
    assert html.split('id="endereco"')[1].split(">")[0].strip().endswith("disabled")  # sem marcar, não escreve
    html = render("clientes/form.html", c={"id": "c1", "cep": "", "endereco": "Sítio do Lago"}, volta="")
    assert "Sítio do Lago" in html and 'value="1" checked' in html  # pessoa sem CEP: abre com a opção marcada
    html = render("clientes/form.html", c={"id": "c1", "cep": "01001000", "numero": "12", "endereco": "Rua A"}, volta="")
    assert 'value="01001000"' in html and "Rua A" not in html and 'value="1" checked' not in html


def test_olhinho_da_senha():
    html = cliente_http.get("/entrar").text
    assert 'id="ver-senha"' in html and 'aria-label="Mostrar a senha"' in html and 'type="password"' in html


def test_camera_le_so_codigo_de_barras():
    js = (PASTA_STATIC / "camera.js").read_text(encoding="utf-8")
    assert "F.EAN_13" in js and "F.CODE_128" in js and "QR_CODE" not in js and "QR Code" not in js.split("(sem QR Code)")[1]


def test_quem_pode_apagar_venda():
    venda = {"vendido_por": "joao"}
    assert vendas_model.pode_apagar(venda, "joao", False)  # a própria venda
    assert not vendas_model.pode_apagar(venda, "maria", False)  # a venda do Joãozinho, não
    assert not vendas_model.pode_apagar({"vendido_por": "elita"}, "maria", False)  # nem a da Elita
    assert not vendas_model.pode_apagar({"vendido_por": None}, "maria", False)  # sem dono: só a Elita
    assert vendas_model.pode_apagar(venda, "elita", True)  # a Elita apaga todas


def test_telas_de_apagar_venda():
    venda = {"id": "v1", "total": "100", "forma_pagamento": "fiado", "observacao": "", "dia_pagamento": 10,
             "clientes": {"id": "c1", "nome": "Maria"}, "venda_itens": [], "parcelas": []}
    feita = dict(v=venda, c=venda["clientes"], recibo="", link_recibo="#", da_encomenda=False, FORMAS=FORMAS)
    assert "/vendas/v1/apagar" in render("vender/feita.html", pode_apagar=True, **feita)
    assert "/vendas/v1/apagar" not in render("vender/feita.html", pode_apagar=False, **feita)
    tela = dict(v=venda, c=venda["clientes"], FORMAS=FORMAS)
    html = render("vender/apagar.html", pago=Decimal(0), **tela)
    assert "SIM, APAGAR" in html and "voltam para o estoque" in html and "saem do fiado" in html
    # já recebeu: a Elita vê o aviso e pode; a ajudante não tem o botão
    assert "abater as outras parcelas" in render("vender/apagar.html", pago=Decimal(30), **tela)
    ajudante = SimpleNamespace(e_dona=False, nome="João", usuario_id="u2")
    html = render("vender/apagar.html", pago=Decimal(30), s=ajudante, **tela)
    assert "Só a Elita pode apagar" in html and "SIM, APAGAR" not in html
    # compra antiga não mexeu no estoque
    antiga = dict(tela, v=dict(venda, observacao=vendas_model.COMPRA_ANTIGA))
    assert "voltam para o estoque" not in render("vender/apagar.html", pago=Decimal(0), **antiga)


def test_lancamentos_do_mes():
    html = render("dinheiro/lancamentos.html", mes="outubro", FORMAS=FORMAS,
                  vendas=[{"id": "v1", "total": "10", "forma_pagamento": "pix", "vezes": None, "cliente_nome": "Ana",
                           "itens_texto": "1x Blusa", "data": "2026-10-20", "vendedor": "João"}],
                  pagamentos=[{"id": "p1", "valor": "5", "forma": "pix", "pago_em": "2026-10-20", "clientes": {"nome": "Ana"}}])
    assert "/vender/feita/v1" in html and "por João" in html and "/pagamentos/p1/apagar" in html


def test_regra_de_apagar_esta_no_banco():
    pasta = PASTA_APP.parent / "supabase" / "migrations"
    sql = (pasta / "20261031220000_apagar_venda.sql").read_text(encoding="utf-8")
    assert "v.vendido_por is distinct from (select auth.uid())" in sql and "privado.sou_dona()" in sql
    assert vendas_model.COMPRA_ANTIGA in sql  # compra antiga não devolve estoque
    assert "revoke all on function public.apagar_venda(uuid) from public, anon" in sql


def test_validade_nao_aceita_data_passada():
    from datetime import timedelta

    from app.models.produtos import validade_recusada
    hoje = util.hoje()
    ontem, amanha = (hoje - timedelta(days=1)).isoformat(), (hoje + timedelta(days=1)).isoformat()
    assert validade_recusada(ontem) and validade_recusada("data errada")
    assert not validade_recusada(hoje.isoformat()) and not validade_recusada(amanha) and not validade_recusada("")
    # produto já vencido: pode guardar com a data que já tinha, mas não trocar por outra no passado
    assert not validade_recusada(ontem, atual=ontem)
    assert validade_recusada(ontem, atual=(hoje - timedelta(days=9)).isoformat())
    produto = dict(PRODUTO, fotos=[], custo=None)
    html = render("produtos/form.html", p=produto, cats=[], categoria=None, max_fotos=3)
    assert f'min="{hoje.isoformat()}"' in html
    html = render("produtos/form.html", p=dict(produto, validade=ontem), cats=[], categoria=None, max_fotos=3)
    assert f'min="{ontem}"' in html


# ---------------------------------------------------------------------------
# Versão 1.8 (04/11/2026): desconto, serviço, excluir pessoa e ofertas
# ---------------------------------------------------------------------------
def test_desconto_no_produto_e_na_compra_toda():
    from app.controllers.vender import ler_itens
    from app.models.vendas import desconto_recusado, juntar_iguais, total_dos_itens
    banco = BancoFalso([{"nome": "Perfume Asad", "preco": "100.00", "quantidade": 5}])
    itens = ler_itens(banco, ["p1"], [""], ["2"], [""], descontos=["15,00"])
    assert itens[0]["desconto"] == Decimal("15.00")
    assert total_dos_itens(itens) == Decimal("185.00")                       # 2 x 100 - 15
    assert total_dos_itens(itens, Decimal("10")) == Decimal("175.00")        # e mais 10 na compra toda
    assert desconto_recusado(itens, Decimal("10")) == ""
    assert "compra toda" in desconto_recusado(itens, Decimal("186"))        # nunca passa do valor
    assert "Perfume Asad" in desconto_recusado([dict(itens[0], desconto=Decimal("201"))], Decimal(0))
    assert "Confira o desconto" in ler_itens(banco, ["p1"], [""], ["1"], [""], descontos=["abc"])
    # sem a lista de descontos (formulário antigo) continua funcionando
    assert ler_itens(banco, ["p1"], [""], ["1"], [""])[0]["desconto"] == Decimal(0)
    # o mesmo produto em duas linhas: soma a quantidade e o desconto
    juntos = juntar_iguais([dict(itens[0]), dict(itens[0], quantidade=1, desconto=Decimal("5"))])
    assert juntos[0]["quantidade"] == 3 and juntos[0]["desconto"] == Decimal("20.00")


def test_recibo_e_tela_mostram_o_desconto():
    venda = {"id": "v1", "total": "175.00", "desconto": "10.00", "forma_pagamento": "pix", "parcelas": [],
             "clientes": {"id": "c1", "nome": "Maria Teste", "whatsapp": "1199"},
             "venda_itens": [{"descricao": "Perfume", "quantidade": 2, "preco_unitario": "100.00", "desconto": "15.00"}]}
    texto = texto_recibo(venda, "ElitaStore")
    assert "2x Perfume: R$ 185,00 (desconto de R$ 15,00)" in texto
    assert "Desconto na compra: − R$ 10,00" in texto and "*Total: R$ 175,00*" in texto
    html = render("vender/feita.html", v=venda, c=venda["clientes"], recibo=texto, link_recibo="https://wa.me/x",
                  da_encomenda=False, pode_apagar=True, FORMAS=FORMAS)
    assert "desconto de R$ 15,00" in html and "Desconto na compra toda: R$ 10,00" in html


def test_tela_de_vender_tem_desconto_e_servico():
    servico = {"id": "s1", "nome": "Escova", "preco": "60.00", "preco_texto": "60,00", "quantidade": 0, "servico": True,
               "categoria": "Serviços", "categorias_ids": "", "codigo_barras": None}
    html = render("vender/nova.html", antiga=None, produtos=[servico], produto="", categorias=[], pessoas=[],
                  letras_clientes=set(), cliente="", descricao="", preco="", encomenda="", volta="/vender",
                  dia_padrao=10, vendas_hoje=[], total_hoje=0, FORMAS=FORMAS, kit=["s1"], desconto_kit="10,00")
    assert 'id="abrir-desconto"' in html and 'name="desconto"' in html and "item_desconto" in html
    assert "Dar desconto neste produto" in html and 'data-tipo-geral="pct"' in html
    assert 'data-estoque="0"' in html and "✂️ serviço" in html  # serviço: sem limite de estoque
    assert 'id="kit-inicial"' in html and 'data-desconto="10,00"' in html and 'data-id="s1"' in html


def test_servico_nao_tem_estoque():
    from app.models import categorias
    from app.models.vendas import passou_do_estoque
    # o serviço não entra no estoque conferido: vende quantos quiser
    assert passou_do_estoque([{"produto_id": "s1", "descricao": "Escova", "quantidade": 9}], {}) == ""
    assert "acabou" in passou_do_estoque([{"produto_id": "p1", "descricao": "Batom", "quantidade": 1}], {"p1": 0})
    cat = {"id": "c", "nome": "Unhas", "tipo": "produto"}
    pai = {"id": "p", "nome": "Serviços", "tipo": "produto"}
    assert categorias.e_de_servico(dict(cat, caminho=[pai, cat]))
    assert not categorias.e_de_servico(dict(cat, caminho=[cat]))
    assert categorias.e_de_servico({"nome": "Beleza", "tipo": "servico"})
    # o cadastro: escolha Produto/Serviço, os campos de estoque somem e o lucro aparece
    cat_servico = {"id": "c", "nome": "Serviços", "nome_completo": "Serviços", "icone": "✂️"}
    html = render("produtos/form.html", p={"categoria_id": "c"}, cats=[], categoria=cat_servico, max_fotos=3,
                  servico_padrao=True)
    assert 'name="servico" value="1" checked' in html and 'id="campos-estoque"' in html and "GUARDAR SERVIÇO" in html
    assert 'id="lucro"' in html and "Qual é o meu custo?" in html
    html = render("produtos/form.html", p=dict(PRODUTO, servico=False, custo=None, fotos=[]), cats=[], categoria=None,
                  max_fotos=3, servico_padrao=False)
    assert 'name="servico" value="" checked' in html and "GUARDAR PRODUTO" in html
    html = render("produtos/lista.html", grupos={"Serviços": [dict(PRODUTO, servico=True, quantidade=0, fotos=[])]},
                  busca="", total=1, unidades=0, categorias=[], filtro=None, preco_max=0, situacao="", situacoes=[],
                  resumo={"produtos": 1, "unidades": 0}, etiquetas=[], cat_principal="", so_filtro=False)
    assert "✂️ Serviço" in html and "Sem estoque" not in html and "MONTAR OFERTA" in html


def test_excluir_pessoa():
    c = {"id": "c1", "nome": "Maria Teste", "whatsapp": "1199"}
    html = render("clientes/excluir.html", c=c, falta="0", compras=2)
    assert "SIM, EXCLUIR" in html and "continuam guardadas" in html
    html = render("clientes/excluir.html", c=c, falta="0", compras=0)
    assert "vai ser <strong>apagado</strong>" in html
    html = render("clientes/excluir.html", c=c, falta="50.00", compras=1)
    assert "ainda deve" in html and "SIM, EXCLUIR" not in html
    base = dict(saldo=SALDO, parcelas=[], abertas=[], pagamentos=[], ajustes=[], cobrar=Decimal(0),
                link_cobrar="", FORMAS=FORMAS, compras=[], total_compras=Decimal(0))
    html = render("clientes/ficha.html", c=dict(c, endereco="", observacoes="", ativo=True), **base)
    assert "EXCLUIR DA MINHA LISTA" in html and "TRAZER DE VOLTA" not in html
    html = render("clientes/ficha.html", c=dict(c, endereco="", observacoes="", ativo=False), **base)
    assert "TRAZER DE VOLTA" in html and "EXCLUIR DA MINHA LISTA" not in html
    html = render("clientes/ficha.html", c=dict(c, endereco="", observacoes="", ativo=True),
                  s=SimpleNamespace(e_dona=False, nome="Ajudante", usuario_id="u2"), **base)
    assert "EXCLUIR DA MINHA LISTA" not in html  # só a Elita exclui


def test_oferta_conta_e_mensagem():
    from app.models import ofertas
    itens = [{"id": "a", "nome": "Perfume", "preco": "120.00"}, {"id": "b", "nome": "Colar", "preco": "80.00"}]
    conta = ofertas.calcular(itens, "pct", Decimal("20"))
    assert conta == {"de": Decimal("200.00"), "por": Decimal("160.00"), "economia": Decimal("40.00"), "pct": 20}
    conta = ofertas.calcular(itens, "kit", Decimal("149.90"))
    assert conta["por"] == Decimal("149.90") and conta["economia"] == Decimal("50.10") and conta["pct"] == 25
    assert "menor que R$ 200,00" in ofertas.calcular(itens, "kit", Decimal("200"))
    assert "menor que 100%" in ofertas.calcular(itens, "pct", Decimal("100"))
    assert "Escreva" in ofertas.calcular(itens, "pct", None)
    msg = ofertas.mensagem("ElitaStore", "Kit Dia das Mães", itens, conta, "2026-11-08")
    assert "🎁 *Kit Dia das Mães* · ElitaStore" in msg and "• Perfume: ~R$ 120,00~" in msg
    assert "De ~R$ 200,00~ por *R$ 149,90*" in msg and "economiza R$ 50,10 (25% de desconto)" in msg
    assert "Só até" in msg
    assert "Oferta especial" in ofertas.mensagem("ElitaStore", "", itens, conta)


def test_telas_da_oferta():
    parado = dict(PRODUTO, id="p1", dias=95, fotos=[])
    outro = dict(PRODUTO, id="p2", nome="Colar", fotos=[])
    html = render("produtos/ofertas_montar.html", parados=[parado], outros=[outro],
                  campos={"prod": ["p2"], "nome": "", "tipo": "pct", "valor": "", "ate": ""}, marcados={"p2"},
                  dias_parado=60, max_oferta=20, hoje=date(2026, 11, 4), categorias=[], busca="", filtrando=False,
                  achados=0, etiquetas=[], filtro=None, preco_max=0, cat_principal="")
    assert "Parados há muito tempo" in html and "95 dias parado" in html and "mais de 60 dias" in html
    assert 'name="prod" form="oferta" value="p2" data-preco="89.90" checked' in html
    assert 'name="tipo" form="oferta" value="kit"' in html and "VER A OFERTA" in html
    # o MESMO filtro do sistema (busca + ⚙️ Filtros) para juntar outros produtos, sem perder a oferta
    assert 'id="filtro"' in html and 'id="abrir-filtros"' in html and 'id="folha-filtros"' in html
    assert "/static/filtro.js" in html and 'data-limpar-aqui="1"' in html and 'action="/ofertas#juntar"' in html
    html = render("produtos/ofertas_montar.html", parados=[], outros=[outro],
                  campos={"prod": [], "nome": "", "tipo": "pct", "valor": "", "ate": ""}, marcados=set(),
                  dias_parado=60, max_oferta=20, hoje=date(2026, 11, 4), categorias=[], busca="colar", filtrando=True,
                  achados=1, etiquetas=[('🔎 "colar"', "busca")], filtro=None, preco_max=0, cat_principal="")
    assert "1 produto encontrado" in html and 'data-tirar="busca"' in html and "Nenhum produto parado" in html
    html = render("produtos/ofertas_ver.html", itens=[parado, outro], com_foto=[], nome_oferta="Kit", msg="texto da oferta",
                  link="https://wa.me/?text=x", voltar="/ofertas?prod=p1", vender="/vender?kit=p1&kit=p2&desconto=40,00",
                  conta={"de": Decimal("179.80"), "por": Decimal("139.80"), "economia": Decimal("40.00"), "pct": 22})
    assert "VENDER ESTE KIT" in html and "/vender?kit=p1&amp;kit=p2&amp;desconto=40,00" in html
    assert "MANDAR SÓ O TEXTO" in html and "MUDAR A OFERTA" in html and "R$ 139,80" in html
    # o aviso do Início leva para montar a oferta
    estoque = {"acabou": [], "acabando": [], "vencendo": [], "parados": [parado]}
    html = render("inicio/inicio.html", saudacao="Bom dia", hoje_qtd=0, hoje_valor=Decimal(0), atrasados_qtd=0,
                  atrasados_valor=Decimal(0), chegaram=0, estoque=estoque, vendas_qtd=0, vendas_valor=Decimal(0))
    assert 'href="/ofertas"' in html and "monte uma oferta" in html


def test_banco_tem_os_campos_novos():
    from app.core.web import PASTA_APP
    sql = (PASTA_APP.parent / "supabase" / "migrations" / "20261104120000_desconto_servico_ofertas.sql").read_text(encoding="utf-8")
    for campo in ("vendas\n  add column if not exists desconto", "venda_itens\n  add column if not exists desconto",
                  "add column if not exists servico", "add column if not exists ativo"):
        assert campo in sql, campo
    assert "and not p.servico" in sql and "and not servico" in sql  # serviço não mexe no estoque


def test_pagamento_em_mais_de_uma_forma():
    from app.controllers.vender import forma_e_partes
    from app.models.vendas import ler_partes, partes_da_venda, texto_partes
    d = Decimal
    assert ler_partes({"dinheiro": "20,00", "pix": "", "cartao": "30"}) == [("dinheiro", d("20.00")), ("cartao", d("30.00"))]
    assert "Escreva quanto foi" in ler_partes({"dinheiro": "", "pix": "0"})
    assert "Confira o valor em Pix" in ler_partes({"pix": "abc"})
    assert "Falta R$ 10,00" in partes_da_venda({"dinheiro": "20", "pix": "20"}, d("50.00"))
    assert "Passou R$ 5,00" in partes_da_venda({"dinheiro": "25", "pix": "30"}, d("50.00"))
    assert texto_partes([("dinheiro", d("20")), ("pix", d("30"))]) == "Dinheiro R$ 20,00 + Pix R$ 30,00"
    assert forma_e_partes("pix", d("50"), "", "", "") == ("pix", None, "")
    assert forma_e_partes("dividido", d("50"), "20", "", "30,00") == ("dividido", [("dinheiro", d("20.00")), ("cartao", d("30.00"))], "")
    assert forma_e_partes("dividido", d("50"), "", "50", "") == ("pix", None, "")  # só uma forma: não divide
    # recibo e tela da venda mostram cada parte
    venda = {"id": "v1", "total": "50.00", "forma_pagamento": "dividido", "parcelas": [], "desconto": "0",
             "clientes": {"id": "c1", "nome": "Maria Teste", "whatsapp": "1199"},
             "venda_itens": [{"descricao": "Blusa", "quantidade": 1, "preco_unitario": "50.00", "desconto": "0"}],
             "venda_pagamentos": [{"forma": "dinheiro", "valor": "20.00"}, {"forma": "cartao", "valor": "30.00"}]}
    assert "Pagamento: Dinheiro R$ 20,00 + Cartão R$ 30,00 (pago ✅)" in texto_recibo(venda, "ElitaStore")
    html = render("vender/feita.html", v=venda, c=venda["clientes"], recibo="", link_recibo="", da_encomenda=False,
                  pode_apagar=False, FORMAS=FORMAS)
    assert "🔀 Mais de uma forma" in html and "💵 Dinheiro R$ 20,00 + 💳 Cartão R$ 30,00" in html
    # Nova venda: a opção e os campos de cada forma; ELA PAGOU: o botão para pagar de mais de um jeito
    html = render("vender/nova.html", antiga=None, produtos=[], produto="", categorias=[], pessoas=[], letras_clientes=set(),
                  cliente="", descricao="", preco="", encomenda="", volta="/vender", dia_padrao=10, vendas_hoje=[],
                  total_hoje=0, FORMAS=FORMAS, kit=[], desconto_kit="")
    assert 'value="dividido"' in html and 'name="parte_pix"' in html and 'id="parte-conta"' in html
    base = dict(saldo=SALDO, parcelas=[], abertas=[], pagamentos=[], ajustes=[], cobrar=Decimal(0), link_cobrar="",
                FORMAS=FORMAS, compras=[], total_compras=Decimal(0))
    html = render("clientes/ficha.html", c={"id": "c1", "nome": "Maria", "whatsapp": "", "endereco": "", "observacoes": ""}, **base)
    assert "Pagou de mais de um jeito?" in html and 'name="parte_cartao"' in html and 'name="dividir"' in html


def test_banco_tem_o_pagamento_dividido():
    from app.core.web import PASTA_APP
    sql = (PASTA_APP.parent / "supabase" / "migrations" / "20261104130000_pagamento_dividido.sql").read_text(encoding="utf-8")
    assert "'dividido'" in sql and "create table if not exists public.venda_pagamentos" in sql
    assert "enable row level security" in sql and "so a dona apaga" in sql  # RLS em todas as tabelas


def test_recibo_sem_coracao_e_com_deus_abencoe():
    venda = {"total": "50.00", "forma_pagamento": "pix", "parcelas": [], "clientes": {"nome": "Maria Teste"},
             "venda_itens": [{"descricao": "Blusa", "quantidade": 1, "preco_unitario": "50.00"}]}
    texto = texto_recibo(venda, "ElitaStore")
    assert "💜" not in texto and "❤" not in texto
    assert texto.startswith("Oi, Maria! Aqui está o recibo da sua compra na ElitaStore.")
    assert texto.endswith("Obrigada pela compra! Deus abençoe 🙏")


class BancoPorTabela:
    """Banco de mentira: cada tabela devolve as suas linhas (os filtros são ignorados)."""
    def __init__(self, tabelas):
        self.tabelas, self.atual = tabelas, None

    def table(self, nome):
        self.atual = nome
        return self

    def __getattr__(self, nome):
        return self if nome == "not_" else (lambda *a, **k: self)

    def execute(self):
        return SimpleNamespace(data=self.tabelas.get(self.atual, []))


def test_custos_e_lucro_de_cada_produto():
    from app.models import financeiro
    banco = BancoPorTabela({
        "produtos": [
            {"id": "p1", "nome": "Perfume", "preco": "100.00", "quantidade": 2, "servico": False},   # comprei 5
            {"id": "p2", "nome": "Colar", "preco": "50.00", "quantidade": 8, "servico": False},      # comprei 10
            {"id": "s1", "nome": "Escova", "preco": "60.00", "quantidade": 0, "servico": True},
            {"id": "p3", "nome": "Batom", "preco": "20.00", "quantidade": 4, "servico": False},      # sem custo
        ],
        "produtos_custo": [{"produto_id": "p1", "preco_custo": "40.00"}, {"produto_id": "p2", "preco_custo": "30.00"},
                           {"produto_id": "s1", "preco_custo": "15.00"}],
        # venda v1: 3 perfumes (R$ 300) + 1 batom (R$ 20) com R$ 32 de desconto na compra toda (10%)
        "venda_itens": [
            {"id": "i1", "venda_id": "v1", "produto_id": "p1", "quantidade": 3, "preco_unitario": "100.00", "desconto": "0",
             "vendas": {"vendida_em": "2026-11-04T12:00:00-03:00", "desconto": "32.00"}},
            {"id": "i2", "venda_id": "v1", "produto_id": "p3", "quantidade": 1, "preco_unitario": "20.00", "desconto": "0",
             "vendas": {"vendida_em": "2026-11-04T12:00:00-03:00", "desconto": "32.00"}},
            {"id": "i3", "venda_id": "v2", "produto_id": "p2", "quantidade": 2, "preco_unitario": "50.00", "desconto": "10.00",
             "vendas": {"vendida_em": "2026-11-04T12:00:00-03:00", "desconto": "0"}},
            {"id": "i4", "venda_id": "v3", "produto_id": "s1", "quantidade": 2, "preco_unitario": "60.00", "desconto": "0",
             "vendas": {"vendida_em": "2026-11-04T12:00:00-03:00", "desconto": "0"}},
        ],
        "gastos": [{"valor": "50.00"}],
    })
    r = financeiro.custos_e_lucro(banco)
    por_id = {p["id"]: p for p in r["produtos"]}
    perfume, colar, escova = por_id["p1"], por_id["p2"], por_id["s1"]
    # perfume: comprei 5 x 40 = 200; entrou 300 - 30 (a parte dele no desconto) = 270: já se pagou
    assert perfume["comprei"] == 5 and perfume["investi"] == Decimal("200.00") and perfume["entrou"] == Decimal("270.00")
    assert perfume["se_pagou"] and perfume["lucro_ate_agora"] == Decimal("150.00") and perfume["andamento"] == 100
    assert perfume["lucro_cada"] == Decimal("60.00") and perfume["pct"] == 60
    # colar: comprei 10 x 30 = 300; entrou 90: falta 210 = mais 5 vendas de R$ 50
    assert not colar["se_pagou"] and colar["falta"] == Decimal("210.00") and colar["faltam_vendas"] == 5
    assert colar["andamento"] == 30
    assert escova["grupo"] == "servico" and escova["lucro_ate_agora"] == Decimal("90.00")
    assert [p["id"] for p in r["sem_custo"]] == ["p3"]
    assert r["produtos"][0]["id"] == "p2"  # os que ainda não se pagaram vêm primeiro
    assert r["qtd"] == {"pagou": 1, "falta": 1, "servico": 1}
    # lucro do mês: vendi 270 + 90 + 120 = 480; custo 120 + 60 + 30 = 210; lucro 270; gastos 50: sobrou 220
    m = r["lucro"]
    assert (m["vendi"], m["custo"], m["lucro"], m["gastei"], m["sobrou"]) == (
        Decimal("480.00"), Decimal("210.00"), Decimal("270.00"), Decimal("50.00"), Decimal("220.00"))
    assert m["sem_custo"] == Decimal("18.00")  # o batom (20 - 2 do desconto) ficou fora da conta
    html = render("dinheiro/custos.html", **r)
    assert "Lucro de" in html and "Já se pagou! Lucro até agora: R$ 150,00" in html
    assert "Falta entrar R$ 210,00 para se pagar (mais 5 vendas)" in html and "Sem custo anotado (1)" in html
    assert "R$ 18,00 das vendas deste mês" in html and "✂️ Vendi 2 vezes" in html and 'data-ver="pagou"' in html


class BancoQueAnota(BancoPorTabela):
    """Como o BancoPorTabela, mas anota o que foi mudado (update e insert) em cada tabela."""
    def __init__(self, tabelas):
        super().__init__(tabelas)
        self.mudancas = []

    def update(self, dados):
        self.mudancas.append(("update", self.atual, dados))
        return self

    def insert(self, dados):
        self.mudancas.append(("insert", self.atual, dados))
        return self


def test_reparcelar_o_que_ela_deve(monkeypatch):
    from app.models import clientes
    monkeypatch.setattr(util, "hoje", lambda: date(2026, 11, 4))
    # deve 2 parcelas: a 1ª de 100 com 40 pagos (falta 60) e a 2ª de 100 (falta 100) = 160
    banco = BancoQueAnota({"parcelas_situacao": [
        {"id": "a", "valor": "100.00", "pago": "40.00", "falta": "60.00", "vencimento": "2026-10-10"},
        {"id": "b", "valor": "100.00", "pago": "0", "falta": "100.00", "vencimento": "2026-11-10"}]})
    feito = clientes.reparcelar(banco, "c1", 3, 15, motivo="pediu mais prazo")
    assert feito["falta"] == Decimal("160.00") and feito["valores"] == [Decimal("53.34"), Decimal("53.33"), Decimal("53.33")]
    assert [d.isoformat() for d in feito["datas"]] == ["2026-11-15", "2026-12-15", "2027-01-15"]
    updates = [m for m in banco.mudancas if m[0] == "update"]
    assert [u[2]["valor"] for u in updates] == ["40.00", "0"]  # as antigas ficam só com o que já foi pago
    novas = next(m[2] for m in banco.mudancas if m[0] == "insert" and m[1] == "parcelas")
    assert sum(Decimal(p["valor"]) for p in novas) == Decimal("160.00") and novas[0]["observacao"] == "reparcelado em 04/11/2026"
    ajuste = next(m[2] for m in banco.mudancas if m[0] == "insert" and m[1] == "ajustes")
    assert ajuste["tipo"] == "vezes" and ajuste["antes"] == "2 parcelas (R$ 160,00)" and "3x de R$ 53,33" in ajuste["depois"]
    assert clientes.reparcelar(BancoQueAnota({"parcelas_situacao": []}), "c1", 3, 15) is None  # não deve nada


def test_telas_de_reparcelar():
    c = {"id": "c1", "nome": "Maria Teste"}
    html = render("clientes/reparcelar.html", c=c, abertas=[PARCELA], falta=Decimal("160.00"), dia_padrao=4)
    assert "R$ 160,00" in html and 'name="vezes"' in html and 'name="dia2"' in html and "REPARCELAR" in html
    assert 'data-confirmar="Reparcelar' in html and "AJUSTAR VALOR" in html
    base = dict(saldo=SALDO, parcelas=[], abertas=[], pagamentos=[], cobrar=Decimal(0), link_cobrar="", FORMAS=FORMAS,
                compras=[], total_compras=Decimal(0),
                ajustes=[{"tipo": "vezes", "antes": "2 parcelas (R$ 160,00)", "depois": "3x de R$ 53,33", "feito_em": "2026-11-04", "motivo": ""}])
    ficha = dict(c, whatsapp="", endereco="", observacoes="")
    html = render("clientes/ficha.html", c=ficha, **base)
    assert 'href="/clientes/c1/reparcelar"' in html and "Reparcelado: 2 parcelas (R$ 160,00) → 3x de R$ 53,33" in html
    html = render("clientes/ficha.html", c=ficha, s=SimpleNamespace(e_dona=False, nome="Ajudante", usuario_id="u2"), **base)
    assert "/reparcelar" not in html  # só a Elita reparcela


def test_dividas_soma_tudo_que_me_devem():
    from app.models import financeiro
    banco = BancoPorTabela({"clientes_saldo": [
        {"cliente_id": "c1", "nome": "Ana", "falta_total": "50.00", "atrasado": "0", "hoje": "0", "proximo_vencimento": "2026-11-20"},
        {"cliente_id": "c2", "nome": "Bia", "falta_total": "230.00", "atrasado": "30.00", "hoje": "0", "proximo_vencimento": "2026-10-06"}]})
    r = financeiro.dividas(banco)
    assert r["total"] == Decimal("280.00") and r["atrasado"] == Decimal("30.00") and r["atrasadas"] == 1
    assert [p["nome"] for p in r["pessoas"]] == ["Bia", "Ana"]  # da maior dívida para a menor
    html = render("dinheiro/dividas.html", **r)
    assert "R$ 280,00" in html and "2 pessoas devendo" in html and "Atrasado: <strong>R$ 30,00</strong> (1 pessoa)" in html
    assert html.index("Bia") < html.index("Ana") and 'href="/clientes/c2"' in html
    assert "Ninguém está devendo" in render("dinheiro/dividas.html", pessoas=[], total=Decimal(0), atrasado=Decimal(0), atrasadas=0)


def test_mandar_o_que_tenho_sem_o_caminho_da_categoria():
    from app.models.produtos import mensagem_o_que_tenho
    grupos = {"Cosméticos › Sabonetes › NATURA › Barras › Tododia": [{"nome": "Sabonete Tododia", "preco": "12.90"}],
              "Perfumes": [{"nome": "Lattafa", "preco": "189.00"}]}
    linhas = mensagem_o_que_tenho("ElitaStore", grupos).splitlines()
    assert linhas == ["🛍️ ElitaStore: o que tenho hoje", "", "• Sabonete Tododia: R$ 12,90", "• Lattafa: R$ 189,00",
                      "", "Quer que eu separe algum? 😊"]


def test_produto_pela_porcentagem_que_ganho():
    from app.models.produtos import custo_pela_porcentagem, ganho_em_pct
    assert custo_pela_porcentagem(Decimal("100.00"), "30") == Decimal("70.00")
    assert custo_pela_porcentagem(Decimal("89.90"), "30%") == Decimal("62.93")
    assert custo_pela_porcentagem(Decimal("50.00"), "27,5") == Decimal("36.25")
    assert custo_pela_porcentagem(Decimal("50.00"), "0") == Decimal("50.00")
    assert custo_pela_porcentagem(Decimal("50.00"), "120") is None and custo_pela_porcentagem(Decimal("50"), "abc") is None
    assert ganho_em_pct("100.00", "70.00") == "30" and ganho_em_pct("50.00", "36.25") == "27,5"
    assert ganho_em_pct("100.00", None) == "" and ganho_em_pct("0", "10") == ""
    html = render("produtos/form.html", p=dict(PRODUTO, servico=False, custo="70.00", ganho_pct="30", fotos=[], preco="100.00"),
                  cats=[], categoria=None, max_fotos=3, servico_padrao=False)
    # os dois juntos: o custo em reais e a % que ganho (um preenche o outro na tela)
    assert "Quanto eu ganho (%)" in html and 'name="ganho_pct"' in html and 'value="30"' in html
    assert "Quanto paguei (custo)" in html and 'name="custo"' in html and 'value="70,00"' in html
    assert "o outro aparece sozinho" in html and "Qual é o meu custo?" in html  # o nome do campo no serviço
    html = render("produtos/form.html", p=dict(PRODUTO, servico=False, fotos=[]), cats=[], categoria=None, max_fotos=3,
                  servico_padrao=False, s=SimpleNamespace(e_dona=False, nome="Ajudante", usuario_id="u2"))
    assert "ganho_pct" not in html and 'name="custo"' not in html  # a ajudante não vê custo nem lucro
