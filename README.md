# HAILA Front

Interface completa para apresentação, configuração, geração e revisão de questões ENADE. O visual segue a referência fornecida, com mascote original, e a integração usa o contrato real da API HAILA-CBQ.

## Executar

```sh
./scripts/start_front.sh
```

Abra http://127.0.0.1:4173. Para outra porta do motor:

```sh
python3 server.py --backend http://127.0.0.1:8000 --port 4173
```

Também é possível executar diretamente com `python3 server.py`. Use `HAILA_API_URL` e `HAILA_FRONT_PORT` para alterar a configuração; `.env.example` mostra os valores padrão.

Para verificar o contrato do front sem carregar modelos, execute `python3 scripts/check_integration.py`. O teste sobe um motor temporário em memória, percorre saúde, criação, geração e histórico, e encerra sem persistir dados.

Inicie separadamente o motor existente usando `iniciar_haila_api.sh` no projeto original. Nenhuma credencial é enviada ao navegador. A interface chama `/health`, cria `/requests`, executa `/requests/{id}/generate` e consulta `/requests/{id}` a cada quatro segundos durante a execução. O contrato completo está em `docs/API_CONTRACT.md`.

## Escopo e limites

- Página inicial e estúdio responsivos; demonstração claramente identificada, rastreabilidade e exportação JSON.
- Parâmetros pedagógicos, retorno de alternativas, gabarito, justificativa e eventos reais do motor.
- O exemplo não executa modelos. Não há scores, métricas, júri de modelos ou autenticação simulados.
- A conexão real depende da API e dos modelos configurados. A interface não inicia treinamento nem carrega modelos por conta própria.
- Resultados ficam na memória da página; o histórico persistente pertence ao motor. Não feche a aba durante a geração. A API atual não fornece o conteúdo de versões completas ao consultar um histórico, portanto não é possível restaurar uma questão final após recarregar a página sem ampliar esse contrato.
- O servidor é local, vinculado a `127.0.0.1`. Para publicar, substitua o proxy por uma API HTTPS protegida e configure autenticação antes de expor a geração.
- As fontes têm alternativas locais caso Google Fonts não esteja acessível.

## Mascote

`public/mascot.png` foi criada pela ferramenta nativa de geração de imagens. Prompt: “Friendly cute feminine educational robot, full body standing arms open. White pearlescent armor, teal screen face with expressive eyes and a smile, magenta headphones, pink joints and belt, white and lavender high ponytail helmet. Polished cartoon illustration, entire figure visible, transparent background, no typography or UI, for a deep ultramarine website hero.”
