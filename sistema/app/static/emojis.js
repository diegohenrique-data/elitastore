// ESCOLHER O ÍCONE (emoji) DA CATEGORIA: a janela sobe de baixo (igual ao painel de Filtros),
// com as abas do teclado do WhatsApp (😀 🐻 🍔 ⚽ 🚗 💡 🔣 🏳️) e a busca pelo nome em português.
// A lista vem de static/emojis.json (só baixa quando ela abre a janela pela primeira vez).
(function () {
  const campos = [...document.querySelectorAll("[data-emoji]")];
  if (!campos.length) return;
  let grupos = null, folha, fundo, busca, grade, abas, campoAtual = null, botaoQueAbriu = null;
  const semAcento = (t) => (t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

  function montar() {
    fundo = document.createElement("div");
    fundo.className = "folha-fundo oculto";
    folha = document.createElement("div");
    folha.className = "folha folha-emoji oculto";
    folha.setAttribute("role", "dialog");
    folha.setAttribute("aria-modal", "true");
    folha.setAttribute("aria-labelledby", "emoji-titulo");
    folha.innerHTML = `
      <div class="folha-alca" aria-hidden="true"></div>
      <h3 class="folha-titulo" id="emoji-titulo" tabindex="-1">Escolha o ícone</h3>
      <input type="search" class="busca-categoria" placeholder="Procurar: perfume, vestido, anel..." aria-label="Procurar ícone pelo nome" autocomplete="off">
      <div class="emoji-abas" role="tablist" aria-label="Grupos de ícones"></div>
      <div class="folha-conteudo emoji-grade" aria-live="polite"><p class="vazio">⏳ Carregando os ícones...</p></div>
      <div class="folha-botoes uma"><button type="button" class="claro emoji-fechar">Fechar</button></div>`;
    document.body.append(fundo, folha);
    busca = folha.querySelector("input");
    grade = folha.querySelector(".emoji-grade");
    abas = folha.querySelector(".emoji-abas");
    fundo.addEventListener("click", fechar);
    folha.querySelector(".emoji-fechar").addEventListener("click", fechar);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") fechar(); });
    busca.addEventListener("input", desenhar);
    busca.addEventListener("keydown", (e) => { if (e.key === "Enter") e.preventDefault(); });
    grade.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-e]");
      if (b) escolher(b.dataset.e);
    });
    fetch("/static/emojis.json").then((r) => r.json()).then((g) => {
      grupos = g;
      abas.innerHTML = g.map((x, i) => `<button type="button" role="tab" data-i="${i}" aria-label="${x.nome}" title="${x.nome}">${x.icone}</button>`).join("");
      abas.addEventListener("click", (e) => {
        const b = e.target.closest("button[data-i]");
        if (!b) return;
        busca.value = "";
        desenhar();
        grade.querySelector(`[data-grupo="${b.dataset.i}"]`)?.scrollIntoView({ block: "start" });
      });
      desenhar();
    }).catch(() => { grade.innerHTML = '<p class="vazio">Não consegui abrir a lista de ícones. Tente de novo.</p>'; });
  }

  function desenhar() {
    if (!grupos) return;
    const termo = semAcento(busca.value);
    let html = "", achados = 0;
    grupos.forEach((g, i) => {
      const lista = termo ? g.emojis.filter(([, nome]) => semAcento(nome).includes(termo)) : g.emojis;
      if (!lista.length) return;
      achados += lista.length;
      html += `<h4 data-grupo="${i}">${g.nome}</h4><div class="emoji-lista">` +
        lista.map(([e, nome]) => `<button type="button" data-e="${e}" aria-label="${nome}" title="${nome}">${e}</button>`).join("") + "</div>";
    });
    grade.innerHTML = achados ? html : '<p class="vazio">Nenhum ícone com esse nome. Tente outra palavra.</p>';
    grade.scrollTop = 0;
  }

  function abrir(campo, botao) {
    if (!folha) montar();
    campoAtual = campo;
    botaoQueAbriu = botao;
    busca.value = "";
    desenhar();
    fundo.classList.remove("oculto");
    folha.classList.remove("oculto");
    document.body.classList.add("com-folha");
    document.getElementById("emoji-titulo").focus();
  }

  function fechar() {
    if (!folha || folha.classList.contains("oculto")) return;
    fundo.classList.add("oculto");
    folha.classList.add("oculto");
    document.body.classList.remove("com-folha");
    botaoQueAbriu?.focus({ preventScroll: true });
  }

  function mostrar(campo, figura) {  // atualiza o botão com o emoji escolhido (ou o automático)
    campo.querySelector('input[name="icone"]').value = figura;
    const atual = campo.querySelector(".emoji-atual");
    atual.textContent = figura || campo.dataset.automatico || "➕";
    atual.classList.toggle("automatico", !figura);
    campo.querySelector(".emoji-texto").textContent = figura ? "Trocar o ícone" : "Escolher um ícone";
    campo.querySelector(".emoji-tirar").hidden = !figura;
    if (campo.dataset.mandar === "sim") campo.closest("form").requestSubmit();
  }

  function escolher(figura) {
    const campo = campoAtual;
    fechar();
    if (campo) mostrar(campo, figura);
  }

  campos.forEach((campo) => {
    const botao = campo.querySelector(".emoji-abrir");
    botao.addEventListener("click", () => abrir(campo, botao));
    campo.querySelector(".emoji-tirar").addEventListener("click", () => mostrar(campo, ""));
  });
})();
