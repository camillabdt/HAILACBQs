import { HailaApi } from "./api.js?v=20261021-front-final-v1";
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
  jurySettings: null,
};
const STORAGE_KEY = "haila:last-request-id";
function isCompatibleBackend(health) {
  return Boolean(
    health &&
    health.status === "ok" &&
    health.service === "HAILA" &&
    health.build
  );
}

function setStudioMode(mode) {
  const visualMode = mode === "complete" ? "review" : mode === "empty" ? "create" : mode;
  document.body.dataset.studioMode = visualMode;
  const createScreen = byId("create-screen");
  const resultScreen = byId("result-screen");
  if (createScreen) createScreen.hidden = visualMode !== "create";
  if (resultScreen) resultScreen.hidden = visualMode === "create";
}

function startNewQuestion() {
  if (state.busy) return;
  state.mode = "empty";
  setStudioMode("create");
  setTab("question");
  setNotice("");
  history.replaceState(null, "", "studio.html?new=1");
  window.scrollTo({ top: 0, behavior: "smooth" });
  setTimeout(() => byId("subject")?.focus(), 200);
}

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
  byId("export-csv").disabled = !data;
  byId("export-html").disabled = !question;
  byId("export-pdf").disabled = !question;
  byId("export-md").disabled = !question;
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
    const compatible = isCompatibleBackend(health);
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
  const forceNew = new URLSearchParams(location.search).get("new") === "1";
  if (forceNew) {
    state.mode = "empty";
    setStudioMode("create");
    return;
  }
  const requestId = localStorage.getItem(STORAGE_KEY);
  if (!requestId || state.busy || state.result) {
    setStudioMode("create");
    return;
  }
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
      setStudioMode("review");
      renderQuestion(history.latest_version.question);
      byId("result-status").textContent = "Última geração recuperada";
      setNotice("Última questão recuperada do banco local.", "success");
      setTab("question");
      return;
    }
    const providerError = [...(history.artifacts ?? [])]
      .reverse()
      .find((artifact) => artifact.kind === "provider_error");
    const error = providerError?.payload?.message
      || providerError?.payload?.mensagem
      || (history.latest_version?.question
        ? "A questão foi montada, mas a revisão automática não terminou."
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
    setStudioMode("review");
    selectBatchResult(0);
    byId("result-status").textContent = record.errorStatus === 429
      ? "Limite da Groq atingido"
      : "Última geração não concluída";
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    setStudioMode("create");
  }
}

