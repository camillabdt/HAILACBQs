import { HailaApi } from "./api.js?v=20260920-9";
import { demoEvents, demoQuestion } from "./demo.js?v=20260920-9";
import { registerStudioTools } from "./webmcp.js?v=20260920-9";

const byId = (id) => document.getElementById(id);
const api = new HailaApi();
const levels = ["Introdutória", "Básica", "Intermediária", "Alta", "Avançada"];
const state = {
  busy: false,
  connected: false,
  backendCompatible: false,
  mode: "empty",
  result: null,
  history: null,
  batchResults: [],
  activeBatchIndex: -1,
  auditConfig: { owner: 100, guest: 0 },
};
const STORAGE_KEY = "haila:last-request-id";
const REQUIRED_API_BUILD = "20260924-17";

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function setNotice(message, tone = "info", action = null) {
  const notice = byId("notice");
  notice.replaceChildren(document.createTextNode(message ?? ""));
  if (message && action?.label && action?.handler) {
    const button = element("button", action.label, "notice-action");
    button.type = "button";
    button.addEventListener("click", action.handler);
    notice.append(button);
  }
  notice.dataset.tone = tone;
  notice.hidden = !message;
}

function setExportAvailability({ data = false, question = false, flags = false } = {}) {
  byId("export-json").disabled = !data;
  byId("export-html").disabled = !question;
  byId("export-pdf").disabled = !question;
  byId("export-flags").disabled = !flags;
}

function renderPlaceholder({ eyebrow, title, message, symbol = "!", actionLabel = null, onAction = null }) {
  const root = byId("empty");
  root.classList.remove("generation-loader");
  root.replaceChildren();
  root.append(
    element("div", symbol, "empty-symbol"),
    element("span", eyebrow, "eyebrow"),
    element("h3", title),
    element("p", message),
  );
  if (actionLabel && onAction) {
    const action = element("button", actionLabel, "secondary");
    action.type = "button";
    action.addEventListener("click", onAction);
    root.append(action);
  }
  root.hidden = false;
}

function renderFailureState(record) {
  const rateLimited = record?.errorStatus === 429;
  renderPlaceholder({
    eyebrow: rateLimited ? "LIMITE TEMPORÁRIO DA GROQ" : "GERAÇÃO NÃO CONCLUÍDA",
    title: rateLimited ? "A geração precisa aguardar." : "Não foi possível gerar esta questão.",
    message: record?.error || "Consulte a rastreabilidade para entender o que aconteceu.",
    symbol: rateLimited ? "◷" : "!",
    actionLabel: "Ver rastreabilidade →",
    onAction: () => setTab("trace"),
  });
  byId("result-footnote").textContent = "Os dados da tentativa e as red flags continuam disponíveis para exportação.";
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
    const compatible = health.build === REQUIRED_API_BUILD;
    state.backendCompatible = compatible;
    state.connected = Boolean(compatible && health.llm_configured && health.slm_configured);
    button.textContent = !compatible
      ? "Motor precisa reiniciar"
      : state.connected ? "Motor conectado" : "Motor com configuração pendente";
    button.classList.toggle("online", state.connected);
    button.title = compatible
      ? "Clique para verificar novamente"
      : "Reinicie ./iniciar_haila_web.sh para carregar a correção do motor.";
  } catch {
    state.connected = false;
    state.backendCompatible = false;
    button.textContent = "Motor desconectado · verificar";
    button.classList.remove("online");
    button.title = "Inicie a API HAILA e clique para verificar novamente.";
  }
  return state.connected;
}

