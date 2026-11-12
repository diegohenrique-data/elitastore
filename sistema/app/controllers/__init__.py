"""CONTROLLERS: recebem o que a pessoa faz (abrir uma tela, tocar num botão, mandar um formulário),
pedem os dados aos models e escolhem a view (tela) que vai aparecer.

Um arquivo por área do sistema, na ordem dos botões da tela principal.
"""

from . import auth, clientes, dinheiro, encomendas, inicio, ofertas, produtos, receber, vender

ROTAS = [auth.router, inicio.router, clientes.router, vender.router, receber.router,
         produtos.router, ofertas.router, encomendas.router, dinheiro.router]
