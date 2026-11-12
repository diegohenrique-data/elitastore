// FILTRO "O que eu tenho?" (um estilo só no sistema): telas PRODUTOS, MANDAR O QUE TENHO e MONTAR OFERTA.
// No painel: escolher a categoria mostra os tipos dela; as 3 últimas categorias usadas ficam na frente.
// Depois de filtrar: o painel de Filtros que sobe de baixo (igual ao da Nova venda).
// Lê do <form id="filtro">: data-usada (categoria recém usada), data-atual, data-preco, data-limpar.
(function () {
  const form = document.getElementById("filtro");
  const marcar = (nome, valor) => { const r = form.querySelector(`input[name="${nome}"][value="${valor}"]`); if (r) r.checked = true; };
  function mostrarTipo(pai) {  // a seção "Tipo de ..." da categoria escolhida
    form.querySelectorAll(".filtro-sub").forEach((sec) => sec.classList.toggle("oculto", sec.dataset.pai !== pai));
  }
  form.querySelectorAll('input[name="f_cat"]').forEach((r) => r.addEventListener("change", () => mostrarTipo(r.value)));
  form.querySelectorAll(".ver-todas").forEach((b) => b.addEventListener("click", () => {
    form.querySelectorAll(`#${b.dataset.grupo} .extra`).forEach((op) => op.classList.remove("oculto"));
    b.remove();
  }));

  // As 3 últimas categorias usadas no filtro ficam guardadas NESTE aparelho (se não der, vale a ordem padrão).
  const CHAVE_RECENTES = "elita:categorias-recentes";
  const lerRecentes = () => { try { return JSON.parse(localStorage.getItem(CHAVE_RECENTES)) || []; } catch (e) { return []; } };
  const guardarRecente = (id) => {
    try { localStorage.setItem(CHAVE_RECENTES, JSON.stringify([id, ...lerRecentes().filter((x) => x !== id)].slice(0, 10))); } catch (e) { /* sem memória: tudo bem */ }
  };
  const usada = form.dataset.usada || "";  // veio de um filtro com categoria: ela vira a mais recente
  if (usada) guardarRecente(usada);

  const grade = document.getElementById("grade-categorias");
  if (grade) {
    const quadros = [...grade.querySelectorAll(".cat-quadro")];
    const porId = Object.fromEntries(quadros.map((q) => [q.dataset.id, q]));
    function mostrarNaFrente(ids) {  // estes primeiro, e só 3 à vista
      [...ids].reverse().forEach((id) => { if (porId[id]) grade.prepend(porId[id]); });
      [...grade.querySelectorAll(".cat-quadro")].forEach((q, i) => q.classList.toggle("oculto", i >= 3));
    }
    const recentes = lerRecentes().filter((id) => porId[id]);
    if (recentes.length) {
      mostrarNaFrente(recentes.slice(0, 3));
      document.getElementById("dica-categorias").textContent = "as últimas que você usou";
    }
    // tocar de novo no quadrado marcado desmarca (nenhuma marcada = todas)
    quadros.forEach((q) => {
      const r = q.querySelector("input");
      const lembrar = () => { r.dataset.estava = r.checked ? "1" : ""; };
      q.addEventListener("pointerdown", lembrar);
      r.addEventListener("keydown", (e) => { if (e.key === " " || e.key === "Enter") lembrar(); });  // teclado também
      r.addEventListener("click", () => {
        if (r.dataset.estava === "1") { r.checked = false; mostrarTipo(""); }
        r.dataset.estava = "";
      });
    });

    // "Ver todas as categorias": painel com todas (A a Z) e busca. A escolhida vem para a frente, marcada.
    const folhaCat = document.getElementById("folha-categorias");
    if (folhaCat) {
      const fundoCat = document.getElementById("fundo-categorias");
      const botaoMais = document.getElementById("abrir-categorias");
      const buscaCat = document.getElementById("busca-categoria");
      const semAcento = (t) => (t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
      function filtrarCat() {
        const termo = semAcento(buscaCat.value);
        let achadas = 0;
        folhaCat.querySelectorAll(".cat-linha").forEach((l) => {
          const combina = !termo || semAcento(l.dataset.busca).includes(termo);
          l.classList.toggle("oculto", !combina);
          if (combina) achadas++;
        });
        document.getElementById("nenhuma-categoria").classList.toggle("oculto", achadas > 0);
      }
      function abrirCat() {
        fundoCat.classList.remove("oculto"); folhaCat.classList.remove("oculto");
        document.body.classList.add("com-folha");
        buscaCat.value = ""; filtrarCat();
        document.getElementById("titulo-categorias").focus();
      }
      function fecharCat() {
        if (folhaCat.classList.contains("oculto")) return;
        fundoCat.classList.add("oculto"); folhaCat.classList.add("oculto");
        document.body.classList.remove("com-folha");
        botaoMais.focus({ preventScroll: true });
      }
      botaoMais.addEventListener("click", abrirCat);
      fundoCat.addEventListener("click", fecharCat);
      document.getElementById("fechar-categorias").addEventListener("click", fecharCat);
      document.addEventListener("keydown", (e) => { if (e.key === "Escape") fecharCat(); });
      buscaCat.addEventListener("input", filtrarCat);
      buscaCat.addEventListener("keydown", (e) => { if (e.key === "Enter") e.preventDefault(); });  // Enter não manda o filtro
      folhaCat.querySelectorAll('input[name="f_cat"]').forEach((r) => r.addEventListener("change", () => {
        mostrarNaFrente([r.value]);
        porId[r.value].querySelector("input").checked = true;
        mostrarTipo(r.value);
        setTimeout(fecharCat, 350);  // dá tempo de ver o ✓
      }));
    }
  }
  // só vai o tipo da categoria escolhida (os outros ficam de fora do endereço)
  form.addEventListener("submit", () => {
    const cat = form.querySelector('input[name="f_cat"]:checked')?.value || "";
    form.querySelectorAll('input[name^="f_sub_"]').forEach((r) => { r.disabled = r.name !== `f_sub_${cat}`; });
  });

  // VITRINE: setinhas ‹ › passam as fotos do produto (no fim, volta para a primeira).
  document.querySelectorAll("[data-carrossel]").forEach((caixa) => {
    const faixa = caixa.querySelector(".vitrine-fotos");
    const pontos = [...caixa.querySelectorAll(".vitrine-pontos span")];
    const atual = () => Math.round(faixa.scrollLeft / faixa.clientWidth);
    const ir = (i) => faixa.scrollTo({ left: ((i + pontos.length) % pontos.length) * faixa.clientWidth, behavior: "smooth" });
    caixa.querySelector(".anterior").addEventListener("click", () => ir(atual() - 1));
    caixa.querySelector(".proxima").addEventListener("click", () => ir(atual() + 1));
    faixa.addEventListener("scroll", () => pontos.forEach((p, i) => p.classList.toggle("atual", i === atual())), { passive: true });
  });

  const folha = document.getElementById("folha-filtros");
  if (!folha) return;
  const fundo = document.getElementById("folha-fundo");
  const abrir = document.getElementById("abrir-filtros");
  function marcarAtual() {
    // o painel mostra o que já está escolhido (e buscar pelo nome não apaga o filtro)
    const atual = form.dataset.atual || "";
    const pai = atual ? form.querySelector(`.filtro-sub [value="${atual}"]`)?.closest(".filtro-sub")?.dataset.pai : undefined;
    marcar("f_cat", pai || atual);
    if (pai) marcar(`f_sub_${pai}`, atual);
    marcar("f_preco", form.dataset.preco || "");
    mostrarTipo(pai || atual);
  }
  marcarAtual();
  function abrirFolha() {
    marcarAtual();
    fundo.classList.remove("oculto"); folha.classList.remove("oculto");
    document.body.classList.add("com-folha");
    document.getElementById("folha-titulo").focus();
  }
  function fecharFolha() {
    if (folha.classList.contains("oculto")) return;
    fundo.classList.add("oculto"); folha.classList.add("oculto");
    document.body.classList.remove("com-folha");
    abrir.focus({ preventScroll: true });
  }
  abrir.addEventListener("click", abrirFolha);
  fundo.addEventListener("click", fecharFolha);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") fecharFolha(); });
  document.getElementById("aplicar-filtros").addEventListener("click", () => form.requestSubmit());
  document.getElementById("limpar-filtros").addEventListener("click", () => {
    if (form.dataset.limparAqui) {  // MONTAR OFERTA: limpa o filtro sem sair da tela (não perde a oferta)
      marcar("f_cat", ""); marcar("f_preco", "");
      form.querySelectorAll('input[name^="f_sub_"][value=""]').forEach((r) => { r.checked = true; });
      const busca = form.querySelector('input[name="busca"]');
      if (busca) busca.value = "";
      form.requestSubmit();
      return;
    }
    window.location.href = form.dataset.limpar || form.getAttribute("action");
  });
})();
