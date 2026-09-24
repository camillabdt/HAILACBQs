export const demoQuestion = {
  exame: "ENADE",
  enunciado:
    "Uma universidade mantém um sistema de matrículas em um banco de dados relacional. Ao abrir as inscrições, duas transações tentam ocupar simultaneamente a última vaga de uma disciplina.\n\nPara impedir que ambas confirmem a matrícula e excedam o limite de vagas, qual estratégia é mais adequada?",
  alternativas: [
    "Executar a consulta de vagas sem controle de concorrência antes de cada inserção.",
    "Reduzir a frequência de cópias de segurança durante o período de matrícula.",
    "Controlar a leitura e a atualização da vaga em uma transação com isolamento e bloqueio adequados.",
    "Criar um índice no nome do estudante para acelerar a consulta.",
    "Replicar a tabela de disciplinas sem sincronizar as operações de escrita.",
  ],
  correta: 2,
  explicacao:
    "O controle transacional com isolamento e bloqueio adequados evita que as duas operações consumam a mesma vaga. Índices e cópias de segurança não garantem, por si só, a consistência de atualizações concorrentes.",
  objeto_conhecimento: "Banco de dados relacionais",
};

export const demoEvents = [
  { component: "HAILA", reason: "Solicitação registrada" },
  { component: "HAILA_RAG", reason: "Referência recuperada" },
  { component: "HAILA_LLM", reason: "Núcleo da questão gerado" },
  { component: "HAILA_SLM", reason: "Distratores gerados" },
  { component: "HAILA_RED_FLAGS", reason: "Verificação automática concluída" },
];
