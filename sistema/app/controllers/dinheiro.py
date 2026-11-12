"""MEU DINHEIRO (só a Elita): resumo do mês, anotar gasto, EQUIPE e DADOS DA LOJA."""

from fastapi import APIRouter, Request

from ..core import util
from ..core.web import Dona, Texto, ir, ir_com_erro, numero, pagina
from ..models import configuracoes, equipe, financeiro
from ..models.equipe import ErroEquipe

router = APIRouter()


@router.get("/meu-dinheiro")
def meu_dinheiro(request: Request, s: Dona):
    return pagina(request, "dinheiro/meu_dinheiro.html", **financeiro.resumo_do_mes(s.db))


@router.post("/meu-dinheiro/gasto")
def anotar_gasto(s: Dona, valor: Texto, descricao: Texto, data: Texto = ""):
    v = util.ler_reais(valor)
    if not v or v <= 0 or not descricao.strip():
        return ir_com_erro("/meu-dinheiro", "Escreva o valor e o que foi. Ex.: 120,00 frete")
    financeiro.anotar_gasto(s.db, v, descricao, util.para_data(data) or util.hoje())
    return ir("/meu-dinheiro", f"Gasto de {util.reais(v)} anotado!")


@router.post("/meu-dinheiro/gasto/{gid}/apagar")
def apagar_gasto(s: Dona, gid: str):
    if not financeiro.apagar_gasto(s.db, gid):
        return ir_com_erro("/meu-dinheiro", "Não consegui apagar esse gasto.")
    return ir("/meu-dinheiro", "Gasto apagado.")


# DÍVIDAS: todo mundo que me deve, da maior dívida para a menor.
@router.get("/meu-dinheiro/dividas")
def dividas(request: Request, s: Dona):
    return pagina(request, "dinheiro/dividas.html", **financeiro.dividas(s.db))


# CUSTOS E LUCRO: o lucro do mês e, produto por produto, se ele já se pagou.
@router.get("/meu-dinheiro/custos")
def custos(request: Request, s: Dona):
    return pagina(request, "dinheiro/custos.html", **financeiro.custos_e_lucro(s.db))


# Lançamentos: as vendas e os pagamentos do mês, para conferir e apagar o que estiver errado.
@router.get("/meu-dinheiro/lancamentos")
def lancamentos(request: Request, s: Dona):
    return pagina(request, "dinheiro/lancamentos.html", **financeiro.lancamentos_do_mes(s.db))


@router.post("/pagamentos/{pid}/apagar")
def apagar_pagamento(s: Dona, pid: str, volta: Texto = "/meu-dinheiro/lancamentos"):
    destino = volta if volta.startswith("/") and not volta.startswith("//") else "/meu-dinheiro/lancamentos"
    if not financeiro.apagar_pagamento(s.db, pid):
        return ir_com_erro(destino, "Não consegui apagar esse pagamento.")
    return ir(destino, "Pagamento apagado. O valor voltou a faltar no fiado.")


# ---------------------------------------------------------------------------
# Equipe: a Elita cadastra, liga, desliga ou exclui a ajudante
# ---------------------------------------------------------------------------
@router.get("/equipe")
def equipe_tela(request: Request, s: Dona):
    return pagina(request, "dinheiro/equipe.html", lista=equipe.listar(s.db))


# A Elita cadastra a ajudante (nome, e-mail e senha) e o acesso já sai liberado.
@router.post("/equipe/nova")
def equipe_nova(s: Dona, nome: Texto, email: Texto, senha: Texto):
    if not nome.strip() or "@" not in email:
        return ir_com_erro("/equipe", "Escreva o nome e o e-mail da ajudante.")
    if len(senha) < 8:
        return ir_com_erro("/equipe", "A senha precisa ter pelo menos 8 letras ou números.")
    try:
        confirmar_email = equipe.cadastrar_ajudante(s.db, nome, email, senha)
    except ErroEquipe as e:
        return ir_com_erro("/equipe", str(e))
    aviso = " Ela vai receber um e-mail para confirmar antes do primeiro acesso." if confirmar_email else ""
    return ir("/equipe", f"{nome.strip()} cadastrada como ajudante, com acesso liberado.{aviso}")


# Excluir da equipe: apaga o login (e-mail, senha) e o perfil da ajudante. Pede confirmação.
@router.get("/equipe/{uid}/excluir")
def equipe_excluir_tela(request: Request, s: Dona, uid: str):
    p = equipe.buscar(s.db, uid)
    if not equipe.pode_mexer(p, uid, s.usuario_id):
        return ir_com_erro("/equipe", "Essa pessoa não pode ser excluída.")
    return pagina(request, "dinheiro/equipe_excluir.html", p=p)


@router.post("/equipe/{uid}/excluir")
def equipe_excluir(s: Dona, uid: str):
    p = equipe.buscar(s.db, uid, "nome, principal")
    if not equipe.pode_mexer(p, uid, s.usuario_id):
        return ir_com_erro("/equipe", "Essa pessoa não pode ser excluída.")
    try:
        equipe.excluir(s.db, uid)
    except ErroEquipe as e:
        return ir_com_erro("/equipe", str(e))
    return ir("/equipe", f"{p['nome'] or 'A pessoa'} foi excluída da equipe. O acesso dela (e-mail e senha) foi apagado.")


@router.post("/equipe/{uid}/{acao}")
def equipe_acao(s: Dona, uid: str, acao: str):
    # A Elita é a única dona (principal): ninguém muda o acesso dela. Para as ajudantes, só liga e desliga.
    if uid == s.usuario_id:
        return ir_com_erro("/equipe", "Você não pode mudar o seu próprio acesso.")
    acoes = {"ligar": True, "desligar": False}
    if acao not in acoes:
        return ir("/equipe")
    if not equipe.pode_mexer(equipe.buscar(s.db, uid, "principal"), uid, s.usuario_id):
        return ir_com_erro("/equipe", "A dona principal da loja não pode ser alterada.")
    equipe.mudar_acesso(s.db, uid, acoes[acao])
    return ir("/equipe", "Pronto, acesso atualizado!")


# ---------------------------------------------------------------------------
# Dados da loja: nome, chave Pix, mensagens e os dias dos avisos
# ---------------------------------------------------------------------------
@router.get("/loja")
def loja_tela(request: Request, s: Dona):
    return pagina(request, "dinheiro/loja.html", cfg=configuracoes.ler(s.db))


@router.post("/loja")
def loja_salvar(s: Dona, nome_loja: Texto, chave_pix: Texto = "", msg_cobranca: Texto = "",
                msg_encomenda: Texto = "", dias_parado: Texto = "60", dias_aviso_validade: Texto = "30",
                estoque_minimo_padrao: Texto = "3"):
    configuracoes.salvar(s.db, {
        "nome_loja": nome_loja.strip() or "ElitaStore", "chave_pix": chave_pix.strip(),
        "msg_cobranca": msg_cobranca.strip(), "msg_encomenda": msg_encomenda.strip(),
        "dias_parado": max(1, numero(dias_parado, 60) or 60),
        "dias_aviso_validade": max(1, numero(dias_aviso_validade, 30) or 30),
        "estoque_minimo_padrao": max(0, numero(estoque_minimo_padrao, 3) or 0),
    })
    return ir("/meu-dinheiro", "Dados da loja guardados!")
