#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("HAILA_DIR", str(Path.home() / "HAILA"))).expanduser().resolve()
BACKEND = ROOT / "backend"
HAILA = BACKEND / "haila"
RAG_PY = HAILA / "rag.py"
CORPUS = BACKEND / "fontes_rag.jsonl"
TESTS = BACKEND / "tests"
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
BACKUP = Path.home() / f"HAILA-backup-rag-v4-{STAMP}"

if not ROOT.is_dir() or not HAILA.is_dir():
    raise SystemExit(f"ERRO: HAILA não encontrado em {ROOT}")

print("=" * 78)
print("HAILA — upgrade RAG v4 (cobertura + recuperação híbrida local)")
print("=" * 78)
print("Projeto:", ROOT)
print("Backup:", BACKUP)

BACKUP.mkdir(parents=True, exist_ok=True)
for src, rel in [(RAG_PY, "backend/haila/rag.py"), (CORPUS, "backend/fontes_rag.jsonl")]:
    if src.exists():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

# ---------------------------------------------------------------------------
# 1) Corpus seed conceitual amplo, curto e rastreável.
#    Texto autoral/parafraseado; referências funcionam como fonte bibliográfica,
#    não como transcrição de trechos.
# ---------------------------------------------------------------------------
chunks: list[dict] = []

def add(area, subarea, objeto, habilidade, texto, palavras, referencia):
    slug = re.sub(r"[^a-z0-9]+", "-", objeto.lower().encode("ascii", "ignore").decode()).strip("-")
    base_id = f"seed-{re.sub(r'[^a-z0-9]+','-',area.lower().encode('ascii','ignore').decode()).strip('-')}-{slug}"
    ident = base_id
    usados = {x["id"] for x in chunks}
    n = 2
    while ident in usados:
        ident = f"{base_id}-{n}"
        n += 1
    chunks.append({
        "id": ident,
        "texto_base": texto,
        "ano": 2026,
        "exame": "ACERVO_CONCEITUAL_HAILA",
        "curso": "Computação",
        "componente": "ESPECIFICO",
        "area": area,
        "subarea": subarea,
        "habilidade": habilidade,
        "objeto_conhecimento": objeto,
        "palavras_chave": palavras,
        "referencia": referencia,
        "fonte_tipo": "sintese_conceitual_curada",
        "origem": "HAILA_SEED_ENADE_POSCOMP_2026",
    })

# Redes de Computadores — cobertura propositalmente densa.
REF_NET = "KUROSE, J. F.; ROSS, K. W. Redes de Computadores e a Internet; TANENBAUM, A. S.; WETHERALL, D. Redes de Computadores."
add("Redes de Computadores","Fundamentos","Arquitetura TCP/IP e encapsulamento","Relacionar camadas, protocolos e unidades de dados","A arquitetura TCP/IP organiza a comunicação em camadas. Aplicação, transporte, internet e acesso à rede executam funções distintas; cada camada adiciona informações de controle durante o encapsulamento e as remove no destino.",["TCP/IP","camadas","encapsulamento","PDU","internet"],REF_NET)
add("Redes de Computadores","Enlace","Ethernet, quadros e endereços MAC","Analisar comunicação em redes locais","Ethernet usa endereços MAC para entrega de quadros no enlace local. Switches aprendem associações entre endereços MAC e portas e encaminham quadros de acordo com sua tabela de comutação.",["Ethernet","MAC","switch","quadro","LAN"],REF_NET)
add("Redes de Computadores","Enlace","ARP e resolução IPv4-MAC","Explicar resolução de endereços na rede local","ARP associa um endereço IPv4 a um endereço MAC dentro da rede local. Quando o destino está fora da sub-rede, o host resolve o MAC do gateway padrão e envia o quadro ao roteador.",["ARP","IPv4","MAC","gateway","resolução de endereços"],REF_NET)
add("Redes de Computadores","Camada de Rede","Endereçamento IPv4","Interpretar endereços IPv4 e prefixos","Um endereço IPv4 possui 32 bits. O prefixo identifica a rede e os bits restantes identificam endereços dentro da sub-rede; a notação CIDR /n informa quantos bits pertencem ao prefixo.",["IPv4","endereço IP","prefixo","32 bits","CIDR"],REF_NET)
add("Redes de Computadores","Camada de Rede","Máscara de sub-rede e CIDR","Calcular limites de uma sub-rede IPv4","A máscara de sub-rede separa bits de rede e host. Em CIDR, /24 equivale a 24 bits de prefixo; aumentar o prefixo cria sub-redes menores e reduz a quantidade de endereços disponível em cada uma.",["sub-rede","subrede","subnetting","CIDR","máscara","prefixo IPv4"],REF_NET)
add("Redes de Computadores","Camada de Rede","Subnetting IPv4","Dividir uma rede em sub-redes","Para dividir uma rede IPv4 em sub-redes, bits originalmente destinados a hosts são incorporados ao prefixo. Cada bit adicional no prefixo dobra o número de sub-redes possíveis e reduz pela metade o bloco de endereços de cada sub-rede.",["subnetting","IPv4","sub-redes","máscara","prefixo"],REF_NET)
add("Redes de Computadores","Camada de Rede","VLSM e alocação de sub-redes","Aplicar máscaras de tamanho variável","VLSM permite empregar prefixos diferentes dentro de um mesmo bloco para adequar o tamanho das sub-redes às necessidades de cada segmento. A alocação costuma começar pelas maiores necessidades de endereços para evitar fragmentação do espaço.",["VLSM","CIDR","sub-rede","prefixos","endereçamento"],REF_NET)
add("Redes de Computadores","Camada de Rede","Endereço de rede, broadcast e hosts IPv4","Determinar faixas de endereços","Em uma sub-rede IPv4 tradicional, o primeiro endereço representa a rede e o último é o broadcast dirigido; os endereços intermediários podem ser atribuídos a interfaces de hosts, observadas exceções e usos especiais.",["endereço de rede","broadcast","hosts","IPv4","sub-rede"],REF_NET)
add("Redes de Computadores","Camada de Rede","NAT e tradução de endereços","Analisar tradução entre redes privadas e públicas","NAT altera informações de endereçamento ao atravessar um dispositivo de borda. NAPT/PAT diferencia conexões também por portas, permitindo que diversos hosts privados compartilhem um endereço IPv4 público.",["NAT","PAT","NAPT","IPv4 privado","endereço público"],REF_NET)
add("Redes de Computadores","Camada de Rede","DHCP e configuração automática","Explicar obtenção dinâmica de parâmetros de rede","DHCP fornece parâmetros como endereço IP, máscara, gateway e servidor DNS. O processo clássico envolve descoberta, oferta, solicitação e confirmação da concessão.",["DHCP","gateway","máscara","DNS","configuração IP"],REF_NET)
add("Redes de Computadores","Camada de Rede","ICMP e diagnóstico de rede","Interpretar mensagens de controle IP","ICMP transporta mensagens de controle e erro usadas por ferramentas de diagnóstico. Echo Request/Reply é empregado pelo ping, enquanto mensagens relacionadas a TTL ajudam a revelar saltos no traceroute.",["ICMP","ping","traceroute","TTL","diagnóstico"],REF_NET)
add("Redes de Computadores","Camada de Rede","Roteamento IP e tabela de rotas","Selecionar próximo salto","Roteadores encaminham pacotes consultando uma tabela de rotas. Quando várias rotas correspondem ao destino, a regra de maior prefixo, também chamada longest prefix match, seleciona a rota mais específica.",["roteamento","roteador","tabela de rotas","longest prefix match","próximo salto"],REF_NET)
add("Redes de Computadores","Camada de Rede","Roteamento estático e rota padrão","Configurar decisões básicas de encaminhamento","Rotas estáticas são inseridas administrativamente e não se adaptam automaticamente a mudanças de topologia. Uma rota padrão é usada quando nenhuma rota mais específica corresponde ao destino.",["roteamento estático","rota padrão","gateway","tabela de rotas"],REF_NET)
add("Redes de Computadores","Camada de Rede","Vetor de distância e RIP","Comparar algoritmos de roteamento","Protocolos de vetor de distância trocam estimativas de custo com vizinhos e atualizam rotas com base nessas informações. RIP utiliza contagem de saltos como métrica e possui limitações de escalabilidade e convergência.",["RIP","vetor de distância","roteamento dinâmico","métrica","convergência"],REF_NET)
add("Redes de Computadores","Camada de Rede","Estado de enlace e OSPF","Comparar algoritmos de roteamento","Protocolos de estado de enlace disseminam informações da topologia para que roteadores calculem caminhos. OSPF utiliza uma visão do estado de enlaces e cálculo de menor caminho dentro de uma área.",["OSPF","estado de enlace","Dijkstra","roteamento dinâmico","menor caminho"],REF_NET)
add("Redes de Computadores","Camada de Rede","BGP e roteamento entre sistemas autônomos","Distinguir roteamento intra e interdomínio","BGP é usado para troca de alcançabilidade entre sistemas autônomos e seleciona caminhos com base em atributos e políticas, não apenas na menor distância física.",["BGP","sistema autônomo","AS","roteamento interdomínio","políticas"],REF_NET)
add("Redes de Computadores","Camada de Rede","IPv6 e estrutura de endereçamento","Comparar IPv4 e IPv6","IPv6 utiliza endereços de 128 bits e representação hexadecimal. O cabeçalho base foi simplificado em relação ao IPv4 e mecanismos como Neighbor Discovery substituem funções associadas ao ARP.",["IPv6","128 bits","Neighbor Discovery","NDP","IPv4"],REF_NET)
add("Redes de Computadores","Transporte","TCP: conexão e confiabilidade","Analisar garantias do TCP","TCP é orientado a conexão e fornece fluxo de bytes confiável e ordenado, usando números de sequência, confirmações, retransmissões e controle de fluxo. Também implementa mecanismos de controle de congestionamento.",["TCP","confiabilidade","ACK","sequência","retransmissão"],REF_NET)
add("Redes de Computadores","Transporte","UDP e comunicação sem conexão","Comparar TCP e UDP","UDP oferece serviço sem conexão e baixa sobrecarga, sem garantir entrega, ordem ou retransmissão. É adequado quando a aplicação tolera perdas ou implementa suas próprias regras de confiabilidade e temporização.",["UDP","datagrama","sem conexão","baixa latência","transporte"],REF_NET)
add("Redes de Computadores","Transporte","Portas e multiplexação","Relacionar processos a conexões de transporte","TCP e UDP utilizam números de porta para identificar pontos finais de comunicação na camada de transporte. A combinação de endereços, portas e protocolo permite distinguir fluxos simultâneos.",["porta","socket","TCP","UDP","multiplexação"],REF_NET)
add("Redes de Computadores","Aplicação","DNS e resolução de nomes","Explicar resolução hierárquica de nomes","DNS é um sistema distribuído e hierárquico que associa nomes a informações como endereços IP. Registros A apontam para IPv4, AAAA para IPv6 e outros tipos descrevem servidores e aliases.",["DNS","A","AAAA","resolução de nomes","servidor DNS"],REF_NET)
add("Redes de Computadores","Aplicação","HTTP e modelo requisição-resposta","Analisar comunicação Web","HTTP organiza a comunicação Web em requisições e respostas. Métodos como GET e POST expressam operações, códigos de status indicam resultados e versões modernas podem reutilizar ou multiplexar conexões.",["HTTP","HTTPS","GET","POST","status HTTP"],REF_NET)
add("Redes de Computadores","Aplicação","TLS e proteção do transporte","Relacionar TLS a confidencialidade e autenticação","TLS protege comunicações por meio de negociação criptográfica, autenticação baseada em certificados quando aplicável e chaves de sessão. HTTPS é HTTP transportado sobre uma conexão protegida por TLS.",["TLS","HTTPS","certificado","criptografia","handshake"],REF_NET)
add("Redes de Computadores","Sem fio","Wi-Fi e acesso ao meio","Analisar redes IEEE 802.11","Redes Wi-Fi baseadas em IEEE 802.11 compartilham o meio sem fio e usam mecanismos de acesso projetados para reduzir colisões. Pontos de acesso integram estações sem fio à infraestrutura da rede.",["Wi-Fi","802.11","CSMA/CA","ponto de acesso","WLAN"],REF_NET)