async function configureGroq() {
  await checkHealth();
  if (!state.backendCompatible) {
    setNotice("O motor ainda executa uma versão antiga. Encerre o servidor no terminal com Ctrl+C e inicie ./iniciar_haila_web.sh novamente.", "error");
    byId("result-status").textContent = "Motor precisa reiniciar";
    return;
  }
  const keyField = byId("groq-key");
  const button = byId("save-groq");
  const apiKey = keyField.value.trim();
  if (!apiKey) {
    setNotice("Informe a chave da Groq para configurar esta sessão.", "warning");
    keyField.focus();
    return;
  }
  button.disabled = true;
  button.textContent = "Verificando chave…";
  try {
    const result = await api.configureGroq(apiKey, fieldValue("groq-model"));
    keyField.value = "";
    byId("groq-status").textContent = `Configurado: ${result.modelo}`;
    keyField.closest("details").open = false;
    setNotice("Chave validada. Agora preencha o objetivo e clique em Gerar questão.", "success");
    byId("result-status").textContent = "Pronto para gerar";
    await checkHealth();
  } catch (error) {
    setNotice(error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = "Usar nesta sessão";
  }
}

async function loadGroqSettings() {
  try {
    const settings = await api.groqSettings();
    if ([...byId("groq-model").options].some((option) => option.value === settings.modelo)) {
      byId("groq-model").value = settings.modelo;
    }
    byId("groq-status").textContent = settings.configured
      ? `Configurado: ${settings.modelo}`
      : "Chave ainda não configurada";
  } catch {
    byId("groq-status").textContent = "Configuração indisponível";
  }
}

async function restoreLastRequest() {
  const requestId = localStorage.getItem(STORAGE_KEY);
  if (!requestId || state.busy || state.result) return;
  try {
    const history = await api.history(requestId);
    state.history = history;
    renderHistory(history);
    if (history.request?.state === "GENERATION_COMPLETED" && history.latest_version?.question) {
      state.mode = "complete";
      state.result = {
        request_id: requestId,
        state: history.request?.state,
        version: history.latest_version,
      };
      renderQuestion(history.latest_version.question);
      byId("result-status").textContent = "Última geração recuperada";
      setNotice("A última questão foi recuperada do banco local do HAILA.", "success");
      setTab("question");
      return;
    }
    const providerError = [...(history.artifacts ?? [])]
      .reverse()
      .find((artifact) => artifact.kind === "provider_error");
    const error = providerError?.payload?.message
      || providerError?.payload?.mensagem
      || (history.latest_version?.question
        ? "Esta questão foi apenas montada; a revisão automática não foi concluída. Ela não pode ser usada nem exportada como questão final."
        : "A última geração não foi concluída. Consulte a rastreabilidade.");
    const record = {
      index: 0,
      requestId,
      result: { request_id: requestId, state: history.request?.state || "GENERATION_FAILED" },
      history,
      error,
      errorStatus: providerError?.payload?.status === 429 ? 429 : null,
    };
    state.mode = "review";
    state.batchResults = [record];
    selectBatchResult(0);
    byId("result-status").textContent = record.errorStatus === 429
      ? "Limite da Groq atingido"
      : "Última geração não concluída";
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
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
  setExportAvailability({ data: !state.busy, question: !state.busy, flags: !state.busy });
  byId("result-footnote").textContent = demo
    ? "Exemplo ilustrativo. Não gerado pelos modelos."
    : "Item gerado. Faça a revisão pedagógica antes do uso.";
  byId("review-panel").hidden = demo;
  if (!demo) renderReviewPanel();
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
  if (!demo && !byId("review-panel").hidden) renderReviewPanel();
}

function auditIsAssigned(percentage, index) {
  if (percentage === 100) return true;
  if (percentage === 50) return index % 2 === 0;
  return false;
}

function readAuditConfig() {
  return {
    owner: Number(fieldValue("audit-owner")),
    guest: Number(fieldValue("audit-guest")),
  };
}

function currentRecord() {
  return state.batchResults[state.activeBatchIndex] ?? {
    requestId: state.result?.request_id,
    result: state.result,
    history: state.history,
    index: Math.max(0, state.activeBatchIndex),
  };
}

function renderReviewPanel() {
  const panel = byId("review-panel");
  if (state.mode === "demo" || !activeQuestion()) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const record = currentRecord();
  const index = Math.max(0, record.index ?? state.activeBatchIndex);
  const assignments = byId("audit-assignments");
  assignments.replaceChildren();
  const roles = [
    ["Professor responsável", state.auditConfig.owner],
    ["Professor convidado", state.auditConfig.guest],
  ];
  for (const [label, percentage] of roles) {
    if (auditIsAssigned(percentage, index)) {
      assignments.append(element("span", `${label} · ${percentage}%`, "audit-badge"));
    }
  }

  const reviews = byId("reviews");
  reviews.replaceChildren();
  for (const review of record.history?.reviews ?? []) {
    const approved = review.decision === "APROVAR";
    const card = element("div", undefined, `review-card ${approved ? "approved" : "rejected"}`);
    card.append(
      element("strong", `${approved ? "Aprovada" : "Rejeitada"} · ${review.reviewer_name}`),
      element("small", `${review.reviewer_role.replaceAll("_", " ")} · cobertura ${review.audit_percentage}%`),
    );
    if (review.comments) card.append(element("p", review.comments));
    reviews.append(card);
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
  state.batchResults = [];
  state.activeBatchIndex = -1;
  byId("batch-results").hidden = true;
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

function updateQuantityLabel() {
  const quantity = Math.min(10, Math.max(1, Number.parseInt(fieldValue("quantity"), 10) || 1));
  const button = byId("generate");
  button.replaceChildren(
    document.createTextNode(quantity === 1 ? "Gerar questão " : `Gerar ${quantity} questões `),
    element("span", "↗"),
  );
}

const generationStages = {
  preparing: {
    eyebrow: "INICIANDO A MISSÃO",
    title: "Aquecendo as turbinas…",
    message: "Preparando os modelos para transformar sua intenção pedagógica em uma boa questão.",
    short: "aquecendo as turbinas",
    step: 0,
  },
  reference: {
    eyebrow: "RAG EM AÇÃO",
    title: "Mergulhando nas referências…",
    message: "A HAILA está buscando uma base confiável para orientar o conteúdo.",
    short: "consultando referências",
    step: 1,
  },
  nucleus: {
    eyebrow: "LLM EM AÇÃO",
    title: "Dando forma a uma questão poderosa…",
    message: "Construindo o cenário, o gabarito e uma explicação coerente com o objetivo.",
    short: "construindo o núcleo",
    step: 2,
  },
  distractors: {
    eyebrow: "SLM EM AÇÃO",
    title: "Criando alternativas que desafiam…",
    message: "Produzindo distratores plausíveis para a questão exigir conhecimento de verdade.",
    short: "criando distratores",
    step: 3,
  },
  checking: {
    eyebrow: "CHECAGEM FINAL",
    title: "Deixando a questão bombástica…",
    message: "Conferindo estrutura, alternativas e sinais de alerta antes de liberar o resultado.",
    short: "fazendo a checagem final",
    step: 4,
  },
  retrying: {
    eyebrow: "AJUSTANDO A ROTA",
    title: "Lapidando mais um pouco…",
    message: "Um alerta foi encontrado. A HAILA está corrigindo a etapa necessária.",
    short: "regenerando com cuidado",
    step: 2,
  },
};

function generationStage(history) {
  const latest = (history?.events?.at(-1)?.reason || "").toLocaleLowerCase("pt-BR");
  if (latest.includes("bloqueado") || latest.includes("nova tentativa")) return "retrying";
  if (latest.includes("distratores gerados") || latest.includes("item montado")) return "checking";
  if (latest.includes("núcleo gerado")) return "distractors";
  if (latest.includes("referência")) return "nucleus";
  if (latest.includes("solicitação registrada")) return "reference";
  return "preparing";
}

function renderGenerationLoader(index, total, stageName = "preparing") {
  const stage = generationStages[stageName] || generationStages.preparing;
  const root = byId("empty");
  root.classList.add("generation-loader");
  root.replaceChildren();

  const visual = element("div", undefined, "loader-visual");
  visual.setAttribute("aria-hidden", "true");
  visual.append(
    element("span", "h", "loader-core"),
    element("span", undefined, "loader-orbit orbit-one"),
    element("span", undefined, "loader-orbit orbit-two"),
    element("span", "✦", "loader-spark spark-one"),
    element("span", "✦", "loader-spark spark-two"),
  );

  const progress = element("div", undefined, "loader-progress");
  for (let step = 1; step <= 4; step += 1) {
    progress.append(element("span", undefined, step <= stage.step ? "active" : ""));
  }

  root.append(
    visual,
    element("span", stage.eyebrow, "eyebrow loader-eyebrow"),
    element("h3", stage.title),
    element("p", stage.message),
    progress,
    element("small", `Questão ${index + 1} de ${total} · você pode acompanhar os detalhes em Rastreabilidade.`),
  );
  root.hidden = false;
}

function setGenerateProgress(index, total, history = null) {
  const stageName = generationStage(history);
  const stage = generationStages[stageName];
  renderGenerationLoader(index, total, stageName);
  byId("generate").replaceChildren(
    document.createTextNode(`Questão ${index + 1} de ${total} · ${stage.short} `),
    element("span", "●", "button-progress"),
  );
}

function fieldValue(id) {
  const field = byId(id);
  return typeof field?.value === "string" ? field.value : "";
}

function buildPayload() {
  const payload = {
    solicitante_id: "haila-studio",
    curso: fieldValue("course").trim(),
    exame: "ENADE",
    componente: fieldValue("component"),
    objetivo_pedagogico: fieldValue("objective").trim(),
    dificuldade: Number(fieldValue("difficulty")),
    restricoes: fieldValue("constraints").split("\n").map((item) => item.trim()).filter(Boolean),
    max_tentativas: 3,
    max_tentativas_distratores: 3,
    competencia: fieldValue("competence").trim() || null,
    habilidade: fieldValue("skill").trim() || null,
    objeto_conhecimento: fieldValue("subject").trim() || null,
  };
  return payload;
}

function isCompleted(record) {
  return Boolean(
    record?.result?.state === "GENERATION_COMPLETED"
    && record.result.version?.question,
  );
}

function selectBatchResult(index) {
  const record = state.batchResults[index];
  if (!record) return;
  state.activeBatchIndex = index;
  state.result = record.result ?? {
    request_id: record.requestId,
    state: "GENERATION_FAILED",
    error: record.error,
  };
  state.history = record.history ?? null;
  renderBatchResults();
  renderHistory(state.history ?? { events: [], red_flags: [] });

  if (isCompleted(record)) {
    renderQuestion(record.result.version.question);
    byId("result-status").textContent = `Questão ${index + 1} concluída`;
    setNotice("Questão concluída. Faça a revisão pedagógica antes do uso.", "success");
    setTab("question");
    return;
  }

  byId("question").hidden = true;
  byId("review-panel").hidden = true;
  renderFailureState(record);
  byId("result-status").textContent = `Questão ${index + 1} não concluída`;
  setNotice(record.error || "O motor não concluiu esta questão. Consulte a rastreabilidade.", "warning");
  setExportAvailability({ data: true, question: false, flags: true });
  setTab("question");
}

function renderBatchResults() {
  const root = byId("batch-results");
  root.replaceChildren();
  root.hidden = state.batchResults.length <= 1;
  const completedCount = state.batchResults.filter(isCompleted).length;
  root.append(element(
    "span",
    `Lote · ${completedCount}/${state.batchResults.length} concluídas`,
    "batch-label",
  ));
  state.batchResults.forEach((record, index) => {
    const completed = isCompleted(record);
    const button = element(
      "button",
      String(index + 1),
      `batch-item ${completed ? "complete" : "failed"}${index === state.activeBatchIndex ? " active" : ""}`,
    );
    button.type = "button";
    button.title = `Questão ${index + 1} · ${completed ? "concluída" : "não concluída"}`;
    button.setAttribute("aria-label", button.title);
    button.addEventListener("click", () => selectBatchResult(index));
    root.append(button);
  });
}

async function generateOne(payload, index, total) {
  let poll;
  let requestId;
  let history = null;
  try {
    const request = await api.createRequest(payload);
    requestId = request.id;
    localStorage.setItem(STORAGE_KEY, requestId);
    byId("result-status").textContent = `Gerando ${index + 1} de ${total}`;
    setGenerateProgress(index, total);
    setNotice(`Questão ${index + 1} de ${total}: a HAILA entrou em ação. Você pode acompanhar cada etapa em Rastreabilidade.`);
    renderHistory({ events: [], red_flags: [] });
    setTab("question");

    let polling = false;
    poll = setInterval(async () => {
      if (polling) return;
      polling = true;
      try {
        history = await api.history(requestId);
        renderHistory(history);
        setGenerateProgress(index, total, history);
      } catch {
        // A geração principal continua sendo a fonte de verdade.
      } finally {
        polling = false;
      }
    }, 4_000);

    const result = await api.generate(requestId);
    clearInterval(poll);
    try {
      history = await api.history(requestId);
      renderHistory(history);
    } catch {
      // O resultado pode ser mantido mesmo sem o histórico final.
    }
    return { index, requestId, result, history };
  } catch (error) {
    if (requestId) {
      try {
        history = await api.history(requestId);
        renderHistory(history);
      } catch {
        // Mantém a mensagem original da falha.
      }
    }
    return { index, requestId, history, error: error.message, errorStatus: error.status ?? null };
  } finally {
    clearInterval(poll);
  }
}

async function generate(event) {
  event.preventDefault();
  if (state.busy) return;
  state.busy = true;
  state.mode = "generating";
  document.body.classList.add("busy");
  byId("generate").disabled = true;
  const exampleButton = byId("example");
  if (exampleButton) exampleButton.disabled = true;
  byId("quantity").disabled = true;
  byId("generate").replaceChildren(
    document.createTextNode("Preparando geração "),
    element("span", "●", "button-progress"),
  );
  setExportAvailability();
  state.batchResults = [];
  state.activeBatchIndex = -1;
  renderBatchResults();
  byId("question").hidden = true;
  renderGenerationLoader(0, Math.min(10, Math.max(1, Number.parseInt(fieldValue("quantity"), 10) || 1)));
  byId("result-status").textContent = "Conectando…";
  setNotice("Verificando o motor antes de iniciar a geração.");

  try {
    const health = await api.health();
    if (health.build !== REQUIRED_API_BUILD) {
      throw new Error("O backend ainda está na versão anterior. Reinicie ./iniciar_haila_web.sh e tente novamente.");
    }
    if (!health.llm_configured || !health.slm_configured) {
      throw new Error("O motor precisa ter LLM e SLM configurados para gerar uma questão.");
    }
    const quantity = Math.min(10, Math.max(1, Number.parseInt(fieldValue("quantity"), 10) || 1));
    byId("quantity").value = String(quantity);
    state.auditConfig = readAuditConfig();
    const payload = buildPayload();

    for (let index = 0; index < quantity; index += 1) {
      const record = await generateOne(payload, index, quantity);
      state.batchResults.push(record);
      state.activeBatchIndex = index;
      renderBatchResults();
      if (isCompleted(record)) {
        state.result = record.result;
        state.history = record.history;
        renderQuestion(record.result.version.question);
      }
      if (record.errorStatus === 429) break;
    }

    const completed = state.batchResults.filter(isCompleted).length;
    let lastCompletedIndex = -1;
    for (let index = state.batchResults.length - 1; index >= 0; index -= 1) {
      if (isCompleted(state.batchResults[index])) {
        lastCompletedIndex = index;
        break;
      }
    }
    const selectedIndex = lastCompletedIndex >= 0 ? lastCompletedIndex : state.batchResults.length - 1;
    selectBatchResult(selectedIndex);

    const attempted = state.batchResults.length;
    const rateLimited = state.batchResults.some((record) => record.errorStatus === 429);
    if (completed === quantity) {
      state.mode = "complete";
      byId("result-status").textContent = quantity === 1 ? "Geração concluída" : `${completed} questões concluídas`;
      setNotice(`${completed} de ${quantity} questões foram concluídas. A revisão humana ainda é necessária.`, "success");
    } else if (completed > 0) {
      state.mode = "review";
      byId("result-status").textContent = `${completed} de ${quantity} concluídas`;
      setNotice(
        rateLimited
          ? `${completed} questão(ões) concluída(s). O restante do lote foi interrompido porque o limite da Groq foi atingido.`
          : `${completed} de ${quantity} questões foram concluídas. Use os botões acima para revisar cada resultado.`,
        "warning",
      );
    } else {
      state.mode = "review";
      byId("result-status").textContent = rateLimited
        ? "Limite da Groq atingido"
        : quantity === 1 ? "Geração não concluída" : "Lote não concluído";
      setNotice(
        rateLimited
          ? "Limite da Groq atingido. Aguarde a renovação da cota ou escolha outro modelo na Configuração Groq."
          : `Nenhuma das ${attempted} tentativa(s) foi concluída. Consulte a rastreabilidade.`,
        "warning",
      );
    }
  } catch (error) {
    state.mode = "error";
    byId("result-status").textContent = "Geração não concluída";
    setNotice(error.message, "error");
  } finally {
    state.busy = false;
    document.body.classList.remove("busy");
    byId("generate").disabled = false;
    if (exampleButton) exampleButton.disabled = false;
    byId("quantity").disabled = false;
    updateQuantityLabel();
    checkHealth();
  }
}

async function saveHumanReview(decision) {
  if (state.busy) return;
  const record = currentRecord();
  if (!record?.requestId || !isCompleted(record)) {
    setNotice("Selecione uma questão concluída para registrar o parecer.", "warning");
    return;
  }
  const role = fieldValue("review-role");
  const reviewerName = fieldValue("reviewer-name").trim();
  if (reviewerName.length < 2) {
    setNotice("Informe o nome de quem está avaliando.", "warning");
    byId("reviewer-name").focus();
    return;
  }
  const percentage = role === "PROFESSOR_RESPONSAVEL" ? state.auditConfig.owner : state.auditConfig.guest;
  if (!auditIsAssigned(percentage, record.index ?? state.activeBatchIndex)) {
    setNotice("Esta questão não foi incluída na cobertura configurada para esse avaliador.", "warning");
    return;
  }
  byId("approve-question").disabled = true;
  byId("reject-question").disabled = true;
  try {
    await api.saveReview(record.requestId, {
      reviewer_role: role,
      reviewer_name: reviewerName,
      decision,
      audit_percentage: percentage,
      comments: fieldValue("review-comments").trim(),
      red_flags: (record.history?.red_flags ?? []).map((flag) => flag.code),
    });
    record.history = await api.history(record.requestId);
    state.history = record.history;
    byId("review-comments").value = "";
    renderReviewPanel();
    setNotice(decision === "APROVAR" ? "Parecer de aprovação registrado." : "Parecer de rejeição registrado.", "success");
  } catch (error) {
    setNotice(error.message, "error");
  } finally {
    byId("approve-question").disabled = false;
    byId("reject-question").disabled = false;
  }
}

function download(content, type, filename) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = element("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function activeQuestion() {
  return state.result?.version?.question ?? null;
}

function questionDocument(question, { printable = false } = {}) {
  const options = (question.alternativas ?? []).map((answer, index) => {
    const letter = String.fromCharCode(65 + index);
    const correct = index === question.correta ? " class=\"correct\"" : "";
    return `<li${correct}><b>${letter}</b> ${escapeHtml(answer)}</li>`;
  }).join("");
  const autoPrint = printable ? "<script>addEventListener('load',()=>setTimeout(()=>print(),250))<\/script>" : "";
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Questão HAILA</title><style>body{font:16px/1.6 Arial,sans-serif;color:#172a24;max-width:850px;margin:40px auto;padding:0 28px}h1{font-size:22px}.meta{color:#527466;font-size:12px;letter-spacing:1px}.stem{white-space:pre-wrap}ol{list-style:none;padding:0}li{border:1px solid #dfe6e1;border-radius:8px;margin:10px 0;padding:12px}.correct{background:#f2f8ed;border-color:#a9c58e}.explanation{margin-top:28px;border-top:1px solid #dfe6e1;padding-top:18px;white-space:pre-wrap}@media print{body{margin:0;max-width:none}.correct{print-color-adjust:exact;-webkit-print-color-adjust:exact}}</style></head><body><div class="meta">HAILA · QUESTÃO ENADE</div><h1>Questão gerada</h1><p class="stem">${escapeHtml(question.enunciado)}</p><ol>${options}</ol><section class="explanation"><b>Gabarito: ${String.fromCharCode(65 + question.correta)}</b><p>${escapeHtml(question.explicacao || "Sem justificativa.")}</p></section>${autoPrint}</body></html>`;
}

function exportResult() {
  if (!state.result) return;
  const isBatch = state.batchResults.length > 1;
  const exportData = isBatch
    ? {
        generated_at: new Date().toISOString(),
        total: state.batchResults.length,
        completed: state.batchResults.filter(isCompleted).length,
        items: state.batchResults,
      }
    : { ...state.result, history: state.history };
  const filename = state.result.demo
    ? "haila-exemplo.json"
    : isBatch
      ? `haila-lote-${new Date().toISOString().replaceAll(":", "-")}.json`
      : `haila-${state.result.request_id}.json`;
  download(JSON.stringify(exportData, null, 2), "application/json", filename);
}

function exportHtml() {
  const question = activeQuestion();
  if (!question) {
    setNotice("Selecione uma questão concluída antes de exportar o HTML.", "warning");
    return;
  }
  download(questionDocument(question), "text/html;charset=utf-8", `haila-questao-${state.result.request_id || "exemplo"}.html`);
}

function exportPdf() {
  const question = activeQuestion();
  if (!question) {
    setNotice("Selecione uma questão concluída antes de exportar o PDF.", "warning");
    return;
  }
  const documentUrl = URL.createObjectURL(new Blob(
    [questionDocument(question, { printable: true })],
    { type: "text/html;charset=utf-8" },
  ));
  const printWindow = window.open(documentUrl, "_blank");
  if (!printWindow) {
    URL.revokeObjectURL(documentUrl);
    setNotice("O navegador bloqueou a janela de impressão. Permita pop-ups para salvar como PDF.", "warning");
    return;
  }
  setTimeout(() => URL.revokeObjectURL(documentUrl), 60_000);
}

function exportFlags() {
  const records = state.batchResults.length
    ? state.batchResults
    : [{ requestId: state.result?.request_id, history: state.history }];
  const report = records.map((record, index) => ({
    questao: index + 1,
    request_id: record.requestId,
    estado: record.result?.state ?? "NAO_CONCLUIDA",
    red_flags: record.history?.red_flags ?? [],
  }));
  download(
    JSON.stringify({ generated_at: new Date().toISOString(), items: report }, null, 2),
    "application/json",
    `haila-red-flags-${new Date().toISOString().replaceAll(":", "-")}.json`,
  );
}

byId("difficulty").addEventListener("input", updateDifficultyLabel);
byId("quantity").addEventListener("input", updateQuantityLabel);
byId("connection").addEventListener("click", checkHealth);
byId("save-groq").addEventListener("click", configureGroq);
byId("example").addEventListener("click", showDemo);
byId("question-form").addEventListener("submit", generate);
byId("export-json").addEventListener("click", exportResult);
byId("export-html").addEventListener("click", exportHtml);
byId("export-pdf").addEventListener("click", exportPdf);
byId("export-flags").addEventListener("click", exportFlags);
byId("approve-question").addEventListener("click", () => saveHumanReview("APROVAR"));
byId("reject-question").addEventListener("click", () => saveHumanReview("REJEITAR"));

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

Promise.all([checkHealth(), loadGroqSettings()]).then(async () => {
  await restoreLastRequest();
  if (!state.backendCompatible) {
    byId("result-status").textContent = "Motor precisa reiniciar";
    setNotice("A versão antiga do motor ainda está ativa. No terminal onde a HAILA roda: Ctrl+C e depois ./iniciar_haila_web.sh. A chave validada nessa sessão será perdida e precisará ser informada novamente.", "error");
  }
});
if (new URLSearchParams(location.search).get("demo") === "1") showDemo();
