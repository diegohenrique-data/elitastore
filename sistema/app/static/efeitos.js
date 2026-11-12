// Efeitos de toque da ElitaStore: ondinha que sai do ponto tocado e uma
// vibraçãozinha no celular (quando o aparelho permite). Não muda nada do
// funcionamento: se o JavaScript não rodar, os botões continuam iguais.
(function () {
  const SELETOR = ".botao, button, .botao-grande, .voltar, a.item, a.aviso, .escolhas label > span, .lateral a.menu, .sair-movel, .opcao > span, .venda-destaque, .fab-venda, .lateral a.menu-venda";

  function marcar() {
    document.querySelectorAll(SELETOR).forEach((el) => el.classList.add("tocavel"));
  }

  function onda(evento) {
    const el = evento.target.closest(SELETOR);
    if (!el) return;
    const caixa = el.getBoundingClientRect();
    const tamanho = Math.max(caixa.width, caixa.height);
    const x = (evento.clientX || caixa.left + caixa.width / 2) - caixa.left - tamanho / 2;
    const y = (evento.clientY || caixa.top + caixa.height / 2) - caixa.top - tamanho / 2;
    const bolha = document.createElement("span");
    bolha.className = "onda";
    bolha.style.cssText = `width:${tamanho}px;height:${tamanho}px;left:${x}px;top:${y}px`;
    el.appendChild(bolha);
    bolha.addEventListener("animationend", () => bolha.remove());
    if (navigator.vibrate) navigator.vibrate(8);
  }

  document.addEventListener("pointerdown", onda, { passive: true });
  document.addEventListener("DOMContentLoaded", marcar);
  marcar();
})();