# Algoritmos e Estruturas de Dados
REF_ALG = "CORMEN, T. H. et al. Introduction to Algorithms."
add("Algoritmos e Estruturas de Dados","Análise","Complexidade assintótica e Big-O","Analisar eficiência de algoritmos","Notações assintóticas descrevem o crescimento do custo de um algoritmo quando o tamanho da entrada aumenta. Big-O fornece um limite superior assintótico; Θ caracteriza crescimento assintoticamente justo quando limites superior e inferior coincidem.",["Big-O","Theta","complexidade","assintótica"],REF_ALG)
add("Algoritmos e Estruturas de Dados","Ordenação","Algoritmos de ordenação","Comparar estratégias de ordenação","Algoritmos de ordenação diferem em custo, estabilidade e uso de memória. Merge sort possui tempo O(n log n) no pior caso, enquanto quicksort tem bom desempenho médio, mas pode chegar a O(n²) com escolhas desfavoráveis de pivô.",["ordenação","merge sort","quicksort","estabilidade"],REF_ALG)
add("Algoritmos e Estruturas de Dados","Busca","Busca binária","Aplicar busca em sequências ordenadas","Busca binária requer uma sequência ordenada e reduz pela metade o intervalo de busca a cada comparação, resultando em O(log n) comparações no pior caso.",["busca binária","log n","vetor ordenado"],REF_ALG)
add("Algoritmos e Estruturas de Dados","Estruturas Lineares","Pilhas e filas","Selecionar estruturas lineares","Pilhas seguem disciplina LIFO, com inserção e remoção no topo. Filas seguem FIFO, preservando a ordem de chegada entre elementos removidos.",["pilha","fila","LIFO","FIFO"],REF_ALG)
add("Algoritmos e Estruturas de Dados","Árvores","Árvores binárias de busca","Analisar operações em árvores de busca","Em uma árvore binária de busca, chaves menores ficam em uma subárvore e maiores em outra conforme a regra adotada. Busca, inserção e remoção dependem da altura; árvores desbalanceadas podem degradar para comportamento linear.",["BST","árvore binária de busca","altura","busca"],REF_ALG)
add("Algoritmos e Estruturas de Dados","Árvores","Árvores AVL e balanceamento","Explicar balanceamento de árvores","Árvores AVL mantêm restrição sobre a diferença de alturas entre subárvores e usam rotações após atualizações para preservar altura O(log n), garantindo operações de busca e atualização logarítmicas.",["AVL","rotação","balanceamento","árvore"],REF_ALG)
add("Algoritmos e Estruturas de Dados","Heaps","Heap e fila de prioridade","Relacionar heaps a prioridades","Um heap binário mantém uma ordem parcial entre pais e filhos. Em um max-heap o maior elemento fica na raiz; inserção e remoção do elemento prioritário custam O(log n).",["heap","fila de prioridade","max-heap","min-heap"],REF_ALG)
add("Algoritmos e Estruturas de Dados","Hashing","Tabelas hash e colisões","Analisar acesso por chave","Tabelas hash mapeiam chaves para posições por uma função de espalhamento. Colisões podem ser tratadas por encadeamento ou endereçamento aberto; desempenho depende da função e do fator de carga.",["hash","colisão","fator de carga","encadeamento"],REF_ALG)
add("Algoritmos e Estruturas de Dados","Grafos","Busca em largura e profundidade","Comparar BFS e DFS","BFS explora vértices por níveis e encontra caminhos com menor número de arestas em grafos não ponderados. DFS aprofunda uma ramificação antes de retroceder e é útil em tarefas como classificação topológica e detecção estrutural.",["BFS","DFS","grafo","busca em largura","busca em profundidade"],REF_ALG)
add("Algoritmos e Estruturas de Dados","Grafos","Dijkstra e menores caminhos","Aplicar algoritmo de menor caminho","Dijkstra calcula menores distâncias a partir de uma origem quando os pesos das arestas são não negativos. A presença de arestas negativas invalida a garantia do procedimento guloso clássico.",["Dijkstra","menor caminho","pesos não negativos","grafo"],REF_ALG)
add("Algoritmos e Estruturas de Dados","Grafos","Bellman-Ford e pesos negativos","Analisar caminhos com pesos negativos","Bellman-Ford relaxa repetidamente as arestas, aceita pesos negativos e pode detectar ciclo negativo alcançável quando uma relaxação ainda é possível após as passagens previstas.",["Bellman-Ford","peso negativo","ciclo negativo","relaxamento"],REF_ALG)
add("Algoritmos e Estruturas de Dados","Grafos","Floyd-Warshall","Calcular caminhos mínimos entre todos os pares","Floyd-Warshall usa programação dinâmica para calcular distâncias entre todos os pares de vértices em tempo O(n³). Ciclos negativos podem ser detectados quando alguma distância diagonal se torna negativa.",["Floyd-Warshall","todos os pares","programação dinâmica","ciclo negativo"],REF_ALG)
add("Algoritmos e Estruturas de Dados","Grafos","Árvore geradora mínima","Comparar Prim e Kruskal","Prim e Kruskal constroem árvores geradoras mínimas em grafos ponderados não direcionados. Kruskal escolhe arestas em ordem crescente evitando ciclos; Prim expande uma árvore a partir de um conjunto já conectado.",["MST","Prim","Kruskal","árvore geradora mínima"],REF_ALG)
add("Algoritmos e Estruturas de Dados","Paradigmas","Programação dinâmica","Reconhecer subestrutura ótima e sobreposição","Programação dinâmica armazena resultados de subproblemas para evitar recomputação quando existe sobreposição de subproblemas e estrutura adequada para combinar soluções parciais.",["programação dinâmica","memoization","subproblemas","subestrutura ótima"],REF_ALG)
add("Algoritmos e Estruturas de Dados","Paradigmas","Algoritmos gulosos","Analisar escolhas locais","Algoritmos gulosos constroem uma solução por escolhas localmente melhores. Sua correção exige propriedades específicas do problema; uma estratégia gulosa não é automaticamente ótima em qualquer contexto.",["greedy","guloso","escolha local","otimalidade"],REF_ALG)

