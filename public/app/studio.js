import { HailaApi } from "./api.js";
import { demoEvents, demoQuestion } from "./demo.js";
import { registerStudioTools } from "./webmcp.js";

const byId = (id) => document.getElementById(id);
const api = new HailaApi();
const levels = ["Introdutória", "Básica", "Intermediária", "Alta", "Avançada"];
const state = { busy: false, connected: false, mode: "empty", result: null, history: null };

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function setNotice(message, tone = "info") {
  const notice = byId("notice");
  notice.textContent = message ?? "";
  notice.dataset.tone = tone;
  notice.hidden = !message;
}

function setTab(name) {
  for (const key of ["question", "trace"]) {
    const active = key === name;
    byId(`${key}-tab`).setAttribute("aria-selected", String(active));
    byId(`${key}-tab`).tabIndex = active ? 0 : -1;
    byId(`${key}-view`).hidden = !active;
  }
}

async function checkHealth() {
  const button = byId("connection");
  button.textContent = "Verificando conexão…";
  try {
    const health = await api.health();
    state.connected = Boolean(health.llm_configured && health.slm_configured);
    button.textContent = state.connected ? "Motor conectado" : "Motor com configuração pendente";
    button.classList.toggle("online", state.connected);
    button.title = "Clique para verificar novamente";
  } catch {
    state.connected = false;
    button.textContent = "Motor desconectado · verificar";
    button.classList.remove("online");
    button.title = "Inicie a API HAILA e clique para verificar novamente.";
  }
  return state.connected;
}

function renderQuestion(question, { demo = false } = {}) {
  byId("empty").hidden = true;
  byId("question").hidden = false;
  const root = byId("question");
  root.replaceChildren();
  root.append(element("div", demo ? "EXEMPLO ILUSTRATIVO · ENADE" : "ENADE · ITEM GERADO", "question-meta"));
  root.append(element("p", question.enunciado, "stem"));

  (question.alternativas ?? []).forEach((answer, index) => {
    const correct = index === question.correta;
    const option = element("div", undefined, `option${correct ? " correct" : ""}`);
    option.append(element("b", String.fromCharCode(65 + index)), element("span", answer));
    root.append(option);
  });

  const explanation = element("section", undefined, "explanation");
  explanation.append(
    element("strong", `Gabarito: ${String.fromCharCode(65 + question.correta)}`),
    element("p", question.explicacao || "Sem justificativa retornada."),
  );
  root.append(explanation);
  byId("export").disabled = false;
  byId("result-footnote").textContent = demo
    ? "Exemplo ilustrativo. Não gerado pelos modelos."
    : "Item gerado. Faça a revisão pedagógica antes do uso.";
}

function renderHistory(data, { demo = false } = {}) {
  state.history = data;
  const events = byId("events");
  events.replaceChildren();
  const items = demo ? demoEvents : data?.events ?? [];
  if (!items.length) items.push({ component: "HAILA", reason: "Aguardando o primeiro evento" });

  for (const event of items) {
    const item = element("li", event.reason || event.to_state);
    const time = event.created_at ? ` · ${new Date(event.created_at).toLocaleTimeString("pt-BR")}` : "";
    item.append(element("small", `${event.component}${time}`));
    events.append(item);
  }

  const flags = byId("flags");
  flags.replaceChildren();
  if (data?.red_flags?.length) {
    flags.append(element("strong", "Alertas registrados nas tentativas"));
    for (const flag of data.red_flags) {
      flags.append(element("p", flag.evidence || flag.evidencia || flag.code));
    }
  }
}

function setFormValues(values) {
  if (values.course) byId("course").value = values.course;
  if (values.knowledgeObject !== undefined) byId("subject").value = values.knowledgeObject;
  if (values.objective) byId("objective").value = values.objective;
  if (values.difficulty) {
    byId("difficulty").value = values.difficulty;
    updateDifficultyLabel();
  }
  byId("objective").focus();
}

function showDemo() {
  if (state.busy) return;
  state.mode = "demo";
  state.result = { demo: true, version: { question: demoQuestion } };
  state.history = null;
  setNotice("Demonstração: este conteúdo é ilustrativo e não representa uma execução ou avaliação dos modelos.");
  renderQuestion(demoQuestion, { demo: true });
  renderHistory(null, { demo: true });
  byId("result-status").textContent = "Demonstração";
  setTab("question");
  setFormValues({
    knowledgeObject: "Banco de dados relacionais",
    objective: "Analisar estratégias de controle de concorrência para preservar a consistência de transações em um banco de dados relacional.",
  });
}

function updateDifficultyLabel() {
  const value = Number(byId("difficulty").value);
  byId("difficulty-value").textContent = `${value} · ${levels[value - 1]}`;
}