function isTechnicalLine(line = "") {
  const value = String(line).trim();
  if (!value) return false;
  if (/^[A-Za-z_][A-Za-z0-9_]*\s*\([^()\n]+\)\s*(?:[-–—].*)?$/.test(value)) return true;
  if (/^(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|WITH|FROM|WHERE|JOIN|GROUP\s+BY|ORDER\s+BY)\b/i.test(value)) return true;
  if (/^(\$|>|#|sudo\s|python\s|pip\s|git\s|docker\s|npm\s|curl\s)/i.test(value)) return true;
  if (/[{}[\];]|=>|:=|==|!=|<=|>=/.test(value) && value.length < 220) return true;
  return false;
}

function normalizeTechnicalBreaks(text = "") {
  return String(text)
    .replace(/\)\s+(?=[A-Za-z_][A-Za-z0-9_]*\s*\()/g, ")\n")
    .replace(/([:;])\s+(?=[A-Za-z_][A-Za-z0-9_]*\s*\([^)]{2,}\))/g, "$1\n");
}

function appendInlineTechnicalText(parent, text = "") {
  const regex = /(`[^`]+`|\b[A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]+\b|\b[A-Za-z][A-Za-z0-9]*ID\b|\b(?:SID|SQL|JSON|SELECT|FROM|WHERE|JOIN|PRIMARY\s+KEY|FOREIGN\s+KEY)\b)/gi;
  let last = 0;
  for (const match of String(text).matchAll(regex)) {
    if (match.index > last) parent.append(document.createTextNode(text.slice(last, match.index)));
    const raw = match[0];
    const clean = raw.startsWith("`") && raw.endsWith("`") ? raw.slice(1, -1) : raw;
    parent.append(element("code", clean, "technical-inline"));
    last = match.index + raw.length;
  }
  if (last < text.length) parent.append(document.createTextNode(text.slice(last)));
}

function richStemNode(text = "") {
  const root = element("div", undefined, "rich-stem");
  const lines = normalizeTechnicalBreaks(text).split(/\r?\n/);
  let paragraph = [];
  let technical = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const node = element("p");
    appendInlineTechnicalText(node, paragraph.join(" ").trim());
    root.append(node);
    paragraph = [];
  };
  const flushTechnical = () => {
    if (!technical.length) return;
    const pre = element("pre", undefined, "technical-block");
    pre.append(element("code", technical.join("\n")));
    root.append(pre);
    technical = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushTechnical();
      continue;
    }
    if (isTechnicalLine(line)) {
      flushParagraph();
      technical.push(line);
    } else {
      flushTechnical();
      paragraph.push(line);
    }
  }
  flushParagraph();
  flushTechnical();
  return root;
}

function looksTechnicalText(text = "") {
  return isTechnicalLine(text) || /\b[A-Za-z][A-Za-z0-9]*ID\b|[_{}[\];]|=>|:=/.test(String(text));
}

function renderQuestion(question, { demo = false } = {}) {
  byId("empty").hidden = true;
  byId("question").hidden = false;
  const root = byId("question");
  root.replaceChildren();
  root.append(element("div", demo ? "EXEMPLO ILUSTRATIVO · ENADE" : "ENADE · ITEM GERADO", "question-meta"));
  root.append(richStemNode(question.enunciado));

  (question.alternativas ?? []).forEach((answer, index) => {
    const correct = index === question.correta;
    const technical = looksTechnicalText(answer);
    const option = element("div", undefined, `option${correct ? " correct" : ""}${technical ? " technical-answer" : ""}`);
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
    ? "Exemplo ilustrativo."
    : "Revise antes do uso.";
  byId("review-panel").hidden = demo;
  if (!demo) renderReviewPanel();
}

const qualityCodeLabels = {
  iwf_termo_absoluto: "Termo absoluto",
  iwf_gabarito_mais_longo: "Gabarito mais longo",
  iwf_repeticao_entrega_gabarito: "Repetição que pode entregar o gabarito",
  gabarito_repetido_no_enunciado: "Gabarito repetido no enunciado",
  espaco_de_respostas_binario: "Espaço de respostas restrito",
  termo_nao_padronizado: "Termo não padronizado",
  fora_do_dominio: "Fora do domínio conceitual",
  implausivel: "Distrator pouco plausível",
  segunda_resposta: "Potencial segunda resposta correta",
  equivalente_gabarito: "Equivalente ao gabarito",
  nivel_conceitual_incompativel: "Nível conceitual incompatível",
};

function humanizeQualityCode(code = "") {
  const clean = String(code).replace(/^distrator_/, "");
  return qualityCodeLabels[clean]
    || clean.replaceAll("_", " ").replace(/(^|\s)\S/g, (letter) => letter.toUpperCase());
}

function latestArtifact(history, kind) {
  return [...(history?.artifacts ?? [])].reverse().find((artifact) => artifact.kind === kind) ?? null;
}

function deriveQualityTrace(history) {
  if (history?.quality_trace) return history.quality_trace;
  const artifacts = history?.artifacts ?? [];
  const summary = latestArtifact(history, "QUALITY_SUMMARY")?.payload ?? {};
  const finalWarnings = (summary.warnings ?? []).map((flag) => ({
    code: flag.codigo || flag.code || "alerta",
    stage: flag.etapa || flag.stage || "QUALIDADE",
    field: flag.campo || flag.field || "",
    evidence: flag.evidencia || flag.evidence || "",
    repair_target: flag.reparo || flag.repair_target || "",
  }));
  const treated = [];
  for (const artifact of artifacts) {
    const candidate = artifact.payload?.texto || "";
    if (artifact.kind === "DISTRACTOR_CANDIDATE_REJECTED") {
      const artifactFlags = artifact.provenance?.flags ?? [];
      if (artifactFlags.length) {
        for (const flag of artifactFlags) {
          treated.push({
            code: flag.codigo || flag.code || "distrator_rejeitado",
            evidence: flag.evidencia || flag.evidence || "",
            candidate: candidate || flag.alternativa_rejeitada || "",
            action: "distrator_rejeitado",
          });
        }
      }
    }
    if (artifact.kind === "DISTRACTOR_CANDIDATE_REJECTED_QUALITY") {
      treated.push({
        code: artifact.provenance?.quality_code || "qualidade_distrator",
        evidence: artifact.provenance?.reason || "",
        candidate,
        action: "distrator_rejeitado",
      });
    }
  }
  const promotions = artifacts
    .filter((artifact) => artifact.kind === "DISTRACTOR_RESERVE_PROMOTED")
    .map((artifact) => ({ candidate: artifact.payload?.texto || "", reason: artifact.provenance?.reason || "" }));
  const batches = artifacts.filter((artifact) => artifact.kind === "DISTRACTOR_BATCH");
  return {
    final_warnings: finalWarnings,
    final_warning_count: finalWarnings.length,
    historical_red_flags: history?.red_flags ?? [],
    historical_red_flag_count: history?.red_flags?.length ?? 0,
    treated_occurrences: treated,
    treated_occurrence_count: treated.length,
    reserve_promotions: promotions,
    reserve_promotion_count: promotions.length,
    metrics: {
      stem_attempts: history?.request?.stem_attempts ?? 0,
      slm_calls: history?.request?.distractor_attempts ?? 0,
      distractor_batches: batches.length,
      candidates_generated: batches.reduce((total, artifact) => total + (Array.isArray(artifact.payload) ? artifact.payload.length : 0), 0),
      candidates_accepted_active: artifacts.filter((artifact) => artifact.kind === "DISTRACTOR_CANDIDATE_ACCEPTED").length,
      candidates_saved_as_reserve: artifacts.filter((artifact) => artifact.kind === "DISTRACTOR_CANDIDATE_RESERVE").length,
      structural_rejections: artifacts.filter((artifact) => artifact.kind === "DISTRACTOR_CANDIDATE_REJECTED").length,
      quality_rejections: artifacts.filter((artifact) => artifact.kind === "DISTRACTOR_CANDIDATE_REJECTED_QUALITY").length,
      quality_gate_checks: artifacts.filter((artifact) => artifact.kind === "DISTRACTOR_QUALITY_GATE").length,
      active_distractors: summary.active_distractors,
      reserve_distractors: summary.reserve_distractors,
      candidate_bank_size: summary.candidate_bank_size,
      duration_seconds: null,
    },
  };
}

function metricChip(label, value) {
  const chip = element("span", undefined, "quality-chip");
  chip.append(element("strong", String(value ?? "—")), document.createTextNode(` ${label}`));
  return chip;
}

function appendQualityIssue(root, issue, tone = "treated") {
  const row = element("div", undefined, `quality-issue ${tone}`);
  const title = element("div", undefined, "quality-issue-title");
  title.append(element("strong", humanizeQualityCode(issue.code)));
  title.append(element("code", issue.code || "alerta"));
  row.append(title);
  if (issue.candidate) row.append(element("p", `Alternativa: “${issue.candidate}”`, "quality-candidate"));
  if (issue.evidence) row.append(element("p", issue.evidence));
  const action = issue.action === "distrator_rejeitado" ? "Rejeitado e preservados os demais candidatos." : "Mantido para revisão humana.";
  row.append(element("small", action));
  root.append(row);
}

function renderQualityTrace(data, { demo = false } = {}) {
  const root = byId("quality-trace");
  if (!root) return;
  root.replaceChildren();
  if (demo) return;
  const trace = deriveQualityTrace(data);
  const metrics = trace.metrics ?? {};

  const heading = element("div", undefined, "quality-trace-heading");
  const headingText = element("div");
  headingText.append(element("span", "QUALIDADE AUTOMÁTICA", "eyebrow"), element("h4", "O que aconteceu durante a geração"));
  const finalBadge = element(
    "span",
    `⚑ ${trace.final_warning_count ?? 0}`,
    `quality-final-badge ${trace.final_warning_count ? "warning" : "ok"}`,
  );
  heading.append(headingText, finalBadge);
  root.append(heading);

  const chips = element("div", undefined, "quality-chips");
  chips.append(
    metricChip("tratadas", trace.treated_occurrence_count),
    metricChip("rejeições de qualidade", metrics.quality_rejections),
    metricChip("chamadas SLM", metrics.slm_calls),
    metricChip("candidatos gerados", metrics.candidates_generated),
  );
  if (trace.reserve_promotion_count) chips.append(metricChip("reservas promovidas", trace.reserve_promotion_count));
  if (metrics.duration_seconds != null) chips.append(metricChip("s", metrics.duration_seconds));
  root.append(chips);

  const finalSection = element("details", undefined, "quality-details");
  finalSection.open = Boolean(trace.final_warning_count);
  finalSection.append(element("summary", `⚑ Red Flags finais (${trace.final_warning_count})`));
  const finalBody = element("div", undefined, "quality-details-body");
  if (!trace.final_warning_count) {
    finalBody.append(element("p", "Nenhuma Red Flag permaneceu na questão entregue.", "quality-empty"));
  } else {
    for (const warning of trace.final_warnings ?? []) appendQualityIssue(finalBody, warning, "final");
  }
  finalSection.append(finalBody);
  root.append(finalSection);

  const treatedSection = element("details", undefined, "quality-details");
  treatedSection.open = Boolean(trace.treated_occurrence_count);
  treatedSection.append(element("summary", `Ocorrências detectadas e tratadas (${trace.treated_occurrence_count})`));
  const treatedBody = element("div", undefined, "quality-details-body");
  if (!trace.treated_occurrence_count) {
    treatedBody.append(element("p", "Nenhuma ocorrência exigiu descarte localizado.", "quality-empty"));
  } else {
    for (const issue of trace.treated_occurrences ?? []) appendQualityIssue(treatedBody, issue, "treated");
  }
  treatedSection.append(treatedBody);
  root.append(treatedSection);

  const promotionSection = element("details", undefined, "quality-details");
  promotionSection.append(element("summary", `Reservas promovidas (${trace.reserve_promotion_count ?? 0})`));
  const promotionBody = element("div", undefined, "quality-details-body");
  if (!(trace.reserve_promotion_count ?? 0)) {
    promotionBody.append(element("p", "Nenhuma reserva precisou ser promovida nesta geração.", "quality-empty"));
  } else {
    for (const promotion of trace.reserve_promotions ?? []) {
      const row = element("div", undefined, "quality-issue promoted");
      row.append(element("strong", promotion.candidate || "Candidato de reserva"));
      row.append(element("p", "Promovido para substituir um distrator rejeitado sem nova geração do núcleo."));
      promotionBody.append(row);
    }
  }
  promotionSection.append(promotionBody);
  root.append(promotionSection);
}

function renderQualitySummary(data, { demo = false } = {}) {
  const root = byId("quality-summary");
  if (!root) return;
  root.replaceChildren();
  const completed = data?.request?.state === "GENERATION_COMPLETED" && data?.latest_version?.question;
  root.hidden = Boolean(demo || !completed);
  if (root.hidden) return;

  const trace = deriveQualityTrace(data);
  const metrics = trace.metrics ?? {};
  const finalCount = trace.final_warning_count ?? 0;
  const treated = trace.treated_occurrence_count ?? 0;
  const promoted = trace.reserve_promotion_count ?? 0;

  const title = element("span", "Qualidade", "quality-summary-title");
  const items = element("div", undefined, "quality-summary-items");

  const final = element("button", `⚑ ${finalCount}`, `quality-summary-pill flag${finalCount ? " warning" : ""}`);
  final.type = "button";
  final.title = `${finalCount} Red Flag${finalCount === 1 ? "" : "s"} final${finalCount === 1 ? "" : "is"}`;
  final.addEventListener("click", () => setTab("trace"));
  items.append(final);

  const treatedButton = element("button", `✓ ${treated}`, "quality-summary-pill ok");
  treatedButton.type = "button";
  treatedButton.title = `${treated} ocorrência${treated === 1 ? "" : "s"} tratada${treated === 1 ? "" : "s"}`;
  treatedButton.addEventListener("click", () => setTab("trace"));
  items.append(treatedButton);

  if (promoted) {
    const reserve = element("span", `↻ ${promoted}`, "quality-summary-pill");
    reserve.title = `${promoted} reserva${promoted === 1 ? "" : "s"} promovida${promoted === 1 ? "" : "s"}`;
    items.append(reserve);
  }
  if (metrics.slm_calls != null) {
    const slm = element("span", `◈ ${metrics.slm_calls}`, "quality-summary-pill muted");
    slm.title = `${metrics.slm_calls} chamada${metrics.slm_calls === 1 ? "" : "s"} SLM`;
    items.append(slm);
  }
  if (metrics.duration_seconds != null) {
    const time = element("span", `◷ ${Number(metrics.duration_seconds).toFixed(1)} s`, "quality-summary-pill muted");
    time.title = "Tempo total da geração";
    items.append(time);
  }

  root.append(title, items);
}

function dashboardRecords() {
  if (state.batchResults.length) return state.batchResults;
  if (state.history || state.result) {
    return [{
      index: 0,
      requestId: state.result?.request_id || state.history?.request?.id,
      result: state.result,
      history: state.history,
    }];
  }
  return [];
}

function latestHumanDecision(history) {
  const review = [...(history?.reviews ?? [])].reverse()[0];
  if (!review) return "—";
  return review.decision === "APROVAR" ? "Usaria" : review.decision === "REJEITAR" ? "Não usaria" : review.decision;
}

function renderSessionDashboard() {
  const rowsRoot = byId("dashboard-rows");
  if (!rowsRoot) return;
  const records = dashboardRecords();
  const completed = records.filter((record) => record?.result?.state === "GENERATION_COMPLETED" || record?.history?.request?.state === "GENERATION_COMPLETED");
  const traces = completed.map((record) => deriveQualityTrace(record.history ?? {}));
  const finalFlags = traces.reduce((sum, trace) => sum + (trace.final_warning_count ?? 0), 0);
  const treated = traces.reduce((sum, trace) => sum + (trace.treated_occurrence_count ?? 0), 0);
  const durations = traces.map((trace) => Number(trace.metrics?.duration_seconds)).filter(Number.isFinite);
  const avg = durations.length ? durations.reduce((a, b) => a + b, 0) / durations.length : null;

  byId("dash-total").textContent = String(records.length);
  byId("dash-completed").textContent = String(completed.length);
  byId("dash-final-flags").textContent = String(finalFlags);
  byId("dash-treated").textContent = String(treated);
  byId("dash-time").textContent = avg == null ? "—" : `${avg.toFixed(1)} s`;

  rowsRoot.replaceChildren();
  if (!records.length) {
    const row = element("tr");
    const cell = element("td", "Nenhuma questão nesta sessão.");
    cell.colSpan = 6;
    row.append(cell);
    rowsRoot.append(row);
    return;
  }

  records.forEach((record, index) => {
    const history = record.history ?? {};
    const trace = deriveQualityTrace(history);
    const metrics = trace.metrics ?? {};
    const stateValue = record?.result?.state || history?.request?.state || "—";
    const stateLabel = stateValue === "GENERATION_COMPLETED" ? "Concluída" : stateValue.replaceAll("_", " ").toLowerCase();
    const quality = `${trace.final_warning_count ?? 0} finais · ${trace.treated_occurrence_count ?? 0} tratadas`;
    const row = element("tr");
    [
      String(index + 1),
      stateLabel,
      quality,
      metrics.slm_calls == null ? "—" : String(metrics.slm_calls),
      metrics.duration_seconds == null ? "—" : `${Number(metrics.duration_seconds).toFixed(1)} s`,
      latestHumanDecision(history),
    ].forEach((value) => row.append(element("td", value)));
    rowsRoot.append(row);
  });
}

function renderHistory(data, { demo = false } = {}) {
  state.history = data;
  renderQualityTrace(data, { demo });
  renderQualitySummary(data, { demo });
  renderSessionDashboard();
  const events = byId("events");
  events.replaceChildren();
  const items = demo ? [...demoEvents] : [...(data?.events ?? [])];
  if (!items.length) items.push({ component: "HAILA", reason: "Aguardando o primeiro evento" });

  for (const event of items) {
    let reason = event.reason || event.to_state;
    if (!demo && event.to_state === "GENERATION_COMPLETED") {
      const trace = deriveQualityTrace(data);
      const treated = trace.treated_occurrence_count ?? 0;
      const finalCount = trace.final_warning_count ?? 0;
      const finalLabel = finalCount === 1 ? "1 Red Flag final" : `${finalCount} Red Flags finais`;
      const treatedLabel = treated === 1 ? "1 ocorrência tratada" : `${treated} ocorrências tratadas`;
      reason = `geração concluída · ${finalLabel} · ${treatedLabel}`;
    }
    const item = element("li", reason);
    const time = event.created_at ? ` · ${new Date(event.created_at).toLocaleTimeString("pt-BR")}` : "";
    item.append(element("small", `${event.component}${time}`));
    events.append(item);
  }

  const flags = byId("flags");
  flags.replaceChildren();
  if (data?.red_flags?.length) {
    const legacy = element("details", undefined, "raw-flags");
    legacy.append(element("summary", `Registro bruto de Red Flags (${data.red_flags.length})`));
    const body = element("div");
    for (const flag of data.red_flags) {
      const row = element("p");
      row.append(element("strong", `${humanizeQualityCode(flag.code)} · `));
      row.append(document.createTextNode(flag.evidence || flag.evidencia || flag.code));
      body.append(row);
    }
    legacy.append(body);
    flags.append(legacy);
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
  renderJuryPanel(record);
}

const juryFlagNames = {
  RF1: "Erro de gabarito",
  RF2: "Complexidade inadequada",
  RF3: "Contradição interna",
  RF4: "Falta de clareza",
  RF5: "Falta de contexto",
  RF6: "Problemas linguísticos",
  RF7: "Avaliação pouco clara",
  RF8: "Distratores fracos",
};

function latestJuryArtifact(history) {
  return [...(history?.artifacts ?? [])]
    .reverse()
    .find((artifact) => artifact.kind === "JURY_LLM_EVALUATION");
}

function latestJuryError(history) {
  return [...(history?.artifacts ?? [])]
    .reverse()
    .find((artifact) => artifact.kind === "JURY_LLM_ERROR");
}

function renderJuryPanel(record = currentRecord()) {
  const button = byId("run-jury");
  const status = byId("jury-status");
  const root = byId("jury-results");
  if (!button || !status || !root) return;
  root.replaceChildren();

  const settings = state.jurySettings;
  if (!settings?.enabled) {
    button.disabled = true;
    status.textContent = "Júri LLM indisponível nesta sessão";
    return;
  }
  if (!settings?.configured) {
    button.disabled = true;
    status.textContent = "Configure a chave Groq para habilitar o júri";
    return;
  }

  button.disabled = Boolean(state.busy);
  const artifact = latestJuryArtifact(record?.history);
  if (!artifact) {
    const errorArtifact = latestJuryError(record?.history);
    status.textContent = errorArtifact
      ? "Última tentativa de avaliação por IA não foi concluída"
      : "Não solicitada";
    root.append(element(
      "p",
      "A questão pode ser avaliada pelo professor sem consultar os juízes de IA.",
      "jury-empty",
    ));
    return;
  }

  const payload = artifact.payload ?? {};
  const evaluation = payload.evaluation ?? {};
  const profile = evaluation.profile_snapshot ?? {};
  const judgeConfig = Object.fromEntries((profile.judges ?? []).map((judge) => [judge.id, judge]));
  status.textContent = payload.cached ? "Avaliação por IA recuperada" : "Avaliação por IA concluída";

  const recommendation = element("div", undefined, "jury-recommendation");
  recommendation.append(
    element("strong", `Recomendação automática: ${evaluation.final_action ?? "—"}`),
    element("small", "A recomendação não altera a decisão do professor."),
  );
  root.append(recommendation);

  for (const report of evaluation.reports ?? []) {
    const config = judgeConfig[report.judge_id] ?? {};
    const card = element("div", undefined, "jury-report");
    card.append(
      element("strong", config.display_name || report.judge_id),
      element("small", `${report.model || "modelo não informado"} · ${Math.round(report.latency_ms || 0)} ms · ${report.total_tokens || 0} tokens`),
    );
    if (report.status !== "completed") {
      card.append(element("p", report.error || "Parecer não concluído.", "jury-error"));
      root.append(card);
      continue;
    }
    const detected = (report.findings ?? []).filter((finding) => finding.detected);
    if (!detected.length) {
      card.append(element("p", "Nenhuma Red Flag detectada por este juiz."));
    } else {
      const list = element("ul", undefined, "jury-flags");
      for (const finding of detected) {
        const confidence = Math.round((finding.confidence || 0) * 100);
        const item = element("li");
        item.append(element("strong", `${finding.red_flag_id} · ${juryFlagNames[finding.red_flag_id] || finding.red_flag_id}`));
        item.append(element("span", `Gravidade ${finding.severity} · confiança ${confidence}%`));
        if (finding.evidence?.length) item.append(element("small", finding.evidence.join(" · ")));
        if (finding.recommendation) item.append(element("small", `Recomendação: ${finding.recommendation}`));
        list.append(item);
      }
      card.append(list);
    }
    root.append(card);
  }

  const summary = payload.summary ?? {};
  const agreement = summary.agreement_rate == null
    ? "—"
    : `${Math.round(summary.agreement_rate * 100)}%`;
  const footer = element("div", undefined, "jury-summary");
  footer.append(
    element("span", `Concordância por Red Flag: ${agreement}`),
    element("span", `Tokens: ${summary.total_tokens ?? 0}`),
    element("span", `Tempo total: ${Math.round(payload.wall_latency_ms ?? 0)} ms`),
  );
  if (summary.disagreements?.length) {
    footer.append(element("span", `Discordâncias: ${summary.disagreements.join(", ")}`));
  }
  root.append(footer);
}

async function loadJurySettings() {
  try {
    state.jurySettings = await api.jurySettings();
  } catch {
    state.jurySettings = { enabled: false, configured: false };
  }
  if (!byId("review-panel").hidden) renderJuryPanel();
}

async function runJuryEvaluation() {
  if (state.busy) return;
  const record = currentRecord();
  if (!record?.requestId || !isCompleted(record)) {
    setNotice("Selecione uma questão concluída antes de solicitar a avaliação por IA.", "warning");
    return;
  }
  const button = byId("run-jury");
  button.disabled = true;
  button.textContent = "Avaliando com IA…";
  byId("jury-status").textContent = "Dois juízes estão analisando a questão";
  try {
    await api.runJuryEvaluation(record.requestId, false);
    record.history = await api.history(record.requestId);
    state.history = record.history;
    renderJuryPanel(record);
    setNotice("Avaliação por IA concluída. O parecer é informativo; a decisão final continua sendo do professor.", "success");
  } catch (error) {
    record.history = await api.history(record.requestId).catch(() => record.history);
    state.history = record.history;
    renderJuryPanel(record);
    setNotice(error.message, error.status === 429 ? "warning" : "error");
  } finally {
    button.disabled = false;
    button.textContent = "Avaliar com IA";
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
  setStudioMode("demo");
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
  renderSessionDashboard();
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
  history.replaceState(null, "", "studio.html");
  setStudioMode("generating");
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
    if (!isCompatibleBackend(health)) {
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
    setStudioMode(state.mode);
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

function stemToHtml(text = "") {
  const lines = normalizeTechnicalBreaks(text).split(/\r?\n/);
  const output = [];
  let normal = [];
  let technical = [];
  const flushNormal = () => {
    if (!normal.length) return;
    output.push(`<p>${escapeHtml(normal.join(" ").trim())}</p>`);
    normal = [];
  };
  const flushTechnical = () => {
    if (!technical.length) return;
    output.push(`<pre><code>${escapeHtml(technical.join("\n"))}</code></pre>`);
    technical = [];
  };
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) { flushNormal(); flushTechnical(); continue; }
    if (isTechnicalLine(line)) { flushNormal(); technical.push(line); }
    else { flushTechnical(); normal.push(line); }
  }
  flushNormal(); flushTechnical();
  return output.join("");
}

function reportQualityHtml(history) {
  const trace = deriveQualityTrace(history ?? {});
  const metrics = trace.metrics ?? {};
  const warnings = (trace.final_warnings ?? []).map((item) => `<li><b>⚑ ${escapeHtml(humanizeQualityCode(item.code))}</b> — ${escapeHtml(item.evidence || "Sem evidência textual.")}</li>`).join("");
  const treated = (trace.treated_occurrences ?? []).map((item) => `<li><b>${escapeHtml(humanizeQualityCode(item.code))}</b>${item.candidate ? ` · ${escapeHtml(item.candidate)}` : ""} — ${escapeHtml(item.evidence || "Ocorrência tratada.")}</li>`).join("");
  return `<section class="report-quality"><h2>Qualidade e rastreabilidade</h2><div class="metrics"><span><b>⚑ ${trace.final_warning_count ?? 0}</b> Red Flags finais</span><span><b>✓ ${trace.treated_occurrence_count ?? 0}</b> tratadas</span><span><b>◈ ${metrics.slm_calls ?? "—"}</b> chamadas SLM</span><span><b>◷ ${metrics.duration_seconds == null ? "—" : `${Number(metrics.duration_seconds).toFixed(1)} s`}</b> tempo</span></div>${warnings ? `<h3>Red Flags finais</h3><ul>${warnings}</ul>` : ""}${treated ? `<h3>Ocorrências tratadas</h3><ul>${treated}</ul>` : ""}</section>`;
}

function questionDocument(question, { printable = false, history = state.history } = {}) {
  const options = (question.alternativas ?? []).map((answer, index) => {
    const letter = String.fromCharCode(65 + index);
    const correct = index === question.correta ? " class=\"correct\"" : "";
    return `<li${correct}><b>${letter}</b> <span>${escapeHtml(answer)}</span></li>`;
  }).join("");
  const reviews = (history?.reviews ?? []).map((review) => `<li><b>${escapeHtml(review.reviewer_name || review.reviewer_role || "Avaliador")}</b> — ${escapeHtml(review.decision || "")}${review.comments ? ` · ${escapeHtml(review.comments)}` : ""}</li>`).join("");
  const autoPrint = printable ? "<script>addEventListener('load',()=>setTimeout(()=>print(),250))<\/script>" : "";
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Relatório HAILA</title><style>body{font:14px/1.65 Arial,sans-serif;color:#302a43;max-width:900px;margin:36px auto;padding:0 30px}.meta{color:#5a45ba;font-size:10px;letter-spacing:1px;font-weight:700}h1{font-size:24px}h2{font-size:16px;margin-top:28px;border-top:1px solid #e7e3ef;padding-top:18px}h3{font-size:12px;margin:16px 0 6px}.stem p{margin:0 0 10px}.stem pre{white-space:pre-wrap;background:#f5faf9;border-left:3px solid #159f95;padding:12px 14px;border-radius:6px;font:11px/1.65 monospace}ol.options{list-style:none;padding:0}.options li{display:flex;gap:10px;border:1px solid #e4dfeb;border-radius:8px;margin:8px 0;padding:10px}.options li b{color:#5a45ba}.options .correct{background:#eef9f7;border-color:#b8ded8}.answer{margin-top:20px;padding-top:14px;border-top:1px solid #e7e3ef}.metrics{display:flex;flex-wrap:wrap;gap:8px}.metrics span{border:1px solid #e4dfeb;border-radius:20px;padding:5px 8px;font-size:10px}.report-quality li{margin:6px 0}.report-quality li b{color:#7c263c}.reviews{font-size:11px}@media print{body{margin:0;max-width:none}.correct{print-color-adjust:exact;-webkit-print-color-adjust:exact}}</style></head><body><div class="meta">HAILA · RELATÓRIO DE QUESTÃO</div><h1>Questão gerada</h1><div class="stem">${stemToHtml(question.enunciado)}</div><ol class="options">${options}</ol><section class="answer"><b>Gabarito: ${String.fromCharCode(65 + question.correta)}</b><p>${escapeHtml(question.explicacao || "Sem justificativa.")}</p></section>${reportQualityHtml(history)}${reviews ? `<section class="reviews"><h2>Revisão humana</h2><ul>${reviews}</ul></section>` : ""}${autoPrint}</body></html>`;
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

function csvEscape(value) {
  const text = value == null ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function exportCsv() {
  const records = dashboardRecords();
  if (!records.length) {
    setNotice("Não há dados disponíveis para exportar em CSV.", "warning");
    return;
  }
  const header = [
    "questao", "request_id", "estado", "red_flags_finais", "ocorrencias_tratadas",
    "rejeicoes_qualidade", "reservas_promovidas", "chamadas_slm", "candidatos_gerados",
    "tempo_segundos", "decisao_humana",
  ];
  const rows = records.map((record, index) => {
    const history = record.history ?? {};
    const trace = deriveQualityTrace(history);
    const metrics = trace.metrics ?? {};
    return [
      index + 1,
      record.requestId || record.result?.request_id || history.request?.id || "",
      record.result?.state || history.request?.state || "",
      trace.final_warning_count ?? 0,
      trace.treated_occurrence_count ?? 0,
      metrics.quality_rejections ?? 0,
      trace.reserve_promotion_count ?? 0,
      metrics.slm_calls ?? 0,
      metrics.candidates_generated ?? 0,
      metrics.duration_seconds ?? "",
      latestHumanDecision(history),
    ];
  });
  const csv = [header, ...rows].map((row) => row.map(csvEscape).join(",")).join("\n");
  download(`\ufeff${csv}`, "text/csv;charset=utf-8", `haila-metricas-${new Date().toISOString().replaceAll(":", "-")}.csv`);
}

function exportHtml() {
  const question = activeQuestion();
  if (!question) {
    setNotice("Selecione uma questão concluída antes de exportar o HTML.", "warning");
    return;
  }
  download(questionDocument(question, { history: state.history }), "text/html;charset=utf-8", `haila-questao-${state.result.request_id || "exemplo"}.html`);
}

function exportPdf() {
  const question = activeQuestion();
  if (!question) {
    setNotice("Selecione uma questão concluída antes de exportar o PDF.", "warning");
    return;
  }
  const documentUrl = URL.createObjectURL(new Blob(
    [questionDocument(question, { printable: true, history: state.history })],
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

function markdownReport(question, history) {
  const trace = deriveQualityTrace(history ?? {});
  const metrics = trace.metrics ?? {};
  const alternatives = (question.alternativas ?? []).map((answer, index) => {
    const letter = String.fromCharCode(65 + index);
    return `- ${letter}) ${answer}${index === question.correta ? " **← gabarito**" : ""}`;
  }).join("\n");
  const warnings = (trace.final_warnings ?? []).length
    ? (trace.final_warnings ?? []).map((item) => `- ⚑ **${humanizeQualityCode(item.code)}**: ${item.evidence || "Sem evidência textual."}`).join("\n")
    : "- Nenhuma Red Flag final.";
  const treated = (trace.treated_occurrences ?? []).length
    ? (trace.treated_occurrences ?? []).map((item) => `- **${humanizeQualityCode(item.code)}**${item.candidate ? ` — \`${item.candidate}\`` : ""}: ${item.evidence || "Ocorrência tratada."}`).join("\n")
    : "- Nenhuma ocorrência tratada.";
  const reviews = (history?.reviews ?? []).length
    ? history.reviews.map((review) => `- **${review.reviewer_name || review.reviewer_role || "Avaliador"}** — ${review.decision || ""}${review.comments ? `: ${review.comments}` : ""}`).join("\n")
    : "- Nenhum parecer humano registrado.";
  return `# Questão HAILA\n\n**Request ID:** ${state.result?.request_id || history?.request?.id || "—"}\n\n## Enunciado\n\n${question.enunciado}\n\n## Alternativas\n\n${alternatives}\n\n## Gabarito\n\n**${String.fromCharCode(65 + question.correta)}**\n\n${question.explicacao || "Sem justificativa."}\n\n## Qualidade automática\n\n- ⚑ Red Flags finais: **${trace.final_warning_count ?? 0}**\n- ✓ Ocorrências tratadas: **${trace.treated_occurrence_count ?? 0}**\n- Rejeições de qualidade: **${metrics.quality_rejections ?? 0}**\n- Reservas promovidas: **${trace.reserve_promotion_count ?? 0}**\n- Chamadas SLM: **${metrics.slm_calls ?? 0}**\n- Candidatos gerados: **${metrics.candidates_generated ?? 0}**\n- Tempo: **${metrics.duration_seconds == null ? "—" : `${Number(metrics.duration_seconds).toFixed(2)} s`}**\n\n### Red Flags finais\n\n${warnings}\n\n### Ocorrências tratadas\n\n${treated}\n\n## Revisão humana\n\n${reviews}\n`;
}

function exportMarkdown() {
  const question = activeQuestion();
  if (!question) {
    setNotice("Selecione uma questão concluída antes de exportar o Markdown.", "warning");
    return;
  }
  const id = state.result?.request_id || "questao";
  download(markdownReport(question, state.history), "text/markdown;charset=utf-8", `haila-${id}.md`);
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
byId("export-csv").addEventListener("click", exportCsv);
byId("export-html").addEventListener("click", exportHtml);
byId("export-pdf").addEventListener("click", exportPdf);
byId("export-md").addEventListener("click", exportMarkdown);
byId("export-flags").addEventListener("click", exportFlags);
byId("run-jury").addEventListener("click", runJuryEvaluation);
byId("approve-question").addEventListener("click", () => saveHumanReview("APROVAR"));
byId("reject-question").addEventListener("click", () => saveHumanReview("REJEITAR"));
byId("new-question").addEventListener("click", startNewQuestion);

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

renderSessionDashboard();

registerStudioTools({
  openDemo: showDemo,
  setFormValues,
  readStatus: () => ({ connected: state.connected, mode: state.mode, busy: state.busy }),
});

setStudioMode("create");

Promise.all([checkHealth(), loadGroqSettings(), loadJurySettings()]).then(async () => {
  await restoreLastRequest();
  if (!state.backendCompatible) {
    byId("result-status").textContent = "Motor precisa reiniciar";
    setNotice("A versão antiga do motor ainda está ativa. No terminal onde a HAILA roda: Ctrl+C e depois ./iniciar_haila_web.sh. A chave validada nessa sessão será perdida e precisará ser informada novamente.", "error");
  }
});
if (new URLSearchParams(location.search).get("demo") === "1") showDemo();