# Banco de Dados
REF_DB = "ELMASRI, R.; NAVATHE, S. Sistemas de Banco de Dados; SILBERSCHATZ, A.; KORTH, H.; SUDARSHAN, S. Database System Concepts."
add("Banco de Dados","Modelo Relacional","Modelo relacional e chaves","Modelar relações e integridade","No modelo relacional, uma relação representa um conjunto de tuplas sobre atributos. Chaves candidatas identificam tuplas, a chave primária é escolhida entre elas e chaves estrangeiras expressam referências entre relações.",["modelo relacional","chave primária","chave estrangeira","tupla"],REF_DB)
add("Banco de Dados","SQL","Junções SQL","Interpretar operações de junção","INNER JOIN retorna combinações que satisfazem a condição de junção. Junções externas preservam linhas de um ou ambos os lados mesmo quando não existe correspondência, preenchendo atributos ausentes com NULL.",["SQL","JOIN","INNER JOIN","LEFT JOIN","NULL"],REF_DB)
add("Banco de Dados","SQL","Agregação, GROUP BY e HAVING","Construir consultas agregadas","Funções agregadas resumem conjuntos de linhas. GROUP BY define grupos e HAVING filtra grupos após agregação, enquanto WHERE filtra linhas antes dessa etapa lógica.",["GROUP BY","HAVING","WHERE","COUNT","agregação"],REF_DB)
add("Banco de Dados","Projeto","Normalização e dependências funcionais","Analisar decomposição de esquemas","Normalização usa dependências funcionais para reduzir redundância e anomalias de atualização. A terceira forma normal e BCNF impõem condições sobre determinantes e dependências, com diferentes compromissos de decomposição.",["normalização","3FN","BCNF","dependência funcional"],REF_DB)
add("Banco de Dados","Transações","Propriedades ACID","Explicar propriedades transacionais","Atomicidade trata a transação como unidade indivisível; consistência preserva regras válidas; isolamento controla interferência entre transações concorrentes; durabilidade preserva efeitos confirmados mesmo após falhas.",["ACID","atomicidade","consistência","isolamento","durabilidade"],REF_DB)
add("Banco de Dados","Concorrência","Anomalias de isolamento","Distinguir anomalias concorrentes","Leitura suja ocorre quando dados não confirmados são lidos; leitura não repetível ocorre quando a mesma linha confirmada muda entre leituras; leitura fantasma envolve mudança no conjunto de linhas que satisfaz uma condição.",["leitura suja","leitura não repetível","fantasma","isolamento"],REF_DB)
add("Banco de Dados","Concorrência","Bloqueios e serialização","Analisar controle de concorrência","Protocolos de bloqueio controlam acesso concorrente a itens de dados. Bloqueios compartilhados permitem leituras compatíveis e bloqueios exclusivos restringem operações conflitantes; protocolos como 2PL buscam serialização.",["2PL","bloqueio compartilhado","bloqueio exclusivo","serializabilidade"],REF_DB)
add("Banco de Dados","Índices","Índices B+ tree","Analisar estruturas de indexação","Árvores B+ mantêm chaves ordenadas e pequena altura, sendo adequadas a buscas pontuais e por intervalo em armazenamento secundário. Índices aceleram leituras, mas adicionam custo de espaço e manutenção em atualizações.",["B+ tree","índice","busca por intervalo","indexação"],REF_DB)
add("Banco de Dados","Recuperação","Log, commit e recuperação","Explicar recuperação após falhas","Sistemas transacionais usam registros de log para apoiar recuperação. Técnicas de write-ahead logging exigem que informações necessárias à recuperação sejam persistidas antes de certas modificações de dados.",["WAL","log","recuperação","commit","rollback"],REF_DB)
add("Banco de Dados","NoSQL","Modelos NoSQL e consistência","Comparar modelos de armazenamento","Bancos NoSQL podem organizar dados como chave-valor, documentos, colunas ou grafos. A escolha depende de padrões de consulta, escalabilidade, modelo de consistência e necessidades de relacionamento.",["NoSQL","documentos","chave-valor","grafos","consistência"],REF_DB)

# Engenharia de Software
REF_SE = "SOMMERVILLE, I. Engenharia de Software; PRESSMAN, R.; MAXIM, B. Software Engineering: A Practitioner's Approach."
add("Engenharia de Software","Requisitos","Requisitos funcionais e não funcionais","Classificar requisitos","Requisitos funcionais descrevem serviços e comportamentos observáveis do sistema. Requisitos não funcionais expressam atributos de qualidade, restrições ou condições sobre a solução, como desempenho, segurança e disponibilidade.",["requisito funcional","requisito não funcional","qualidade","restrição"],REF_SE)
add("Engenharia de Software","Requisitos","Elicitação e validação de requisitos","Analisar atividades de engenharia de requisitos","Elicitação busca compreender necessidades de partes interessadas; especificação registra requisitos; validação verifica se representam corretamente necessidades e possuem propriedades como clareza, consistência e testabilidade.",["elicitação","especificação","validação","stakeholder"],REF_SE)
add("Engenharia de Software","Requisitos","Rastreabilidade e mudança","Gerenciar evolução de requisitos","Rastreabilidade relaciona requisitos a fontes, artefatos de projeto, implementação e testes. Quando um requisito muda, esses vínculos ajudam a analisar impacto e manter consistência entre artefatos.",["rastreabilidade","mudança","impacto","requisitos"],REF_SE)
add("Engenharia de Software","Processos","Modelos de processo de software","Comparar processos de desenvolvimento","Modelos de processo organizam atividades de especificação, desenvolvimento, validação e evolução. Processos sequenciais favorecem planejamento antecipado; abordagens iterativas e incrementais incorporam feedback ao longo das entregas.",["cascata","iterativo","incremental","processo de software"],REF_SE)
add("Engenharia de Software","Ágil","Scrum e desenvolvimento iterativo","Analisar práticas ágeis","Scrum organiza trabalho em ciclos curtos, mantendo um backlog priorizado e inspecionando incrementos regularmente. Papéis, eventos e artefatos buscam transparência, inspeção e adaptação.",["Scrum","sprint","backlog","incremento"],REF_SE)
add("Engenharia de Software","Projeto","Coesão e acoplamento","Avaliar modularidade","Alta coesão mantém responsabilidades relacionadas dentro de um módulo, enquanto baixo acoplamento reduz dependências entre módulos. Esses princípios favorecem manutenção, teste e evolução.",["coesão","acoplamento","modularidade","projeto"],REF_SE)
add("Engenharia de Software","Arquitetura","Arquiteturas em camadas e serviços","Comparar estilos arquiteturais","Arquiteturas em camadas separam responsabilidades por níveis; arquiteturas orientadas a serviços ou microsserviços decompõem capacidades em serviços com interfaces explícitas. Cada escolha afeta implantação, acoplamento e operação.",["arquitetura em camadas","microsserviços","serviços","arquitetura"],REF_SE)
add("Engenharia de Software","Testes","Testes unitários, integração e sistema","Distinguir níveis de teste","Teste unitário foca unidades isoladas; teste de integração verifica interações entre componentes; teste de sistema avalia o produto integrado contra requisitos. Critérios e oráculos determinam o que deve ser exercitado e como julgar resultados.",["teste unitário","integração","teste de sistema","oráculo"],REF_SE)
add("Engenharia de Software","Testes","Caixa-preta e caixa-branca","Comparar técnicas de teste","Técnicas de caixa-preta derivam casos a partir de entradas, saídas e especificações, sem depender da estrutura interna. Técnicas de caixa-branca usam informações do código e fluxo de controle para orientar cobertura.",["caixa-preta","caixa-branca","cobertura","teste"],REF_SE)
add("Engenharia de Software","Qualidade","Atributos de qualidade de software","Avaliar qualidades do produto","Qualidade de software envolve atributos como adequação funcional, confiabilidade, usabilidade, eficiência de desempenho, segurança, manutenibilidade, compatibilidade e portabilidade, conforme o modelo considerado.",["qualidade","confiabilidade","usabilidade","manutenibilidade","ISO 25010"],REF_SE)
add("Engenharia de Software","Manutenção","Manutenção e evolução de software","Classificar mudanças pós-entrega","Manutenção corretiva remove defeitos; adaptativa responde a mudanças de ambiente; perfectiva melhora desempenho ou funcionalidades; preventiva busca reduzir problemas futuros e facilitar evolução.",["manutenção corretiva","adaptativa","perfectiva","preventiva"],REF_SE)
add("Engenharia de Software","Configuração","Controle de versão e integração contínua","Relacionar práticas de configuração e entrega","Controle de versão registra evolução e permite colaboração sobre artefatos. Integração contínua automatiza compilação, testes e outras verificações frequentes para detectar problemas cedo.",["Git","controle de versão","CI","integração contínua"],REF_SE)