function buildPayload(form) {
  const fields = new FormData(form);
  const payload = {
    solicitante_id: "haila-studio",
    curso: fields.get("curso").trim(),
    exame: "ENADE",
    componente: fields.get("componente"),
    objetivo_pedagogico: fields.get("objetivo_pedagogico").trim(),
    dificuldade: Number(fields.get("dificuldade")),
    restricoes: fields.get("restricoes").split("\n").map((item) => item.trim()).filter(Boolean),
    max_tentativas: 3,
    max_tentativas_distratores: 3,
  };
  for (const key of ["competencia", "habilidade", "objeto_conhecimento"]) {
    payload[key] = fields.get(key).trim() || null;
  }
  return payload;
}

async function generate(event) {
  event.preventDefault();
  if (state.busy) return;
  state.busy = true;
  state.mode = "generating";
  document.body.classList.add("busy");
  byId("generate").disabled = true;
  byId("example").disabled = true;
  byId("export").disabled = true;
  byId("question").hidden = true;
  byId("empty").hidden = false;
  byId("result-status").textContent = "Conectando…";
  setNotice("Verificando o motor antes de iniciar a geração.");

  let poll;
  let requestId;
  try {
    const health = await api.health();
    if (!health.llm_configured || !health.slm_configured) {
      throw new Error("O motor precisa ter LLM e SLM configurados para gerar uma questão.");
    }

    const request = await api.createRequest(buildPayload(event.currentTarget));
    requestId = request.id;
    byId("result-status").textContent = "Geração em andamento";
    setNotice("O motor está trabalhando. Acompanhe os eventos em Rastreabilidade.");
    renderHistory({ events: [], red_flags: [] });
    setTab("trace");

    let polling = false;
    poll = setInterval(async () => {
      if (polling) return;
      polling = true;
      try {
        renderHistory(await api.history(requestId));
      } catch {
        // A chamada principal continua sendo a fonte de verdade da geração.
      } finally {
        polling = false;
      }
    }, 4_000);

    state.result = await api.generate(requestId);
    clearInterval(poll);
    try {
      renderHistory(await api.history(requestId));
    } catch {
      // O resultado final ainda pode ser apresentado sem o histórico.
    }

    if (state.result.state === "GENERATION_COMPLETED" && state.result.version?.question) {
      state.mode = "complete";
      renderQuestion(state.result.version.question);
      byId("result-status").textContent = "Geração concluída";
      setNotice("Verificação automática concluída sem red flags. A revisão humana ainda é necessária.", "success");
      setTab("question");
    } else {
      state.mode = "review";
      byId("result-status").textContent = "Revisão necessária";
      setNotice("O motor esgotou as tentativas sem concluir um item válido. Consulte os alertas e ajuste os parâmetros.", "warning");
      byId("export").disabled = false;
    }
  } catch (error) {
    state.mode = "error";
    byId("result-status").textContent = "Geração não concluída";
    const suffix = requestId
      ? ` Solicitação: ${requestId}. O processamento pode continuar no motor; consulte a rastreabilidade antes de iniciar outra geração.`
      : "";
    setNotice(`${error.message}${suffix}`, "error");
    if (requestId) {
      try {
        renderHistory(await api.history(requestId));
      } catch {
        // A mensagem principal já informa a falha de conexão.
      }
    }
  } finally {
    clearInterval(poll);
    state.busy = false;
    document.body.classList.remove("busy");
    byId("generate").disabled = false;
    byId("example").disabled = false;
    checkHealth();
  }
}

function exportResult() {
  if (!state.result) return;
  const content = JSON.stringify({ ...state.result, history: state.history }, null, 2);
  const url = URL.createObjectURL(new Blob([content], { type: "application/json" }));
  const link = element("a");
  link.href = url;
  link.download = state.result.demo ? "haila-exemplo.json" : `haila-${state.result.request_id}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

byId("difficulty").addEventListener("input", updateDifficultyLabel);
byId("connection").addEventListener("click", checkHealth);
byId("example").addEventListener("click", showDemo);
byId("question-form").addEventListener("submit", generate);
byId("export").addEventListener("click", exportResult);

for (const key of ["question", "trace"]) {
  byId(`${key}-tab`).addEventListener("click", () => setTab(key));
  byId(`${key}-tab`).addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? "question" : event.key === "End" ? "trace" : key === "question" ? "trace" : "question";
    setTab(next);
    byId(`${next}-tab`).focus();
  });
}

registerStudioTools({
  openDemo: showDemo,
  setFormValues,
  readStatus: () => ({ connected: state.connected, mode: state.mode, busy: state.busy }),
});

checkHealth();
if (new URLSearchParams(location.search).get("demo") === "1") showDemo();
