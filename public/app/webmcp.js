export function registerStudioTools({ openDemo, setFormValues, readStatus }) {
  const context = document.modelContext;
  if (!context?.registerTool) return;

  const lifecycle = new AbortController();
  const register = (tool) => {
    try {
      Promise.resolve(context.registerTool(tool, { signal: lifecycle.signal })).catch(() => {});
    } catch {
      // O navegador pode expor uma implementação parcial. A tela continua funcional.
    }
  };

  register({
    name: "open_haila_demo",
    title: "Abrir demonstração HAILA",
    description: "Mostra a questão ENADE de demonstração no estúdio, sem executar modelos.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    annotations: { readOnlyHint: true, untrustedContentHint: false },
    execute() {
      openDemo();
      return { mode: "demo", visible: true };
    },
  });

  register({
    name: "configure_haila_question",
    title: "Configurar questão HAILA",
    description: "Preenche os parâmetros pedagógicos visíveis sem iniciar a geração.",
    inputSchema: {
      type: "object",
      properties: {
        course: { type: "string", minLength: 1 },
        knowledgeObject: { type: "string" },
        objective: { type: "string", minLength: 15 },
        difficulty: { type: "integer", minimum: 1, maximum: 5 },
      },
      required: ["course", "objective"],
      additionalProperties: false,
    },
    annotations: { readOnlyHint: false, untrustedContentHint: false },
    execute(input) {
      setFormValues(input);
      return { configured: true, generationStarted: false };
    },
  });

  register({
    name: "read_haila_studio_status",
    title: "Ler status do HAILA Studio",
    description: "Retorna o estado atual da conexão e da geração sem alterar a tela.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    annotations: { readOnlyHint: true, untrustedContentHint: false },
    execute: readStatus,
  });
}