# Sistemas Operacionais
REF_OS = "SILBERSCHATZ, A.; GALVIN, P.; GAGNE, G. Operating System Concepts; TANENBAUM, A. Modern Operating Systems."
add("Sistemas Operacionais","Processos","Processos e estados","Analisar ciclo de vida de processos","Um processo representa um programa em execução com contexto próprio. Sistemas operacionais mantêm estados como pronto, executando e bloqueado e realizam trocas de contexto para alternar a CPU entre processos.",["processo","estado","troca de contexto","CPU"],REF_OS)
add("Sistemas Operacionais","Threads","Processos e threads","Comparar unidades de execução","Threads de um mesmo processo compartilham recursos como espaço de endereçamento, mas possuem contexto de execução próprio. Elas podem aumentar responsividade e paralelismo, exigindo sincronização sobre dados compartilhados.",["thread","processo","paralelismo","memória compartilhada"],REF_OS)
add("Sistemas Operacionais","Escalonamento","Escalonamento de CPU","Comparar políticas de escalonamento","Políticas de escalonamento escolhem qual processo pronto recebe a CPU. FCFS, SJF, prioridade e Round Robin apresentam compromissos diferentes entre tempo de espera, resposta, justiça e sobrecarga.",["FCFS","SJF","Round Robin","escalonamento"],REF_OS)
add("Sistemas Operacionais","Sincronização","Região crítica, mutex e semáforo","Controlar acesso concorrente","Regiões críticas acessam estado compartilhado e precisam de exclusão adequada para evitar condições de corrida. Mutexes fornecem exclusão mútua; semáforos podem controlar disponibilidade de recursos e sincronização entre fluxos.",["mutex","semáforo","região crítica","condição de corrida"],REF_OS)
add("Sistemas Operacionais","Deadlock","Condições para deadlock","Analisar impasses","Deadlock pode ocorrer quando coexistem exclusão mútua, posse e espera, ausência de preempção e espera circular. Estratégias incluem prevenção, evitação, detecção e recuperação.",["deadlock","espera circular","prevenção","detecção"],REF_OS)
add("Sistemas Operacionais","Memória","Paginação e memória virtual","Analisar tradução de endereços","Paginação divide endereços virtuais em páginas e memória física em quadros. Tabelas de páginas realizam o mapeamento e uma TLB armazena traduções recentes para reduzir custo de acesso.",["paginação","memória virtual","TLB","página","quadro"],REF_OS)
add("Sistemas Operacionais","Memória","Substituição de páginas","Comparar políticas de substituição","Quando ocorre falta de página e não há quadro livre, uma política escolhe uma página para substituição. FIFO, LRU e aproximações têm comportamentos diferentes e podem afetar a taxa de faltas.",["page replacement","FIFO","LRU","falta de página"],REF_OS)
add("Sistemas Operacionais","Arquivos","Sistemas de arquivos e alocação","Analisar organização de arquivos","Sistemas de arquivos organizam nomes, diretórios, metadados e blocos de armazenamento. Estratégias de alocação e estruturas de índices afetam acesso, fragmentação e recuperação de espaço.",["sistema de arquivos","inode","diretório","alocação"],REF_OS)
add("Sistemas Operacionais","E/S","Interrupções e DMA","Relacionar CPU e dispositivos","Interrupções permitem que dispositivos sinalizem eventos à CPU sem espera ocupada contínua. DMA permite transferências entre dispositivo e memória com menor intervenção da CPU em cada unidade transferida.",["interrupção","DMA","entrada e saída","dispositivo"],REF_OS)

# Arquitetura e Organização
REF_ARCH = "PATTERSON, D.; HENNESSY, J. Computer Organization and Design."
add("Arquitetura e Organização de Computadores","Processador","Ciclo de instrução e datapath","Analisar execução de instruções","A execução de uma instrução envolve busca, decodificação e operações no caminho de dados. Unidade de controle coordena registradores, ALU, memória e demais componentes conforme a instrução.",["datapath","ALU","registradores","ciclo de instrução"],REF_ARCH)
add("Arquitetura e Organização de Computadores","Processador","Pipeline e hazards","Analisar paralelismo em nível de instrução","Pipeline sobrepõe etapas de instruções diferentes para aumentar vazão. Hazards estruturais, de dados e de controle podem exigir forwarding, stalls ou técnicas de previsão.",["pipeline","hazard","forwarding","stall"],REF_ARCH)
add("Arquitetura e Organização de Computadores","Memória","Hierarquia de memória e localidade","Explicar desempenho da hierarquia","Hierarquias combinam níveis pequenos e rápidos com níveis maiores e mais lentos. Localidade temporal e espacial permite que caches mantenham dados e instruções com alta probabilidade de reutilização.",["cache","localidade","memória","hierarquia"],REF_ARCH)
add("Arquitetura e Organização de Computadores","Cache","Mapeamento e políticas de cache","Comparar organizações de cache","Caches podem ser de mapeamento direto, associativas por conjunto ou totalmente associativas. Políticas de substituição e escrita influenciam taxa de acertos, tráfego e complexidade.",["cache","mapeamento direto","associatividade","write-back","write-through"],REF_ARCH)
add("Arquitetura e Organização de Computadores","Representação","Representação binária e complemento de dois","Interpretar representação de inteiros","Complemento de dois representa inteiros com sinal de modo que soma e subtração possam compartilhar circuitos. O bit mais significativo participa do peso negativo e a faixa é assimétrica em torno de zero.",["complemento de dois","binário","overflow","inteiro"],REF_ARCH)
add("Arquitetura e Organização de Computadores","Paralelismo","Multicore e paralelismo","Relacionar hardware paralelo e software","Processadores multicore executam fluxos simultaneamente, mas ganho depende da fração paralelizável, comunicação e sincronização. Paralelismo não elimina gargalos sequenciais ou contenção por recursos compartilhados.",["multicore","paralelismo","Amdahl","sincronização"],REF_ARCH)

# Inteligência Artificial
REF_AI = "RUSSELL, S.; NORVIG, P. Artificial Intelligence: A Modern Approach."
add("Inteligência Artificial","Busca","Busca em largura, profundidade e custo uniforme","Comparar estratégias de busca","Busca em largura expande nós por profundidade e é ótima para custos unitários; busca em profundidade usa pouca memória, mas não garante menor solução; custo uniforme prioriza menor custo acumulado.",["busca em largura","busca em profundidade","custo uniforme","espaço de estados"],REF_AI)
add("Inteligência Artificial","Busca","A* e heurísticas","Aplicar busca heurística","A* prioriza nós por f(n)=g(n)+h(n). Com condições adequadas, uma heurística admissível não superestima o custo restante e permite obter solução ótima.",["A*","heurística","admissível","g(n)","h(n)"],REF_AI)
add("Inteligência Artificial","Jogos","Minimax e poda alfa-beta","Analisar decisões adversariais","Minimax escolhe ações considerando um oponente que também otimiza seu resultado. Poda alfa-beta elimina ramos que não podem alterar a decisão final, preservando o resultado do minimax.",["minimax","alfa-beta","jogos","adversarial"],REF_AI)
add("Inteligência Artificial","Aprendizado","Aprendizado supervisionado e não supervisionado","Distinguir paradigmas de aprendizado","Aprendizado supervisionado usa exemplos com alvo para aprender uma função preditiva. Aprendizado não supervisionado procura estrutura em dados sem rótulos, como agrupamentos ou representações.",["supervisionado","não supervisionado","rótulo","classificação","clustering"],REF_AI)
add("Inteligência Artificial","Avaliação","Matriz de confusão, precisão, recall e F1","Calcular métricas de classificação","Precisão mede a proporção de predições positivas que estão corretas; recall mede a proporção de positivos reais recuperados; F1 é a média harmônica entre precisão e recall.",["precision","recall","F1","matriz de confusão"],REF_AI)
add("Inteligência Artificial","Generalização","Overfitting, validação e regularização","Analisar generalização de modelos","Overfitting ocorre quando o modelo se ajusta excessivamente aos dados de treino e generaliza mal. Separação de validação, regularização, controle de complexidade e mais dados podem ajudar a reduzir o problema.",["overfitting","validação","regularização","generalização"],REF_AI)
add("Inteligência Artificial","Modelos","Árvores de decisão","Interpretar modelos baseados em regras","Árvores de decisão particionam o espaço por testes sobre atributos. Critérios de divisão buscam aumentar pureza ou reduzir incerteza; profundidade excessiva pode aumentar sobreajuste.",["árvore de decisão","entropia","Gini","classificação"],REF_AI)
add("Inteligência Artificial","Agrupamento","K-means","Analisar agrupamento por centróides","K-means alterna atribuição de pontos ao centróide mais próximo e atualização dos centróides. O resultado depende de k, inicialização e geometria dos dados, e o método é sensível a escala e outliers.",["k-means","cluster","centróide","agrupamento"],REF_AI)
add("Inteligência Artificial","Redes Neurais","Treinamento de redes neurais","Explicar otimização em redes","Redes neurais combinam transformações parametrizadas e funções de ativação. Treinamento usa retropropagação para calcular gradientes e um otimizador para ajustar pesos com base em uma função de perda.",["rede neural","backpropagation","gradiente","função de perda"],REF_AI)

