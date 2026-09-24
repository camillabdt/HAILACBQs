# API HAILA

## Rotas operacionais

- `GET /health`: configuração e versão do backend.
- `GET /settings/groq`: estado da LLM usada para gerar o núcleo.
- `POST /settings/groq`: valida a chave e escolhe o modelo do núcleo para a sessão.
- `POST /requests`: registra a especificação pedagógica.
- `POST /requests/{id}/generate`: executa RAG, LLM, SLM, montagem e regras determinísticas.
- `GET /requests/{id}`: retorna estados, versões, artefatos, red flags e pareceres.
- `POST /requests/{id}/reviews`: registra avaliação de professor responsável ou convidado.

Não existe rota de aprovação por LLM no backend operacional. Avaliadores automáticos pertencem ao protocolo experimental em `research/`.
