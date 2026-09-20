# Arquitetura do front

```text
haila-front/
├── public/
│   ├── app/
│   │   ├── api.js       cliente do contrato HAILA
│   │   ├── demo.js      dados demonstrativos identificados
│   │   ├── studio.js    fluxo e renderização do estúdio
│   │   └── webmcp.js    ferramentas opcionais para navegadores compatíveis
│   ├── index.html       apresentação
│   ├── studio.html      criação e revisão
│   ├── landing.css      identidade da apresentação
│   ├── style.css        layout do estúdio
│   ├── studio-theme.css cores do estúdio
│   ├── states.css       mensagens de sucesso, alerta e erro
│   ├── mascot.png       mascote da HAILA
│   └── favicon.svg
├── scripts/
│   ├── start_front.sh
│   └── check_integration.py
├── docs/
│   ├── API_CONTRACT.md
│   └── ARCHITECTURE.md
├── .env.example
├── README.md
└── server.py
```

O navegador conversa apenas com `/api`. O servidor local encaminha uma lista restrita de caminhos ao motor HAILA. Isso evita CORS, mantém o endereço do motor em um só lugar e impede que a página funcione como proxy aberto.

O fluxo de geração é assíncrono do ponto de vista visual: a chamada de geração permanece aberta enquanto o estúdio consulta o histórico em paralelo. Assim, o usuário acompanha RAG, LLM, SLM e red flags sem depender de dados inventados.