# Segurança
REF_SEC = "STALLINGS, W. Cryptography and Network Security; OWASP Foundation, OWASP Top 10."
add("Segurança da Informação","Fundamentos","Confidencialidade, integridade e disponibilidade","Relacionar objetivos de segurança","Confidencialidade limita acesso indevido à informação; integridade protege contra alteração não autorizada; disponibilidade busca manter serviços e dados acessíveis quando necessários.",["CIA","confidencialidade","integridade","disponibilidade"],REF_SEC)
add("Segurança da Informação","Criptografia","Criptografia simétrica e assimétrica","Comparar mecanismos criptográficos","Criptografia simétrica utiliza uma chave compartilhada e é eficiente para grandes volumes. Criptografia assimétrica usa pares de chaves e viabiliza mecanismos como troca de chaves, autenticação e assinatura digital.",["AES","RSA","simétrica","assimétrica","chave pública"],REF_SEC)
add("Segurança da Informação","Criptografia","Hash, MAC e assinatura digital","Distinguir garantias criptográficas","Hash criptográfico produz um resumo de tamanho fixo; MAC combina segredo e mensagem para autenticar integridade e origem entre partes que compartilham chave; assinatura digital usa criptografia assimétrica para autenticidade e integridade verificável.",["hash","HMAC","MAC","assinatura digital"],REF_SEC)
add("Segurança da Informação","Autenticação","Autenticação multifator e credenciais","Analisar mecanismos de autenticação","Autenticação verifica identidade por fatores como conhecimento, posse e inerência. Combinar fatores independentes reduz o impacto do comprometimento de uma única credencial.",["MFA","2FA","autenticação","credencial"],REF_SEC)
add("Segurança da Informação","Autorização","Controle de acesso","Comparar modelos de autorização","Controle de acesso define quais ações sujeitos podem executar sobre recursos. Modelos incluem DAC, MAC e RBAC, que organizam permissões por propriedade, políticas ou papéis.",["RBAC","DAC","MAC","autorização","controle de acesso"],REF_SEC)
add("Segurança da Informação","Web","Injeção e validação de entrada","Identificar vulnerabilidades de aplicações","Falhas de injeção ocorrem quando entrada não confiável altera a interpretação de comandos ou consultas. Consultas parametrizadas, validação apropriada e separação entre dados e comandos reduzem o risco.",["SQL injection","injeção","parametrização","validação"],REF_SEC)
add("Segurança da Informação","Web","XSS e conteúdo não confiável","Analisar execução de scripts no cliente","Cross-Site Scripting permite que conteúdo controlado por atacante seja interpretado como código no navegador. Codificação contextual de saída, políticas de conteúdo e manipulação segura do DOM ajudam a reduzir a exposição.",["XSS","CSP","escape","DOM"],REF_SEC)
add("Segurança da Informação","Redes","Firewall e segmentação","Analisar controles de rede","Firewalls aplicam regras ao tráfego com base em atributos de comunicação e estado. Segmentação reduz exposição lateral ao separar zonas e limitar fluxos conforme necessidade de negócio e segurança.",["firewall","segmentação","ACL","stateful"],REF_SEC)
add("Segurança da Informação","PKI","Certificados e infraestrutura de chaves públicas","Explicar confiança em certificados","Certificados associam identidades a chaves públicas por meio de assinaturas de autoridades certificadoras. Cadeias de confiança permitem verificar se um certificado apresentado deriva de uma raiz confiável.",["PKI","certificado","CA","cadeia de confiança"],REF_SEC)

# Teoria da Computação e Linguagens Formais
REF_THEORY = "SIPSER, M. Introduction to the Theory of Computation."
add("Teoria da Computação","Linguagens Regulares","Autômatos finitos e expressões regulares","Relacionar modelos para linguagens regulares","Autômatos finitos determinísticos e não determinísticos reconhecem exatamente as linguagens regulares; expressões regulares possuem poder expressivo equivalente para essa classe.",["DFA","NFA","expressão regular","linguagem regular"],REF_THEORY)
add("Teoria da Computação","Linguagens Livres de Contexto","Gramáticas livres de contexto e pilha","Relacionar gramáticas e autômatos de pilha","Gramáticas livres de contexto descrevem uma classe mais expressiva que linguagens regulares. Autômatos de pilha reconhecem linguagens livres de contexto e usam uma pilha como memória auxiliar.",["CFG","PDA","gramática livre de contexto","autômato de pilha"],REF_THEORY)
add("Teoria da Computação","Computabilidade","Máquinas de Turing e decidibilidade","Distinguir reconhecimento e decisão","Máquinas de Turing formalizam computação geral. Uma linguagem é decidível quando existe uma máquina que termina para toda entrada e responde corretamente; reconhecibilidade permite não terminar em certas entradas fora da linguagem.",["máquina de Turing","decidibilidade","reconhecível","computabilidade"],REF_THEORY)
add("Teoria da Computação","Complexidade","P, NP e redução","Analisar classes e reduções","P contém problemas decidíveis em tempo polinomial por algoritmos determinísticos. NP inclui problemas cujas soluções podem ser verificadas em tempo polinomial; reduções polinomiais ajudam a comparar dificuldade entre problemas.",["P","NP","NP-completo","redução polinomial"],REF_THEORY)

# Compiladores e Linguagens de Programação
REF_COMP = "AHO, A. V. et al. Compilers: Principles, Techniques, and Tools."
add("Compiladores e Linguagens","Compiladores","Análise léxica","Explicar tokenização de programas","Análise léxica transforma sequência de caracteres em tokens segundo padrões léxicos. Espaços e comentários podem ser descartados conforme a linguagem, enquanto lexemas são associados a classes de tokens.",["lexer","token","lexema","análise léxica"],REF_COMP)
add("Compiladores e Linguagens","Compiladores","Análise sintática","Analisar estrutura gramatical","Análise sintática verifica se a sequência de tokens pode ser derivada pela gramática e constrói uma representação estrutural, como árvore sintática ou AST, para fases posteriores.",["parser","AST","gramática","análise sintática"],REF_COMP)
add("Compiladores e Linguagens","Compiladores","Análise semântica e tipos","Detectar erros além da sintaxe","Análise semântica verifica propriedades não capturadas apenas pela gramática, como compatibilidade de tipos, escopos e declarações. Tabelas de símbolos mantêm informações sobre identificadores.",["análise semântica","tipos","tabela de símbolos","escopo"],REF_COMP)
add("Compiladores e Linguagens","Compiladores","Código intermediário e otimização","Explicar etapas de tradução","Representações intermediárias desacoplam partes do front-end e back-end. Otimizações procuram reduzir custo mantendo semântica, e geração de código mapeia a representação para instruções da arquitetura-alvo.",["IR","código intermediário","otimização","geração de código"],REF_COMP)
add("Compiladores e Linguagens","Programação","Tipagem estática e dinâmica","Comparar sistemas de tipos","Em tipagem estática, muitas verificações são realizadas antes da execução; em tipagem dinâmica, tipos e erros correspondentes podem ser tratados em tempo de execução. A escolha afeta ferramentas, flexibilidade e garantias.",["tipagem estática","tipagem dinâmica","tipo","runtime"],REF_COMP)

# Sistemas Distribuídos
REF_DIST = "TANENBAUM, A. S.; VAN STEEN, M. Distributed Systems."
add("Sistemas Distribuídos","Fundamentos","Modelos de sistemas distribuídos","Analisar ausência de memória e relógio globais","Sistemas distribuídos são compostos por processos em máquinas conectadas que coordenam ações por mensagens. A ausência de memória compartilhada global e incertezas de tempo e falhas tornam coordenação mais complexa.",["sistemas distribuídos","mensagens","falha","coordenação"],REF_DIST)
add("Sistemas Distribuídos","Tempo","Relógios lógicos de Lamport","Ordenar eventos distribuídos","Relógios lógicos de Lamport atribuem marcas que preservam a relação acontece-antes: se um evento causalmente precede outro, sua marca é menor. A recíproca não implica causalidade.",["Lamport","relógio lógico","happens-before","causalidade"],REF_DIST)
add("Sistemas Distribuídos","Replicação","Replicação e consistência","Analisar cópias de dados","Replicação aumenta disponibilidade e desempenho, mas exige definir como e quando cópias convergem. Modelos de consistência estabelecem quais valores operações concorrentes podem observar.",["replicação","consistência","réplica","convergência"],REF_DIST)
add("Sistemas Distribuídos","Consenso","Consenso sob falhas","Explicar acordo distribuído","Problemas de consenso exigem que processos corretos concordem sobre um valor apesar de certas falhas e atrasos. Protocolos práticos distinguem hipóteses de falha, temporização e quóruns.",["consenso","quórum","falha","Raft","Paxos"],REF_DIST)
add("Sistemas Distribuídos","Transações","Commit distribuído","Analisar atomicidade entre participantes","Two-Phase Commit coordena participantes para decidir commit ou abort de uma transação distribuída. O protocolo preserva atomicidade, mas pode bloquear sob determinadas falhas do coordenador.",["2PC","two-phase commit","transação distribuída","coordenador"],REF_DIST)
add("Sistemas Distribuídos","Arquitetura","Microsserviços e comunicação","Analisar decomposição de serviços","Microsserviços organizam uma aplicação como serviços implantáveis de forma independente com contratos explícitos. Benefícios de autonomia vêm acompanhados de desafios de rede, observabilidade, consistência e operação.",["microsserviços","API","observabilidade","serviço"],REF_DIST)

# IHC
REF_HCI = "NIELSEN, J. Usability Engineering; ISO 9241-210."
add("Interação Humano-Computador","Usabilidade","Eficácia, eficiência e satisfação","Avaliar usabilidade","Usabilidade considera se usuários alcançam objetivos com eficácia, eficiência e satisfação em um contexto de uso. Avaliação deve considerar usuários, tarefas, ambiente e métricas adequadas.",["usabilidade","eficácia","eficiência","satisfação"],REF_HCI)
add("Interação Humano-Computador","Avaliação","Avaliação heurística","Aplicar inspeção de interfaces","Avaliação heurística inspeciona uma interface segundo princípios de usabilidade para identificar problemas sem exigir um experimento completo com usuários. Problemas podem ser priorizados por gravidade.",["avaliação heurística","Nielsen","interface","usabilidade"],REF_HCI)
add("Interação Humano-Computador","Acessibilidade","Acessibilidade digital","Analisar barreiras de interação","Acessibilidade busca permitir uso por pessoas com diferentes capacidades e tecnologias assistivas. Estrutura semântica, navegação por teclado, contraste e alternativas textuais são exemplos de aspectos relevantes.",["acessibilidade","WCAG","teclado","contraste","tecnologia assistiva"],REF_HCI)
add("Interação Humano-Computador","Projeto","Design centrado no usuário","Relacionar pesquisa e projeto iterativo","Processos centrados no usuário investigam contexto, necessidades e tarefas, produzem soluções e avaliam iterativamente com evidências de uso para refinar o projeto.",["user-centered design","UCD","prototipação","avaliação"],REF_HCI)

