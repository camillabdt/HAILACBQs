# Triagem automática das questões

> Esta triagem identifica sinais observáveis. Correção conceitual, unicidade do gabarito, plausibilidade dos distratores e adequação pedagógica exigem revisão semântica humana ou experimental separada.

## Resultado do piloto

- Questões avaliadas: 22
- Questões sem sinais automáticos: 13
- Questões encaminhadas para revisão: 9
- Sinais de bloqueio estrutural: 5
- Sinais de revisão: 6

## Por questão

### `50b77170-cebc-425a-a872-03028a35e0e0`

**Enunciado:** Uma transação em um SGBD sofre queda de energia antes de executar COMMIT. Considerando as propriedades ACID, qual delas assegura que a perda das alterações feitas até o ponto da falha não constitui violação da garantia oferecida pelo sistema?

- **possivel_desalinhamento_do_objeto_conhecimento** [semantica_triagem]: solicitado='arquitetura de computadores'; gerado='Propriedades ACID – atomicidade e durabilidade'; requer confirmação humana

### `2f619649-dfe7-49b2-bc71-9c94839bb326`

**Enunciado:** Qual padrão arquitetural descreve a organização em camadas da pilha TCP/IP, em que a camada de transporte fornece serviços de comunicação fim a fim aos processos da camada de aplicação?

- **idioma_inconsistente** [linguistica]: arquitectura, estructura

### `3bcfb3f5-6755-47f5-a179-d6f6659df1d4`

**Enunciado:** Cite uma funcionalidade fornecida pelo protocolo TCP que não está presente no protocolo UDP.

- **comando_resposta_aberta_em_item_objetivo** [linguistica]: Cite uma funcionalidade fornecida pelo protocolo TCP que não está presente no protocolo UDP.
- **possivel_desalinhamento_do_objeto_conhecimento** [semantica_triagem]: solicitado='arquitetura de computadores'; gerado='Protocolos de transporte TCP e UDP'; requer confirmação humana

### `e2223d66-590c-4c49-997e-25256c9f2049`

**Enunciado:** Em um projeto de software, quais requisitos são responsáveis por especificar atributos como desempenho, segurança, confiabilidade e usabilidade?

Nenhum sinal automático encontrado.

### `37f20290-4c55-433e-9b26-053133e20f8d`

**Enunciado:** Em um sistema de gerenciamento de banco de dados que garante as propriedades ACID, ocorre uma queda de energia imediatamente antes da execução do comando COMMIT de uma transação. Qual propriedade ACID, se houver, está sendo violada por essa falha?

Nenhum sinal automático encontrado.

### `dda7b947-5b81-4069-912d-4ffdfc6737a7`

**Enunciado:** Um sistema de videoconferência em tempo real deve minimizar a latência, podendo tolerar perda ocasional de pacotes, enquanto mantém a comunicação bidirecional entre clientes. Considerando as garantias oferecidas por TCP e UDP, qual protocolo de transporte é mais adequado para atender a esses requisitos?

- **selecao_de_protocolo_potencialmente_ambigua** [deterministica]: outros protocolos podem satisfazer o cenário; avalie garantias ou compare explicitamente TCP e UDP

### `76456ded-0792-4ef4-b132-d7bcdd1652bd`

**Enunciado:** Em um sistema bancário online, o requisito a seguir deve ser analisado: “O sistema deve garantir que a operação de transferência entre contas seja concluída em até 2 segundos.” Classifique esse requisito como funcional ou não funcional.

- **espaco_de_respostas_binario** [deterministica]: o comando restringe a resposta a duas classes, mas o item objetivo exige cinco alternativas plausíveis

### `53015de6-418d-43c2-b598-61e14f1163f7`

**Enunciado:** Um sistema de atendimento ao cliente registra as solicitações na ordem em que chegam e deve atender cada cliente exatamente nessa sequência, garantindo tempo O(1) para inserir uma nova solicitação e para remover a próxima a ser atendida. Qual estrutura de dados é a mais adequada para implementar essa fila de atendimento?

Nenhum sinal automático encontrado.

### `97400dc1-648f-403b-9088-3f00f3549439`

**Enunciado:** Uma empresa de comércio eletrônico deseja segmentar seus clientes em grupos com padrões de compra semelhantes, mas não possui rótulos que indiquem a qual segmento cada cliente pertence. Qual tipo de aprendizado de máquina deve ser empregado para realizar essa tarefa?

Nenhum sinal automático encontrado.

### `ddd10b0c-9960-4312-9510-618a4c7a236c`

**Enunciado:** Em um sistema de gerenciamento de banco de dados, uma transação é confirmada (COMMIT) e, imediatamente após, ocorre uma falha de energia que interrompe o servidor. Qual propriedade ACID assegura que os efeitos dessa transação permanecem no banco de dados após a recuperação?

- **possivel_desalinhamento_do_objeto_conhecimento** [semantica_triagem]: solicitado='banco de dados'; gerado='Propriedades ACID e controle de concorrência'; requer confirmação humana

### `40058529-c7d9-4955-b9de-3bd37adbf90e`

**Enunciado:** Uma transação em um SGBD ACID realizou alterações em duas tabelas e, antes da execução do comando COMMIT, ocorreu uma falha de energia que interrompeu o sistema. Qual propriedade do modelo ACID assegura que nenhuma dessas alterações permanecerá gravada no banco de dados?

Nenhum sinal automático encontrado.

### `89a2bef4-9eb3-4d9b-a410-e669625ebf9b`

**Enunciado:** Uma aplicação de streaming de vídeo em tempo real precisa de baixa latência, tolera perda de pacotes e não requer entrega ordenada nem controle de fluxo. Qual protocolo de transporte da camada TCP/IP deve ser escolhido?

