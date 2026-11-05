import { HailaApi } from "./api.js?v=20261021-front-final-v1";

const api = new HailaApi();
const STORAGE_KEY = "haila:last-request-id";
const byId = (id) => document.getElementById(id);

function traceFrom(history) {
  const trace = history?.quality_trace ?? {};
  const metrics = trace.metrics ?? {};
  return {
    final: trace.final_warning_count ?? 0,
    treated: trace.treated_occurrence_count ?? 0,
    slm: metrics.slm_calls ?? history?.request?.distractor_attempts ?? 0,
    time: metrics.duration_seconds,
  };
}

async function loadLastGeneration() {
  const requestId = localStorage.getItem(STORAGE_KEY);
  if (!requestId) return;
  try {
    const history = await api.history(requestId);
    const trace = traceFrom(history);
    const state = history?.request?.state ?? "—";
    byId("last-state").textContent = state === "GENERATION_COMPLETED" ? "Concluída" : state.replaceAll("_", " ").toLowerCase();
    byId("last-flags").textContent = String(trace.final);
    byId("last-treated").textContent = String(trace.treated);
    byId("last-slm").textContent = String(trace.slm);
    byId("last-time").textContent = Number.isFinite(Number(trace.time)) ? `${Number(trace.time).toFixed(1)} s` : "—";
    byId("last-note").textContent = `Última questão salva · ${requestId.slice(0, 8)}…`;
    byId("last-open").hidden = false;
  } catch {
    byId("last-note").textContent = "A última geração não pôde ser carregada agora.";
  }
}

loadLastGeneration();
