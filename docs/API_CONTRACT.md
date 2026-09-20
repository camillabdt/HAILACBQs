# Contrato do motor HAILA-CBQ

O front usa somente quatro operações. O `server.py` atua como proxy local, então chaves e endereços internos do motor não chegam ao navegador.

## 1. Saúde do motor

`GET /health`

Resposta mínima:

```json
{
  "status": "ok",
  "llm_configured": true,
  "slm_configured": true,
  "slm_backend": "qwen"
}
```

Enquanto `llm_configured` ou `slm_configured` for `false`, a demonstração funciona, mas a geração real fica bloqueada antes de criar uma solicitação.

## 2. Criar solicitação

`POST /requests`

```json
{
  "solicitante_id": "haila-studio",
  "curso": "Computação",
  "exame": "ENADE",
  "componente": "ESPECIFICO",
  "objetivo_pedagogico": "Analisar...",
  "dificuldade": 3,
  "competencia": null,
  "habilidade": null,
  "objeto_conhecimento": "Banco de dados",
  "restricoes": [],
  "max_tentativas": 3,
  "max_tentativas_distratores": 3
}
```

A resposta precisa conter `id`, usado nas operações seguintes.

## 3. Executar geração

`POST /requests/{request_id}/generate`

Resposta concluída:

```json
{
  "request_id": "uuid",
  "state": "GENERATION_COMPLETED",
  "red_flags": [],
  "version": {
    "id": "uuid",
    "version_number": 1,
    "question": {
      "exame": "ENADE",
      "enunciado": "Texto da questão",
      "alternativas": ["A", "B", "C", "D", "E"],
      "correta": 2,
      "explicacao": "Justificativa do gabarito",
      "competencia": "...",
      "habilidade": "...",
      "objeto_conhecimento": "..."
    }
  }
}
```

`correta` é um índice começando em zero. Para um resultado incompleto, a resposta pode usar `ATTEMPTS_EXHAUSTED` e deve incluir as red flags que explicam o bloqueio.

## 4. Consultar histórico

`GET /requests/{request_id}`

```json
{
  "request": { "id": "uuid", "state": "STEM_GENERATED" },
  "versions": [],
  "artifacts": [],
  "red_flags": [],
  "events": [
    {
      "component": "CBQ_LLM",
      "reason": "núcleo gerado",
      "to_state": "STEM_GENERATED",
      "created_at": "2026-09-19T20:00:00Z"
    }
  ]
}
```

O estúdio consulta esse histórico a cada quatro segundos enquanto `/generate` está aberto. Falhas temporárias do histórico não cancelam a geração principal.

## Estados esperados

- `REQUESTED`
- `REFERENCE_RETRIEVED`
- `STEM_GENERATED`
- `DISTRACTORS_GENERATED`
- `ITEM_ASSEMBLED`
- `BLOCKED_BY_RED_FLAGS`
- `GENERATION_COMPLETED`
- `ATTEMPTS_EXHAUSTED`

## Melhoria recomendada no motor

O histórico atual lista versões sem o conteúdo da questão. Para restaurar uma geração após recarregar a página, inclua a questão da versão mais recente no histórico ou exponha `GET /requests/{request_id}/versions/{version_id}`. A primeira opção é suficiente para este front:

```json
{
  "latest_version": {
    "id": "uuid",
    "version_number": 1,
    "question": { "enunciado": "...", "alternativas": [] }
  }
}
```