- **selecao_de_protocolo_potencialmente_ambigua** [deterministica]: outros protocolos podem satisfazer o cenário; avalie garantias ou compare explicitamente TCP e UDP

### `45e49c4d-fffe-4f09-9e0b-6be50f9e00c3`

**Enunciado:** Em um sistema de gestão de biblioteca, foram especificados os seguintes requisitos: REQ1 – O usuário deve poder pesquisar livros por título; REQ2 – A pesquisa deve retornar resultados em até 2 segundos; REQ3 – O acesso ao sistema deve ser restrito a usuários autenticados; REQ4 – O sistema deve suportar até 500 usuários simultâneos. Qual desses requisitos corresponde a um requisito não funcional?

- **multiplos_candidatos_ao_gabarito** [deterministica]: 3 requisitos apresentam marcadores de requisito não funcional
- **alternativas_com_extensao_desequilibrada** [linguistica]: palavras por alternativa=[6, 1, 1, 1, 1]

### `560bd37f-a337-4a8a-9a88-2392863f4354`

**Enunciado:** Um interpretador de calculadora recebe expressões aritméticas em notação pós‑fixada (notação polonesa inversa) e deve avaliá‑las realizando sucessivas operações de empilhar operandos e desempilhar para aplicar operadores. Qual estrutura de dados é a mais adequada para implementar esse algoritmo, considerando as operações predominantes?

Nenhum sinal automático encontrado.

### `23ad82c2-b7a4-45bf-a8f8-aacd69a00577`

**Enunciado:** Uma empresa possui um histórico de 10.000 clientes contendo as variáveis idade, renda, número de compras nos últimos 6 meses e, para cada cliente, a informação se ele cancelou o serviço (sim ou não). O objetivo é criar um modelo que, a partir das características dos clientes, preveja se um novo cliente irá cancelar o serviço. Qual paradigma de aprendizado de máquina deve ser empregado?

Nenhum sinal automático encontrado.

### `716c6a17-9eba-476c-92cc-3ba4f0788094`

**Enunciado:** Um servidor de banco de dados sofre falha inesperada imediatamente antes de executar o comando COMMIT de uma transação que já realizou várias operações de escrita. Qual propriedade ACID assegura que nenhum desses efeitos permanecerá no banco após a recuperação?

Nenhum sinal automático encontrado.

### `42495f67-d615-4d4c-a010-738e56388cc7`

**Enunciado:** Uma aplicação de transferência de arquivos críticos exige que todos os bytes cheguem ao destino na mesma ordem em que foram enviados, mesmo que isso aumente o tempo de transmissão. Qual protocolo de transporte deve ser escolhido?

- **selecao_de_protocolo_potencialmente_ambigua** [deterministica]: outros protocolos podem satisfazer o cenário; avalie garantias ou compare explicitamente TCP e UDP

### `7e614912-8ffa-47c3-a055-e78d915aaad1`

**Enunciado:** Em um projeto de sistema de gerenciamento de biblioteca, foram identificados os seguintes requisitos: I – O sistema deve permitir que o usuário pesquise livros por título, autor ou ISBN. II – O tempo máximo de resposta para exibir os resultados de uma pesquisa não deve exceder 2 segundos. III – O sistema deve registrar todas as operações de empréstimo em um log auditável. IV – O sistema deve enviar e‑mail de confirmação ao usuário após a finalização do empréstimo. Qual desses requisitos é classificado como não funcional?

Nenhum sinal automático encontrado.

### `60774a2d-ff89-41b8-8e1f-6091408a6f95`

**Enunciado:** Um sistema de impressão recebe documentos de múltiplos usuários. Cada documento é colocado na fila de impressão na ordem de chegada e o spooler sempre envia o documento que está no início da fila para a impressora. Não há necessidade de buscar documentos aleatoriamente nem de reordenar a fila. Qual estrutura de dados é a mais adequada para implementar a fila de impressão?

Nenhum sinal automático encontrado.

### `ca66e36c-3f16-4ffe-accf-46a541f1fa12`

**Enunciado:** Uma empresa possui dados demográficos e de compras de seus clientes, mas não dispõe de rótulos indicando quem cancelou o serviço. Para descobrir grupos de clientes com comportamentos semelhantes e direcionar campanhas de marketing, qual paradigma de aprendizado de máquina deve ser empregado?

Nenhum sinal automático encontrado.

### `f6a83c2b-4da8-4b78-820a-fe8ec7b7c6db`

**Enunciado:** Um serviço de transferência de arquivos deve garantir que todos os bytes enviados cheguem ao destino sem perdas e na mesma sequência em que foram emitidos. Considerando as garantias oferecidas pelos protocolos de transporte TCP e UDP, quais garantias de nível de transporte são indispensáveis para atender a esses requisitos?

Nenhum sinal automático encontrado.

### `bdf3cf31-4a59-4367-ac77-808b27f42d32`

**Enunciado:** Uma empresa possui um histórico de compras de 10.000 clientes, contendo apenas os itens adquiridos e valores gastos, sem nenhuma informação pré‑definida sobre categorias ou rótulos. O objetivo é identificar grupos de clientes com padrões de consumo semelhantes para campanhas de marketing direcionado. Qual paradigma de aprendizado de máquina deve ser adotado para esse problema?

Nenhum sinal automático encontrado.

## Interpretação

A ausência de sinais não equivale a aprovação pedagógica. Os itens sinalizados devem ser apresentados sem identificação da configuração a professores, usando a ficha de avaliação humana.
