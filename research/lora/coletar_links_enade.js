// Cole no console do navegador (F12 > Console) na página "Provas e Gabaritos" do Enade
// DEPOIS de clicar em cada aba de ano que quiser (as abas carregam sob demanda).
// O resultado é copiado para a área de transferência: cole em enade/links.txt.
(() => {
  const CURSOS = /ci[êe]ncias? da computa[çc][ãa]o|engenharia de computa[çc][ãa]o|sistemas? de informa[çc][ãa]o|^\s*computa[çc][ãa]o/i;
  const TIPO = /^\s*(prova|gabarito)\s*$/i;
  const titulo = (el) => /^H[1-6]$/.test(el.tagName);
  const anoDe = (h) => {
    for (let el = h; el; el = el.parentElement) {
      for (let p = el.previousElementSibling; p; p = p.previousElementSibling) {
        const m = /^\s*(20\d\d)\s*$/.exec(p.textContent || "");
        if (m && (titulo(p) || p.getAttribute("role") === "tab")) return m[1];
      }
      const rotulo = el.getAttribute && (el.getAttribute("aria-labelledby") || el.id || "");
      const m = /(20\d\d)/.exec(rotulo || "");
      if (m) return m[1];
    }
    return null;
  };
  const linhas = new Set();
  document.querySelectorAll("h1,h2,h3,h4,h5,h6,strong").forEach((h) => {
    const curso = (h.textContent || "").trim();
    if (!CURSOS.test(curso) || curso.length > 90) return;
    const links = [];
    const cabecalho = titulo(h) ? h : h.closest("p,div,li") || h;
    for (let n = cabecalho.nextElementSibling; n && !titulo(n) && !(n.querySelector && n.querySelector("h1,h2,h3,h4,h5,h6")); n = n.nextElementSibling) {
      if (n.tagName === "A") links.push(n); else n.querySelectorAll && links.push(...n.querySelectorAll("a"));
    }
    if (cabecalho !== h) links.push(...cabecalho.querySelectorAll("a"));
    for (const a of links) {
      const tipo = (a.textContent || "").trim();
      if (!TIPO.test(tipo)) continue; // ignora Ledor, Ampliada, Padrão de resposta
      const ano = anoDe(h) || ((/(20\d\d)/.exec(a.href) || [])[1]) || "ano?";
      linhas.add([ano, curso.replace(/\s+/g, " "), tipo.toLowerCase(), a.href].join(" | "));
    }
  });
  const texto = [...linhas].sort().join("\n");
  console.log(texto || "Nenhum link encontrado: clique nas abas dos anos e rode de novo.");
  console.log(`${linhas.size} links`);
  if (typeof copy === "function" && texto) { copy(texto); console.log("Copiado: cole em enade/links.txt"); }
  return linhas.size;
})();