# Matemática e Fundamentos
REF_MATH = "ROSEN, K. Discrete Mathematics and Its Applications."
add("Matemática para Computação","Lógica","Lógica proposicional","Aplicar equivalências e inferência","Proposições podem ser combinadas por conectivos e avaliadas por tabelas-verdade. Equivalências lógicas e regras de inferência permitem transformar fórmulas e verificar validade de argumentos.",["lógica proposicional","tabela verdade","implicação","equivalência"],REF_MATH)
add("Matemática para Computação","Conjuntos e Relações","Relações de equivalência e ordem","Classificar relações","Uma relação de equivalência é reflexiva, simétrica e transitiva e induz classes de equivalência. Ordens parciais são reflexivas, antissimétricas e transitivas.",["relação","equivalência","ordem parcial","transitividade"],REF_MATH)
add("Matemática para Computação","Combinatória","Princípios de contagem","Resolver problemas de contagem","Princípios aditivo e multiplicativo estruturam contagens. Permutações, arranjos e combinações dependem de ordem, repetição e seleção dos elementos envolvidos.",["combinatória","combinação","permutação","contagem"],REF_MATH)
add("Matemática para Computação","Probabilidade","Probabilidade condicional e Bayes","Aplicar condicionamento probabilístico","Probabilidade condicional atualiza a chance de um evento diante de informação conhecida. O teorema de Bayes relaciona probabilidades condicionais e probabilidades a priori para inverter o sentido de condicionamento.",["Bayes","probabilidade condicional","independência","probabilidade"],REF_MATH)
add("Matemática para Computação","Grafos","Conceitos básicos de grafos","Modelar relações por grafos","Grafos são formados por vértices e arestas e podem ser dirigidos ou não dirigidos. Caminhos, ciclos, graus e conectividade descrevem propriedades úteis na modelagem de redes e dependências.",["grafo","vértice","aresta","caminho","ciclo"],REF_MATH)

# Programação e Paradigmas
REF_PROG = "SEBESTA, R. Concepts of Programming Languages; documentação técnica das linguagens conforme contexto."
add("Programação","Orientação a Objetos","Encapsulamento, herança e polimorfismo","Analisar princípios orientados a objetos","Encapsulamento protege representação interna por interfaces; herança expressa relações de especialização quando apropriadas; polimorfismo permite tratar diferentes implementações por uma abstração comum.",["encapsulamento","herança","polimorfismo","OO"],REF_PROG)
add("Programação","Funções","Recursão e pilha de chamadas","Analisar execução recursiva","Funções recursivas resolvem problemas por chamadas sobre instâncias menores e precisam de condição de parada. Cada chamada normalmente mantém um registro de ativação na pilha até retornar.",["recursão","caso base","pilha de chamadas","função"],REF_PROG)
add("Programação","Concorrência","Concorrência e paralelismo","Distinguir execução concorrente e paralela","Concorrência trata a composição de atividades que progridem ao longo do tempo; paralelismo envolve execução simultânea efetiva. Dados compartilhados exigem coordenação para evitar condições de corrida.",["concorrência","paralelismo","race condition","sincronização"],REF_PROG)
add("Programação","Tratamento de Erros","Exceções e fluxo de erro","Projetar tratamento de falhas","Exceções separam fluxo normal de certas condições de erro e podem propagar informação até um tratador adequado. Capturas excessivamente genéricas podem ocultar falhas e dificultar diagnóstico.",["exceção","try","catch","erro"],REF_PROG)

# Computação, sociedade e ética
REF_ETH = "ACM Code of Ethics and Professional Conduct; Lei nº 13.709/2018 (LGPD)."
add("Computação e Sociedade","Ética","Responsabilidade profissional em computação","Analisar impactos e deveres profissionais","Decisões computacionais podem afetar segurança, privacidade, acesso e oportunidades. Prática responsável exige considerar consequências, competência técnica, transparência apropriada e respeito a direitos e normas aplicáveis.",["ética","responsabilidade profissional","impacto social","ACM"],REF_ETH)
add("Computação e Sociedade","Privacidade","Proteção de dados e LGPD","Relacionar tratamento de dados a princípios de proteção","Tratamento de dados pessoais deve observar finalidade, adequação, necessidade, segurança e outros princípios legais aplicáveis. Medidas técnicas e organizacionais devem ser proporcionais ao risco e ao contexto do tratamento.",["LGPD","dados pessoais","privacidade","tratamento de dados"],REF_ETH)

print(f"Chunks seed preparados: {len(chunks)}")

# Mescla sem apagar os 12 registros existentes.
existentes: list[dict] = []
if CORPUS.exists():
    for line in CORPUS.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            existentes.append(obj)

ids = {str(x.get("id")) for x in existentes if x.get("id")}
novos = [x for x in chunks if x["id"] not in ids]
final = existentes + novos
CORPUS.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in final) + "\n", encoding="utf-8")
print(f"Corpus: {len(existentes)} existentes + {len(novos)} novos = {len(final)} registros")

