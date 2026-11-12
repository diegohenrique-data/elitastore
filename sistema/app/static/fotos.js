// FOTOS DO PRODUTO: "Tirar foto" (câmera do celular) e "Escolher da galeria / do computador".
// Antes de mandar, a foto é diminuída aqui mesmo no aparelho (no máximo 1600 px), para subir
// rápido mesmo no 4G. O servidor faz o ajuste final (quadrado com fundo branco, igual vitrine).
// Sem JavaScript, os campos funcionam sozinhos (mandam a foto do jeito que veio).
(function () {
  const MAIOR_LADO = 1600;

  function diminuir(arquivo) {
    return new Promise((pronto) => {
      if (!arquivo.type.startsWith("image/")) return pronto(arquivo);
      const img = new Image();
      const url = URL.createObjectURL(arquivo);
      img.onload = () => {
        URL.revokeObjectURL(url);
        const escala = Math.min(1, MAIOR_LADO / Math.max(img.naturalWidth, img.naturalHeight));
        const tela = document.createElement("canvas");
        tela.width = Math.round(img.naturalWidth * escala);
        tela.height = Math.round(img.naturalHeight * escala);
        const g = tela.getContext("2d");
        g.fillStyle = "#fff";
        g.fillRect(0, 0, tela.width, tela.height);
        g.drawImage(img, 0, 0, tela.width, tela.height);
        tela.toBlob((b) => pronto(b ? new File([b], "foto.jpg", { type: "image/jpeg" }) : arquivo), "image/jpeg", 0.88);
      };
      img.onerror = () => { URL.revokeObjectURL(url); pronto(arquivo); };  // o servidor tenta mesmo assim
      img.src = url;
    });
  }

  document.querySelectorAll("[data-fotos]").forEach((caixa) => {
    const guardadas = caixa.querySelector(".fotos-guardar");  // o campo que vai no formulário
    const previas = caixa.querySelector(".fotos-previas");
    const contador = caixa.querySelector(".fotos-contador");
    const botoes = caixa.querySelector(".fotos-botoes");
    const max = Number(caixa.dataset.max || 3);
    const mandarSozinho = caixa.dataset.mandar === "sim";  // tela do produto: guarda na hora
    let lista;
    try { lista = new DataTransfer(); } catch (e) { return; }  // aparelho antigo: fica sem prévia
    caixa.querySelectorAll(".fotos-escolher").forEach((c) => c.removeAttribute("name"));
    guardadas.setAttribute("name", "fotos");

    function mostrar() {
      previas.innerHTML = "";
      [...lista.files].forEach((arq, i) => {
        const fig = document.createElement("figure");
        fig.className = "foto-quadro nova";
        const img = document.createElement("img");
        img.src = URL.createObjectURL(arq);
        img.alt = `Foto nova ${i + 1}`;
        fig.appendChild(img);
        if (!mandarSozinho) {
          const tirar = document.createElement("button");
          tirar.type = "button";
          tirar.className = "foto-tirar";
          tirar.setAttribute("aria-label", `Tirar a foto ${i + 1}`);
          tirar.textContent = "✕";
          tirar.addEventListener("click", () => {
            const nova = new DataTransfer();
            [...lista.files].forEach((a, j) => { if (j !== i) nova.items.add(a); });
            lista = nova; guardadas.files = lista.files; mostrar();
          });
          fig.appendChild(tirar);
        }
        if (i === 0 && caixa.dataset.temPrincipal !== "sim") {
          const selo = document.createElement("span");
          selo.className = "foto-selo";
          selo.textContent = "⭐ Principal";
          fig.appendChild(selo);
        }
        previas.appendChild(fig);
      });
      const cheias = lista.files.length >= max;
      if (botoes) botoes.classList.toggle("oculto", cheias);
      if (contador) contador.textContent = lista.files.length
        ? `${lista.files.length} de ${max} ${max === 1 ? "foto" : "fotos"}${cheias ? " (cheio)" : ""}` : "";
    }

    caixa.querySelectorAll(".fotos-escolher").forEach((campo) => campo.addEventListener("change", async () => {
      const escolhidos = [...campo.files].slice(0, max - lista.files.length);
      campo.value = "";
      if (!escolhidos.length) return;
      caixa.classList.add("carregando");
      for (const arq of escolhidos) lista.items.add(await diminuir(arq));
      guardadas.files = lista.files;
      caixa.classList.remove("carregando");
      mostrar();
      if (mandarSozinho) { caixa.classList.add("carregando"); caixa.closest("form").requestSubmit(); }
    }));
  });
})();

// Apagar foto: a pergunta "Apagar esta foto?" (data-confirmar) vale em todas as telas: ver layout/base.html.
