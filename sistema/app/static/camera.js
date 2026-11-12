// LER CÓDIGO DE BARRAS COM A CÂMERA DO CELULAR (qualquer aparelho: iPhone, Android, Xiaomi, Samsung...).
// 1) PEDE A PERMISSÃO da câmera, explicando para que é (o navegador mostra a pergunta dele).
// 2) Abre a câmera de trás numa tela cheia, lê o código de barras do produto, faz o BIP igual
//    à maquininha, vibra e fecha. Se a câmera foi bloqueada, ensina a liberar NAQUELE aparelho.
// Uso: lerComCamera((codigo) => { ... }). O aparelho vem de window.aparelho (layout/base.html).
// A leitura usa a biblioteca html5-qrcode, carregada só na primeira vez que tocam no botão.
// Só aceita códigos de barras (sem QR Code) e confere duas leituras iguais antes do bip.
(function () {
  const BIBLIOTECA = "https://cdn.jsdelivr.net/npm/html5-qrcode@2.3.8/html5-qrcode.min.js";
  const aparelho = window.aparelho || { sistema: "computador", marca: "outra", navegador: "outro" };
  let carregando = null;

  function carregar() {
    if (window.Html5Qrcode) return Promise.resolve();
    if (!carregando) {
      carregando = new Promise((ok, falhou) => {
        const s = document.createElement("script");
        s.src = BIBLIOTECA;
        s.onload = ok;
        s.onerror = () => { carregando = null; falhou(new Error("sem internet")); };
        document.head.append(s);
      });
    }
    return carregando;
  }

  // o bip curtinho da maquininha (o som é criado no toque do botão, como o iPhone exige)
  let som;
  function prepararBip() {
    try { som = som || new (window.AudioContext || window.webkitAudioContext)(); som.resume(); } catch (e) { som = null; }
  }
  function bip() {
    if (navigator.vibrate) navigator.vibrate(120);  // o iPhone não vibra pelo site; os Android vibram
    if (!som) return;
    const o = som.createOscillator(), g = som.createGain();
    o.type = "square"; o.frequency.value = 1800;
    g.gain.value = 0.12;
    o.connect(g); g.connect(som.destination);
    o.start(); o.stop(som.currentTime + 0.12);
  }

  // Como liberar a câmera, passo a passo, em cada aparelho e navegador.
  function comoLiberar() {
    const { sistema, marca, navegador } = aparelho;
    if (navegador === "dentro-de-app") {
      return ["Este link abriu dentro de outro aplicativo (WhatsApp, Instagram...), que não deixa usar a câmera.",
              "Toque nos 3 pontinhos (⋮ ou …) e escolha \"Abrir no navegador\" (Chrome ou Safari).",
              "Lá, toque de novo em LER CÓDIGO DE BARRAS."];
    }
    if (sistema === "ios" && navegador === "safari") {
      return ["Toque em \"aA\" (ou no ícone ao lado do endereço, lá em cima ou embaixo).",
              "Toque em \"Ajustes do Site\" > \"Câmera\" > \"Permitir\".",
              "Se não aparecer: Ajustes do iPhone > Safari > Câmera > Permitir.",
              "Volte aqui e toque em TENTAR DE NOVO."];
    }
    if (sistema === "ios") {
      const app = navegador === "chrome" ? "Chrome" : navegador === "firefox" ? "Firefox" : navegador === "edge" ? "Edge" : "navegador";
      return [`Abra os Ajustes do iPhone e procure o ${app}.`, "Ligue a chave \"Câmera\".",
              "Volte aqui e toque em TENTAR DE NOVO."];
    }
    if (sistema === "android") {
      const passos = navegador === "samsung"
        ? ["Toque no cadeado 🔒 ao lado do endereço.", "Toque em \"Permissões\" > \"Câmera\" > \"Permitir\"."]
        : navegador === "xiaomi"
          ? ["Toque no cadeado 🔒 ao lado do endereço.", "Em \"Câmera\", escolha \"Permitir\"."]
          : ["Toque no cadeado 🔒 (ou ⓘ) ao lado do endereço.", "Toque em \"Permissões\" > \"Câmera\" > \"Permitir\"."];
      if (marca === "xiaomi") {
        passos.push("Se continuar bloqueada: Configurações do celular > Apps > Gerenciar apps > o navegador > Permissões do app > Câmera > Permitir.");
      } else {
        passos.push("Se continuar bloqueada: Configurações do celular > Apps > o navegador > Permissões > Câmera > Permitir.");
      }
      passos.push("Volte aqui e toque em TENTAR DE NOVO.");
      return passos;
    }
    return ["Clique no cadeado 🔒 ao lado do endereço do site.", "Em \"Câmera\", escolha \"Permitir\".",
            "Clique em TENTAR DE NOVO."];
  }

  function motivoDoErro(erro) {
    const texto = String((erro && (erro.name || erro.message)) || erro);
    if (/NotAllowed|Permission|Security/i.test(texto)) return "bloqueada";
    if (/NotFound|Devices|Overconstrained/i.test(texto)) return "sem-camera";
    if (/NotReadable|TrackStart|Abort/i.test(texto)) return "ocupada";
    if (/internet/i.test(texto)) return "sem-internet";
    return "outro";
  }

  // Situação da permissão sem perguntar nada: "granted" (já liberada), "denied" (bloqueada) ou
  // "prompt" (ainda vai perguntar). Navegador que não sabe dizer: trata como "prompt".
  function situacaoDaPermissao() {
    if (!navigator.permissions || !navigator.permissions.query) return Promise.resolve("prompt");
    return navigator.permissions.query({ name: "camera" }).then((p) => p.state, () => "prompt");
  }

  window.lerComCamera = function (aoLer) {
    prepararBip();
    const tela = document.createElement("div");
    tela.className = "camera-tela";
    tela.setAttribute("role", "dialog");
    tela.setAttribute("aria-modal", "true");
    tela.setAttribute("aria-label", "Ler código de barras com a câmera");
    tela.innerHTML = `
      <div class="camera-permissao" id="camera-explica"></div>
      <div class="camera-quadro oculto" id="camera-quadro"></div>
      <p class="camera-aviso" role="status"></p>
      <div class="camera-botoes">
        <button type="button" class="verde camera-principal oculto"></button>
        <button type="button" class="claro camera-fechar">✕ FECHAR</button>
      </div>`;
    document.body.append(tela);
    document.body.classList.add("com-folha");
    const explica = tela.querySelector("#camera-explica");
    const quadro = tela.querySelector("#camera-quadro");
    const aviso = tela.querySelector(".camera-aviso");
    const principal = tela.querySelector(".camera-principal");
    let leitor = null, acabou = false, acao = null;

    function botao(texto, fazer) {  // o botão grande verde da tela (PERMITIR / TENTAR DE NOVO)
      acao = fazer;
      principal.textContent = texto;
      principal.classList.toggle("oculto", !texto);
      if (texto) principal.focus();
    }
    principal.addEventListener("click", () => { if (acao) acao(); });

    function mostrarExplicacao(icone, titulo, texto, passos) {
      quadro.classList.add("oculto");
      explica.innerHTML = `<div class="camera-icone" aria-hidden="true">${icone}</div><h2></h2><p></p>`;
      explica.querySelector("h2").textContent = titulo;
      explica.querySelector("p").textContent = texto;
      if (passos) {
        const ol = document.createElement("ol");
        ol.className = "camera-passos";
        passos.forEach((p) => { const li = document.createElement("li"); li.textContent = p; ol.append(li); });
        explica.append(ol);
      }
      aviso.textContent = "";
    }

    function fechar() {
      if (acabou) return;
      acabou = true;
      const parar = leitor && leitor.isScanning ? leitor.stop().catch(() => {}) : Promise.resolve();
      parar.finally(() => {
        tela.remove();
        document.body.classList.remove("com-folha");
        document.removeEventListener("keydown", comEsc);
        document.removeEventListener("visibilitychange", saiu);
      });
    }
    const comEsc = (e) => { if (e.key === "Escape") fechar(); };
    const saiu = () => { if (document.hidden) fechar(); };  // trocou de app: desliga a câmera
    document.addEventListener("keydown", comEsc);
    document.addEventListener("visibilitychange", saiu);
    tela.querySelector(".camera-fechar").addEventListener("click", fechar);

    function deuErro(erro) {
      if (acabou) return;
      const motivo = motivoDoErro(erro);
      if (motivo === "bloqueada") {
        mostrarExplicacao("🔒", "A câmera está bloqueada", "Para ler o código de barras, libere a câmera para este site:", comoLiberar());
        botao("🔄 TENTAR DE NOVO", pedirPermissao);
      } else if (motivo === "sem-camera") {
        mostrarExplicacao("📷", "Não achei a câmera", "Este aparelho não tem câmera, ou ela não está funcionando.");
        botao("", null);
      } else if (motivo === "ocupada") {
        mostrarExplicacao("📷", "A câmera está ocupada", "Feche outro aplicativo que esteja usando a câmera (ou uma chamada de vídeo) e tente de novo.");
        botao("🔄 TENTAR DE NOVO", abrirCamera);
      } else if (motivo === "sem-internet") {
        mostrarExplicacao("📶", "Sem internet", "Preciso da internet para abrir o leitor da câmera. Confira o Wi-Fi ou os dados móveis.");
        botao("🔄 TENTAR DE NOVO", abrirCamera);
      } else {
        mostrarExplicacao("📷", "Não consegui abrir a câmera", "Feche esta tela e tente de novo.");
        botao("🔄 TENTAR DE NOVO", abrirCamera);
      }
    }

    // Pergunta do navegador ("Permitir que o site use a câmera?"). Vem de um toque no botão,
    // como iPhone e Android exigem. Depois de liberada, a câmera já abre para ler.
    function pedirPermissao() {
      aviso.textContent = "Responda a pergunta do celular: toque em \"Permitir\".";
      botao("", null);
      navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false })
        .then((stream) => { stream.getTracks().forEach((t) => t.stop()); abrirCamera(); })
        .catch(deuErro);
    }

    function opcoesDeLeitura() {
      return {
        fps: 15,
        aspectRatio: 1.6,
        // quadro largo e baixo, do jeito do código de barras
        qrbox: (w, h) => ({ width: Math.floor(w * 0.9), height: Math.floor(Math.min(h * 0.45, w * 0.45)) }),
      };
    }
    // Duas leituras iguais seguidas: evita número errado quando a câmera ainda está focando.
    let ultimaLeitura = "";
    function aoAchar(codigo) {
      if (acabou) return;
      const lido = String(codigo).trim();
      if (lido !== ultimaLeitura) { ultimaLeitura = lido; return; }
      bip();
      fechar();
      aoLer(lido);
    }

    function abrirCamera() {
      explica.innerHTML = "";
      botao("", null);
      quadro.classList.remove("oculto");
      aviso.textContent = "Abrindo a câmera...";
      carregar()
        .then(() => {
          if (acabou) return null;
          if (!leitor) {
            // o leitor rápido de código que já vem no Android (Chrome) é usado quando existe
            const F = window.Html5QrcodeSupportedFormats;
            leitor = new window.Html5Qrcode("camera-quadro", { verbose: false,
              formatsToSupport: [F.EAN_13, F.EAN_8, F.UPC_A, F.UPC_E, F.CODE_128, F.CODE_39, F.ITF],
              experimentalFeatures: { useBarCodeDetectorIfSupported: true } });
          }
          // câmera de trás; se o aparelho não aceitar o pedido assim (alguns Xiaomi e Motorola
          // antigos), procura na lista a câmera de trás pelo nome, ou usa a última da lista
          return leitor.start({ facingMode: "environment" }, opcoesDeLeitura(), aoAchar, () => {})
            .catch((erro) => {
              if (motivoDoErro(erro) === "bloqueada") throw erro;
              return window.Html5Qrcode.getCameras().then((cameras) => {
                if (!cameras.length) throw new Error("NotFound");
                const tras = cameras.find((c) => /back|rear|traseira|environment|trás|0, facing back/i.test(c.label))
                  || cameras[cameras.length - 1];
                return leitor.start(tras.id, opcoesDeLeitura(), aoAchar, () => {});
              });
            });
        })
        .then(() => {
          // fechou enquanto a câmera ainda estava abrindo: desliga a câmera
          if (acabou) { if (leitor && leitor.isScanning) leitor.stop().catch(() => {}); return; }
          // iPhone: o vídeo tem que tocar dentro da página (sem abrir em tela cheia) e sem som
          quadro.querySelectorAll("video").forEach((v) => {
            v.setAttribute("playsinline", ""); v.setAttribute("muted", ""); v.muted = true;
          });
          aviso.textContent = "Deixe o código de barras deitado dentro do quadro e segure parado até ouvir o bip.";
        })
        .catch(deuErro);
    }

    // ---- começo: confere se dá para usar a câmera neste aparelho ----
    if (!window.isSecureContext) {
      mostrarExplicacao("🔒", "Câmera só no link seguro",
        "O celular só libera a câmera quando o site abre com https (pelo link da internet). Pelo Wi-Fi de casa (http) ela fica bloqueada.");
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      mostrarExplicacao("📷", "Este navegador não abre a câmera",
        aparelho.navegador === "dentro-de-app" ? "Abra o link no navegador do celular:" : "Abra o sistema no Chrome (Android) ou no Safari (iPhone).",
        aparelho.navegador === "dentro-de-app" ? comoLiberar() : null);
      return;
    }
    situacaoDaPermissao().then((situacao) => {
      if (acabou) return;
      if (situacao === "granted") { abrirCamera(); return; }
      if (situacao === "denied") { deuErro({ name: "NotAllowedError" }); return; }
      // ainda não liberou: explica para que é e pede a permissão
      mostrarExplicacao("📷", "Usar a câmera para ler o código de barras?",
        "O sistema vai pedir permissão para usar a câmera do celular. Ela só é usada para ler o código do produto, e desliga sozinha quando fecha esta tela.");
      botao("✅ PERMITIR A CÂMERA", pedirPermissao);
    });
  };
})();