# ---------------------------------------------------------------------------
# 2) RAG v4: BM25 + expansão controlada + frases + fuzzy + metadados + top-k.
#    Continua recusando tema sem evidência no corpus.
# ---------------------------------------------------------------------------
rag_source = r'''"""RAG local híbrido, rastreável e reproduzível da HAILA.

v4: BM25 + frases + aliases + fuzzy lexical conservador + roteamento por área
+ agregação top-k. Não inventa referência: consulta sem suporte continua bloqueada.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .contracts import ReferenciaRAG

STOPWORDS = set("""
que para uma umas uns com dos das pelo pela entre sobre como qual quais este esta esse essa
sao seu sua seus suas analisar identificar compreender computacao especifico enade objetivo
avaliar explicar comparar diferenciar descrever distinguir funcao funcoes principal conceito
conceitos funcionamento exemplo exemplos aplicacao aplicacoes uso usos sistema sistemas dados
software estudante consegue partir cenário cenario situação situacao problema correto correta
melhor seguintes considerando relação relacao acordo deve podem possui possuiem
""".split())

ALIASES = {
    "condicao_corrida": ("condicao de corrida", "condicoes de corrida", "race condition", "race conditions"),
    "exclusao_mutua": ("exclusao mutua", "mutual exclusion"),
    "regiao_critica": ("regiao critica", "critical section", "secao critica"),
    "deadlock": ("deadlock", "impasse", "interbloqueio"),
    "memoria_virtual": ("memoria virtual", "virtual memory"),
    "paginacao": ("paginacao", "paging"),
    "falta_pagina": ("falta de pagina", "faltas de pagina", "page fault", "page faults"),
    "complexidade": ("complexidade", "complexity"),
    "pilha": ("pilha", "pilhas", "stack", "stacks"),
    "fila": ("fila", "filas", "queue", "queues"),
    "transacao": ("transacao", "transacoes", "transaction", "transactions"),
    "normalizacao": ("normalizacao", "normalization"),
    "teste_unitario": ("teste unitario", "testes unitarios", "unit test", "unit tests", "unit testing"),
    "teste_integracao": ("teste de integracao", "testes de integracao", "integration testing", "integration test"),
    "aprendizado_supervisionado": ("aprendizado supervisionado", "aprendizagem supervisionada", "supervised learning"),
    "aprendizado_nao_supervisionado": ("aprendizado nao supervisionado", "aprendizagem nao supervisionada", "unsupervised learning"),
    "overfitting": ("sobreajuste", "overfitting"),
    "microsservico": ("microsservico", "microsservicos", "microservice", "microservices"),
    "autenticacao": ("autenticacao", "authentication"),
    "autorizacao": ("autorizacao", "authorization"),
    "ipv4": ("ipv4", "ip v4", "internet protocol version 4"),
    "ipv6": ("ipv6", "ip v6", "internet protocol version 6"),
    "subrede": ("subrede", "sub-redes", "sub-rede", "subnet", "subnets", "subnetting"),
    "cidr": ("cidr", "classless inter-domain routing", "prefixo de rede", "prefixo ipv4"),
    "mascara_subrede": ("mascara de subrede", "mascara de sub-rede", "subnet mask"),
    "roteamento": ("roteamento", "routing", "encaminhamento ip"),
    "roteador": ("roteador", "roteadores", "router", "routers"),
    "rota_padrao": ("rota padrao", "default route", "gateway padrao", "gateway padrão"),
    "vetor_distancia": ("vetor de distancia", "distance vector"),
    "estado_enlace": ("estado de enlace", "link state"),
    "endereco_mac": ("endereco mac", "mac address"),
    "dns": ("dns", "domain name system"),
    "http": ("http", "hypertext transfer protocol"),
    "https": ("https",),
    "tcp": ("tcp", "transmission control protocol"),
    "udp": ("udp", "user datagram protocol"),
    "banco_dados": ("banco de dados", "database", "dbms", "sgbd"),
    "engenharia_requisitos": ("engenharia de requisitos", "requirements engineering"),
    "requisito_nao_funcional": ("requisito nao funcional", "requisitos nao funcionais", "non functional requirement", "nfr"),
    "requisito_funcional": ("requisito funcional", "requisitos funcionais", "functional requirement"),
    "arvore_decisao": ("arvore de decisao", "decision tree"),
    "rede_neural": ("rede neural", "redes neurais", "neural network", "neural networks"),
    "busca_largura": ("busca em largura", "breadth first search", "bfs"),
    "busca_profundidade": ("busca em profundidade", "depth first search", "dfs"),
}

AREA_HINTS = {
    "Redes de Computadores": {"ipv4","ipv6","subrede","cidr","mascara_subrede","roteamento","roteador","rota_padrao","vetor_distancia","estado_enlace","endereco_mac","dns","http","https","tcp","udp","ethernet","icmp","dhcp","nat","bgp","ospf","rip","wifi"},
    "Banco de Dados": {"banco_dados","transacao","normalizacao","sql","acid","join","indice","serializabilidade","isolamento","relacional"},
    "Engenharia de Software": {"engenharia_requisitos","requisito_nao_funcional","requisito_funcional","scrum","uml","teste_unitario","teste_integracao","arquitetura","manutencao","rastreabilidade"},
    "Sistemas Operacionais": {"processo","thread","deadlock","memoria_virtual","paginacao","falta_pagina","escalonamento","semaforo","mutex","dma"},
    "Algoritmos e Estruturas de Dados": {"complexidade","pilha","fila","grafo","dijkstra","floyd","kruskal","prim","heap","hash","quicksort","mergesort","bfs","dfs","busca_largura","busca_profundidade"},
    "Inteligência Artificial": {"aprendizado_supervisionado","aprendizado_nao_supervisionado","overfitting","arvore_decisao","rede_neural","heuristica","minimax","kmeans","recall","precision"},
    "Segurança da Informação": {"criptografia","hash","firewall","autenticacao","autorizacao","xss","injecao","tls","pki","certificado"},
    "Arquitetura e Organização de Computadores": {"cache","pipeline","alu","registrador","multicore","complemento","datapath"},
    "Teoria da Computação": {"automato","turing","decidibilidade","np","linguagem_regular","gramatica"},
    "Compiladores e Linguagens": {"compilador","lexer","parser","ast","token","semantica","tipagem"},
    "Sistemas Distribuídos": {"distribuido","lamport","consenso","replicacao","quorum","2pc","microsservico"},
    "Interação Humano-Computador": {"usabilidade","acessibilidade","heuristica","interface","prototipo"},
    "Matemática para Computação": {"probabilidade","bayes","combinatoria","logica","relacao","grafo"},
}


def _ascii(value: Any) -> str:
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()


def _canonical_text(value: Any) -> str:
    text = _ascii(value)
    pairs = [(alias, canon) for canon, aliases in ALIASES.items() for alias in aliases]
    for alias, canon in sorted(pairs, key=lambda x: -len(x[0])):
        text = re.sub(r"(?<!\w)" + re.escape(_ascii(alias)) + r"(?!\w)", canon, text)
    return re.sub(r"\s+", " ", text).strip()


def _terms(value: Any) -> list[str]:
    text = _canonical_text(value)
    raw = re.findall(r"[a-z0-9_]+", text)
    uni = [t for t in raw if (len(t) > 2 or t in {"ip","ia","p","np"}) and t not in STOPWORDS]
    # Bigrams preserve local meaning without requiring an embedding model.
    bi = [f"{a}__{b}" for a, b in zip(uni, uni[1:]) if a not in STOPWORDS and b not in STOPWORDS]
    return uni + bi


def _token_set(value: Any) -> set[str]:
    return set(_terms(value))


def _normalize_record(raw: dict[str, Any], line_no: int) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    if raw.get("quarentena") or str(raw.get("status", "")).upper() in {"REJEITADO","QUARENTENA","REJEITAR_EXTRACAO"}:
        return None
    q = raw.get("questao") if isinstance(raw.get("questao"), dict) else raw
    text = q.get("texto_base") or q.get("enunciado") or raw.get("texto")
    ident = raw.get("id") or raw.get("questao_id") or q.get("id")
    if not ident or not isinstance(text, str) or len(text.strip()) < 40:
        return None
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]", text):
        return None
    if (raw.get("tem_imagem") or q.get("tem_imagem")) and not (raw.get("recurso_visual") or q.get("recurso_visual")):
        return None
    kw = raw.get("palavras_chave") or q.get("palavras_chave") or []
    if isinstance(kw, str):
        kw = [kw]
    return {
        "id": str(ident), "texto": text.strip(),
        "ano": raw.get("ano") or q.get("ano"),
        "exame": raw.get("exame") or q.get("exame") or "ACERVO_LOCAL",
        "curso": raw.get("curso") or q.get("curso"),
        "componente": raw.get("componente") or q.get("componente"),
        "area": raw.get("area") or q.get("area"),
        "subarea": raw.get("subarea") or q.get("subarea"),
        "habilidade": raw.get("habilidade") or q.get("habilidade"),
        "objeto_conhecimento": raw.get("objeto_conhecimento") or q.get("objeto_conhecimento"),
        "palavras_chave": kw,
        "referencia": raw.get("referencia") or q.get("referencia"),
        "fonte_tipo": raw.get("fonte_tipo") or q.get("fonte_tipo"),
        "origem": raw.get("origem") or q.get("origem"),
        "linha": line_no,
    }


def _infer_area(tokens: set[str]) -> str | None:
    scores = [(len(tokens & hints), area) for area, hints in AREA_HINTS.items()]
    score, area = max(scores, default=(0, None))
    return area if score > 0 else None


def _fuzzy_hits(query_uni: set[str], doc_uni: set[str]) -> list[tuple[str,str,float]]:
    hits = []
    for q in query_uni:
        if len(q) < 5 or "__" in q or q in doc_uni:
            continue
        best = None
        for d in doc_uni:
            if len(d) < 5 or "__" in d or abs(len(q)-len(d)) > 3 or q[:2] != d[:2]:
                continue
            s = SequenceMatcher(None, q, d).ratio()
            if s >= .88 and (best is None or s > best[2]):
                best = (q, d, s)
        if best:
            hits.append(best)
    return hits


class CorpusJsonlRAG:
    """Recuperação híbrida local com agregação de evidências top-k."""

    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)
        if not self.caminho.is_file():
            raise RuntimeError(f"corpus RAG não encontrado: {self.caminho}")
        records = []
        with self.caminho.open(encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    rec = _normalize_record(json.loads(line), n)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"JSON inválido no corpus RAG, linha {n}") from exc
                if rec:
                    records.append(rec)
        if not records:
            raise RuntimeError("corpus RAG não contém referências utilizáveis")

        unique, texts = {}, set()
        for r in records:
            normalized = re.sub(r"\s+", " ", _ascii(r["texto"])).strip()
            if r["id"] not in unique and normalized not in texts:
                unique[r["id"]] = r
                texts.add(normalized)
        self.registros = list(unique.values())

        self._doc_texts = []
        self._docs = []
        self._uni = []
        for r in self.registros:
            joined = " ".join(str(r.get(k) or "") for k in ("area","subarea","habilidade","objeto_conhecimento","palavras_chave","texto"))
            self._doc_texts.append(_canonical_text(joined))
            ts = _terms(joined)
            self._docs.append(Counter(ts))
            self._uni.append({x for x in ts if "__" not in x})

        # document frequency, not total term frequency
        self._df = Counter(t for doc in self._docs for t in doc.keys())
        self._avg_len = sum(sum(d.values()) for d in self._docs) / len(self._docs)
        self.top_k = max(1, min(5, int(os.getenv("HAILA_RAG_TOP_K", "3"))))
        self.min_score = float(os.getenv("HAILA_RAG_MIN_SCORE", "1.10"))
        self.min_focus = float(os.getenv("HAILA_RAG_MIN_FOCUS_COVERAGE", "0.30"))

    def __len__(self) -> int:
        return len(self.registros)

    def _score(self, q_terms, q_uni, focus_uni, q_area, r, doc, doc_uni, doc_text):
        common = set(q_terms) & doc.keys()
        fuzzy = _fuzzy_hits(q_uni, doc_uni)
        focus_common = focus_uni & doc_uni
        focus_cov = len(focus_common) / max(1, len(focus_uni))

        bm25 = 0.0
        dl = max(1, sum(doc.values()))
        for t in common:
            df = self._df[t]
            idf = math.log(1 + (len(self.registros) - df + .5) / (df + .5))
            tf = doc[t]
            bm25 += idf * (tf * 2.2) / (tf + 1.2 * (.25 + .75 * dl / self._avg_len))

        phrase = 0.0
        obj = _canonical_text(r.get("objeto_conhecimento"))
        for token in focus_uni:
            if token in doc_uni:
                phrase += .45
        if obj and len(obj) >= 5 and (obj in _canonical_text(" ".join(q_uni)) or any(x in doc_text for x in focus_uni)):
            phrase += .35

        area_bonus = 0.0
        r_area = _ascii(r.get("area"))
        if q_area and r_area:
            if _ascii(q_area) == r_area:
                area_bonus = 2.25
            elif q_area.casefold().split()[0] in r_area:
                area_bonus = .75

        fuzzy_bonus = sum(.35 * s for _,_,s in fuzzy[:4])
        score = bm25 + phrase + area_bonus + fuzzy_bonus
        evidence = bool(common or fuzzy)
        if focus_uni:
            evidence = evidence and (focus_cov >= self.min_focus or len(focus_common) >= 2 or area_bonus >= 2.0)
        return score, sorted(common), focus_cov, fuzzy, evidence

    def __call__(self, specification: dict[str, Any]) -> ReferenciaRAG:
        query = " ".join(str(specification.get(k) or "") for k in ("objetivo_pedagogico","competencia","habilidade","objeto_conhecimento"))
        q_terms = _terms(query)
        q_uni = {x for x in q_terms if "__" not in x}
        focus_terms = _terms(specification.get("objeto_conhecimento"))
        focus_uni = {x for x in focus_terms if "__" not in x}
        q_area = _infer_area(q_uni | focus_uni)

        ranking = []
        for r, doc, doc_uni, doc_text in zip(self.registros, self._docs, self._uni, self._doc_texts):
            if any(specification.get(k) and r.get(k) and _ascii(specification[k]) != _ascii(r[k]) for k in ("curso","componente")):
                continue
            exame = str(r.get("exame") or "")
            if specification.get("exame") and exame in {"ENADE","ENEM"} and exame != specification["exame"]:
                continue
            score, common, focus_cov, fuzzy, evidence = self._score(q_terms, q_uni, focus_uni, q_area, r, doc, doc_uni, doc_text)
            if evidence and score >= self.min_score:
                ranking.append({"score":score,"registro":r,"comuns":common,"focus":focus_cov,"fuzzy":fuzzy})

        if not ranking:
            extra = f" Área inferida: {q_area}." if q_area else ""
            raise ValueError("RAG sem referência relevante para o objetivo solicitado; amplie o acervo ou especifique o tema." + extra)

        ranking.sort(key=lambda x: (-x["score"], x["registro"]["id"]))
        best = ranking[0]["score"]

        # Top-k mantém somente fontes suficientemente próximas da principal e, quando
        # a área é inferida, evita misturar áreas sem necessidade.
        selected = []
        for item in ranking:
            if len(selected) >= self.top_k:
                break
            if item["score"] < max(self.min_score, .42 * best):
                continue
            if q_area and selected:
                area = _ascii(item["registro"].get("area"))
                if area and area != _ascii(q_area):
                    continue
            selected.append(item)
        if not selected:
            selected = [ranking[0]]

        primary = selected[0]["registro"]
        blocks = []
        sources = []
        for i, item in enumerate(selected, 1):
            r = item["registro"]
            header = f"[Fonte {i}: {r['id']} | {r.get('area') or 'sem área'} | {r.get('objeto_conhecimento') or 'sem objeto'}]"
            blocks.append(header + "\n" + r["texto"])
            sources.append({
                "id": r["id"], "area": r.get("area"), "subarea": r.get("subarea"),
                "objeto_conhecimento": r.get("objeto_conhecimento"), "referencia": r.get("referencia"),
                "score": round(item["score"], 6), "focus_coverage": round(item["focus"], 3),
                "termos_recuperados": item["comuns"],
                "fuzzy": [{"consulta":a,"documento":b,"score":round(s,3)} for a,b,s in item["fuzzy"]],
            })

        metadata = {k:v for k,v in primary.items() if k not in {"id","texto","ano","exame"}}
        metadata.update({
            "corpus": str(self.caminho),
            "retrieval": "hybrid-bm25-phrase-fuzzy-metadata-v4",
            "area_inferida": q_area,
            "top_k": len(selected),
            "fontes_ids": [x["id"] for x in sources],
            "fontes": sources,
            "candidatas_relevantes": len(ranking),
            "consulta_normalizada": sorted(q_uni),
            "ranking": [{"id":x["registro"]["id"],"score":round(x["score"],6),"area":x["registro"].get("area")} for x in ranking[:8]],
            "query_fingerprint": hashlib.sha256(query.encode()).hexdigest()[:16],
        })
        return ReferenciaRAG(id=primary["id"], texto="\n\n".join(blocks), exame=primary["exame"], ano=primary["ano"], metadados=metadata)


def rag_from_env() -> CorpusJsonlRAG:
    project_root = Path(__file__).resolve().parents[2]
    default = Path(__file__).resolve().parents[1] / "fontes_rag.jsonl"
    path = Path(os.getenv("HAILA_RAG_CORPUS", str(default))).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return CorpusJsonlRAG(path.resolve())
'''
RAG_PY.write_text(rag_source, encoding="utf-8")
print("RAG v4 instalado em", RAG_PY)

# ---------------------------------------------------------------------------
# 3) Configuração conservadora. Não força resposta sem evidência.
# ---------------------------------------------------------------------------
env = ROOT / ".env"
if env.exists():
    text = env.read_text(encoding="utf-8")
else:
    text = ""
updates = {
    "HAILA_RAG_TOP_K": "3",
    "HAILA_RAG_MIN_SCORE": "1.10",
    "HAILA_RAG_MIN_FOCUS_COVERAGE": "0.30",
}
lines = text.splitlines()
out = []
seen = set()
for line in lines:
    if "=" in line and not line.lstrip().startswith("#"):
        key = line.split("=",1)[0].strip()
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
            continue
    out.append(line)
for k,v in updates.items():
    if k not in seen:
        out.append(f"{k}={v}")
env.write_text("\n".join(out).rstrip()+"\n", encoding="utf-8")

# ---------------------------------------------------------------------------
# 4) Testes específicos do novo RAG.
# ---------------------------------------------------------------------------
TESTS.mkdir(parents=True, exist_ok=True)
test_file = TESTS / "test_rag_v4_coverage.py"
test_file.write_text(r'''import json
import pytest
from haila.rag import CorpusJsonlRAG


def _seed(tmp_path):
    p = tmp_path / "c.jsonl"
    rows = [
        {"id":"ipv4","texto_base":"IPv4 usa endereços de 32 bits. CIDR e máscara de sub-rede definem o prefixo e permitem subnetting.","area":"Redes de Computadores","objeto_conhecimento":"IPv4, sub-redes e CIDR","palavras_chave":["IPv4","subnetting","CIDR"],"exame":"ACERVO_CONCEITUAL_HAILA"},
        {"id":"tcp","texto_base":"TCP oferece entrega confiável e ordenada e usa confirmações e retransmissões.","area":"Redes de Computadores","objeto_conhecimento":"TCP","palavras_chave":["TCP"],"exame":"ACERVO_CONCEITUAL_HAILA"},
        {"id":"acid","texto_base":"Transações de bancos de dados seguem propriedades como atomicidade, isolamento e durabilidade.","area":"Banco de Dados","objeto_conhecimento":"Transações ACID","palavras_chave":["ACID"],"exame":"ACERVO_CONCEITUAL_HAILA"},
    ]
    p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows)+"\n", encoding="utf-8")
    return p


def test_recupera_ipv4_subnetting_por_alias(tmp_path):
    rag = CorpusJsonlRAG(_seed(tmp_path))
    ref = rag({"curso":"Computação","componente":"ESPECIFICO","exame":"ENADE","objeto_conhecimento":"endereçamento IPv4 e subnetting","objetivo_pedagogico":"calcular sub-redes usando máscara e CIDR"})
    assert ref.id == "ipv4"
    assert "ipv4" in ref.texto.lower()
    assert ref.metadados["retrieval"].endswith("v4")


def test_top_k_nao_mistura_banco_com_redes(tmp_path):
    rag = CorpusJsonlRAG(_seed(tmp_path))
    ref = rag({"curso":"Computação","componente":"ESPECIFICO","exame":"ENADE","objeto_conhecimento":"TCP","objetivo_pedagogico":"analisar confiabilidade do TCP"})
    assert all(x["area"] == "Redes de Computadores" for x in ref.metadados["fontes"])


def test_tema_ausente_continua_bloqueado(tmp_path):
    rag = CorpusJsonlRAG(_seed(tmp_path))
    with pytest.raises(ValueError, match="sem referência relevante"):
        rag({"curso":"Computação","componente":"ESPECIFICO","exame":"ENADE","objeto_conhecimento":"Computação quântica","objetivo_pedagogico":"analisar correção de erros quânticos"})
''', encoding="utf-8")
print("Teste criado:", test_file)

# ---------------------------------------------------------------------------
# 5) Auditoria de cobertura do corpus final.
# ---------------------------------------------------------------------------
area_counter = Counter(str(x.get("area") or "Não informado") for x in final)
print("\nCobertura por área:")
for area, n in area_counter.most_common():
    print(f"  {area:42} {n:3d}")

network_terms = ["ipv4","ipv6","cidr","sub-rede","roteamento","tcp","udp","dns","http","nat","dhcp","ospf","bgp"]
blob = "\n".join(json.dumps(x, ensure_ascii=False).casefold() for x in final)
print("\nCobertura rápida de Redes:")
for term in network_terms:
    print(f"  {term:12} {blob.count(term.casefold()):3d} ocorrência(s)")

# ---------------------------------------------------------------------------
# 6) Validação local.
# ---------------------------------------------------------------------------
py = ROOT / ".venv" / "bin" / "python"
python = str(py if py.exists() else Path(sys.executable))
print("\nValidando sintaxe...")
subprocess.run([python, "-m", "py_compile", str(RAG_PY)], check=True, cwd=ROOT)
print("OK")

print("Executando testes do backend...")
proc = subprocess.run([python, "-m", "pytest", "-q"], cwd=BACKEND)
if proc.returncode != 0:
    print("\nATENÇÃO: houve falha em testes. O backup está em:", BACKUP)
    raise SystemExit(proc.returncode)

print("\n" + "="*78)
print("UPGRADE CONCLUÍDO")
print("="*78)
print("Corpus:", CORPUS)
print("Registros:", len(final))
print("RAG:", RAG_PY)
print("Backup:", BACKUP)
print("Config: HAILA_RAG_TOP_K=3, MIN_SCORE=1.10, MIN_FOCUS_COVERAGE=0.30")
print("\nReinicie o backend para carregar o novo RAG.")
