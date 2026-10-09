from __future__ import annotations

import ast
import json
import os
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Protocol

from .contracts import DistratorGerado, NucleoQuestao, ReferenciaRAG
from .slm_config import adapter_is_complete, allow_base_qwen, resolve_adapter_path, slm_backend, slm_base_model


class RecuperadorRAG(Protocol):
    def __call__(self, specification: dict[str, Any]) -> ReferenciaRAG: ...


class SpecificationRAG:
    """Adapter inicial: recebe uma referência recuperada externamente na solicitação."""
    def __call__(self, specification):
        ref = specification.get("referencia") or {}
        if not ref.get("id") or not ref.get("texto"):
            raise RuntimeError("solicitação não contém referencia.id e referencia.texto")
        return ReferenciaRAG(id=str(ref["id"]), texto=str(ref["texto"]), exame="ENADE",
                             ano=ref.get("ano"), metadados=ref.get("metadados") or {})


class GeradorNucleo(Protocol):
    model: str
    def __call__(self, specification: dict[str, Any], referencia: ReferenciaRAG,
                 feedback: list[dict[str, Any]]) -> tuple[NucleoQuestao, dict[str, Any]]: ...


class GeradorDistratores(Protocol):
    model: str
    def __call__(self, nucleo: NucleoQuestao, feedback: list[dict[str, Any]]) -> tuple[list[DistratorGerado], dict[str, Any]]: ...


SYSTEM_QUALITY_BASE = """Crie uma questão objetiva inédita de Computação, alinhada ao ENADE e à especificação.
Use a referência somente como fundamento conceitual. Exija raciocínio, mantenha uma
única resposta defensável e sustente-a na explicação. Delimite produto, API e modelo
de execução quando forem necessários. Não use comportamento indefinido. Formule o
comando afirmativamente, sem termos vagos ou absolutos. Não repita no enunciado a
expressão que entrega o gabarito. Respeite o objeto de conhecimento e responda somente
JSON válido."""


SYSTEM_NUCLEO = SYSTEM_QUALITY_BASE + """
Gere somente o núcleo da questão: enunciado, resposta_correta concisa,
explicacao, competencia, habilidade, objeto_conhecimento, tem_imagem
e recurso_visual.

REGRAS OBRIGATÓRIAS PARA O NÚCLEO:

1. NÃO gere alternativas. Não coloque A), B), C), D) ou E) dentro
   do enunciado. As alternativas serão produzidas posteriormente
   por outro componente.

2. NÃO formule perguntas binárias como:
   "funcional ou não funcional",
   "verdadeiro ou falso",
   "sim ou não",
   ou qualquer comando que restrinja a resposta a somente duas classes.

3. A resposta correta deve ser um conceito ou afirmação concisa e
   NÃO deve aparecer literalmente no enunciado.

4. O cenário deve permitir pelo menos quatro erros conceituais
   plausíveis, para que posteriormente sejam produzidos quatro
   distratores distintos.

5. Quando o tema envolver requisitos funcionais e não funcionais,
   descreva UM único requisito ou situação e pergunte qual
   classificação, propriedade ou característica melhor o descreve.
   Não apresente uma lista de requisitos candidatos no enunciado.

6. Não inclua no mesmo cenário dois elementos que possam satisfazer
   corretamente o comando.

7. Não use grafia artificial, erros ortográficos ou palavras inventadas.

8. Não antecipe as alternativas no enunciado.

Ao comparar TCP e UDP, restrinja explicitamente a comparação aos dois
protocolos e use como resposta uma afirmação comparativa sobre ambos,
sem copiá-la no enunciado.

Se o item reunir função e desempenho, pergunte separadamente pelo
aspecto pretendido.

REGRA DE COMANDO EXPLÍCITO:
Todo enunciado deve terminar com uma pergunta ou tarefa clara ao estudante.
Não entregue apenas a descrição de um cenário.

Quando um cenário mencionar uma funcionalidade e também um atributo de
qualidade, o comando deve indicar explicitamente qual elemento deve ser
avaliado. Por exemplo, em uma questão sobre tempo de resposta, pergunte
pela classificação da restrição de desempenho, e não pela classificação
ambígua do cenário inteiro.

REGRA DE FOCO SEMÂNTICO V13:
Cada item deve avaliar UMA decisão principal. Não combine, no mesmo gabarito,
uma máscara/prefixo de sub-rede com uma técnica de roteamento, protocolo,
algoritmo ou outra decisão independente.

Em questões de subnetting com divisão em partes iguais, calcule o prefixo antes
de escrever resposta_correta e explicacao. Exemplo: dividir um /24 em quatro
sub-redes iguais exige emprestar 2 bits, resultando em /26.

Em Engenharia de Requisitos, mantenha o nível taxonômico consistente. Se o
comando pede classificação geral, use "Requisito funcional" ou "Requisito não
funcional". Se pede o tipo de atributo de qualidade, use categorias específicas,
como "Requisito de desempenho", "Requisito de segurança" ou equivalentes.

Responda somente JSON válido.
"""


INSTRUCAO_DISTRACTORES = (
    "Gere exatamente 4 distratores plausiveis, distintos entre si e "
    "diferentes da resposta correta. Responda somente JSON valido."
)

SYSTEM_DISTRACTORES_QWEN = (
    "Você gera distratores para questões educacionais em português. "
    "Produza exatamente quatro alternativas incorretas, plausíveis, relevantes, "
    "gramaticalmente corretas e do mesmo tipo conceitual e nível de especificidade "
    "do gabarito. Cada alternativa deve representar uma confusão real de estudante "
    "sobre o conceito cobrado. Evite recipientes ou categorias genéricas como "
    "'arquivo', 'sistema', 'banco de dados' ou 'lista' quando o gabarito nomeia uma "
    "estrutura, protocolo, propriedade ou mecanismo específico. Não copie, não "
    "parafraseie e não inclua o gabarito. Não invente palavras. Nunca devolva "
    "placeholders como <NAME>, traduções para outro idioma ou palavras soltas "
    "sem função de alternativa. Se o gabarito é uma propriedade, protocolo, "
    "estrutura, classe ou paradigma, todos os distratores devem pertencer à "
    "mesma categoria. "
    "Mantenha as quatro alternativas com extensão e estrutura gramatical próximas "
    "às da resposta correta, para que o gabarito não se destaque pelo tamanho. "
    "Responda exclusivamente com JSON válido no formato "
    '{"distratores":["D1","D2","D3","D4"]}.'
)


def resumir_feedback_distratores(red_flags):
    """Extrai somente alternativas citadas pelo auditor para orientar a nova amostra."""
    rejeitados = []
    vistos = set()
    for flag in red_flags or []:
        evidencia = str(flag.get("evidencia") or flag.get("evidence") or "")
        citados = re.findall(r'["\u201c]([^"\u201d]{2,160})["\u201d]', evidencia)
        if isinstance(flag.get("alternativa_rejeitada"), str):
            citados.insert(0, flag["alternativa_rejeitada"])
        for texto in citados:
            texto = re.sub(r"\s+", " ", texto).strip()
            chave = texto.casefold()
            if chave not in vistos:
                vistos.add(chave)
                rejeitados.append(texto)
    return rejeitados[:8]


def chave_semantica_curta(texto):
    """Chave conservadora para impedir cópia literal do gabarito na origem."""
    base = unicodedata.normalize("NFKD", str(texto or "").casefold())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"\W+", "", base)



def _token_base(token: str) -> str:
    base = unicodedata.normalize("NFKD", str(token).casefold())
    base = "".join(
        c for c in base
        if not unicodedata.combining(c)
    )
    return re.sub(r"[^a-z0-9]", "", base)


def _tokens_originais(texto: str) -> list[str]:
    return re.findall(
        r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]*",
        str(texto),
    )


def motivo_distrator_lexicalmente_suspeito(
    nucleo,
    candidato: str,
) -> str | None:
    """
    Detecta corrupção lexical conservadora.

    Não tenta atuar como corretor ortográfico geral.
    Procura principalmente palavras que parecem versões
    deformadas de termos já existentes no enunciado/gabarito.
    """

    origem = (
        str(nucleo.enunciado)
        + " "
        + str(nucleo.resposta_correta)
    )

    tokens_origem = _tokens_originais(origem)
    tokens_candidato = _tokens_originais(candidato)

    mapa_origem = {}

    for token in tokens_origem:
        base = _token_base(token)

        if len(base) >= 4:
            mapa_origem.setdefault(base, set()).add(
                token.casefold()
            )

    bases_origem = list(mapa_origem)

    for token in tokens_candidato:
        base = _token_base(token)

        if len(base) < 5:
            continue

        # Ex.: "Requisítos" x "Requisitos":
        # mesma palavra após retirar acento, mas forma escrita
        # diferente da que aparece na questão.
        if base in mapa_origem:
            formas = mapa_origem[base]

            if (
                token.casefold() not in formas
                and any(
                    _token_base(forma) == base
                    for forma in formas
                )
            ):
                return (
                    f'forma ortográfica suspeita "{token}" '
                    f'para termo existente na questão'
                )

            continue

        # Ex.: Permitidr/permitir, estudants/estudantes,
        # criptoagrar/criptografar, requisitórios/requisitos.
        for original in bases_origem:
            if len(original) < 5:
                continue

            if _flexao_simples(base, original):
                continue

            if base[:3] != original[:3]:
                continue

            if abs(len(base) - len(original)) > 3:
                continue

            similaridade = SequenceMatcher(
                None,
                base,
                original,
            ).ratio()

            if similaridade >= 0.86:
                return (
                    f'possível corrupção lexical "{token}" '
                    f'(similaridade={similaridade:.2f} '
                    f'com "{original}")'
                )

    return None


def criar_prompt_distratores(enunciado, resposta, red_flags=None):
    """Prompt canônico compartilhado pelo fine-tuning e pela inferência local."""
    correcao = ""
    if red_flags:
        correcao = "\n\n### Corrija estes problemas:\n" + json.dumps(
            red_flags, ensure_ascii=False
        )
    return (
        f"### Instrucao:\n{INSTRUCAO_DISTRACTORES}\n\n"
        f"### Questao:\n{str(enunciado).strip()}\n\n"
        f"### Resposta correta:\n{str(resposta).strip()}\n\n"
        f"{correcao}\n\n### Saida:\n"
    )


class EnadeStemGenerator:
    def __init__(self, caller: Callable[[str, str], str], model: str = "desconhecido"):
        self.caller, self.model = caller, model

    def __call__(self, specification, referencia, feedback):
        reparo_prioritario = ""
        codigos = {str(item.get("codigo") or "") for item in feedback or []}

        # HAILA_PATCH_NUCLEO_20261007
        if codigos & {
            "espaco_de_respostas_binario",
            "gabarito_repetido_no_enunciado",
            "alternativas_embutidas_no_nucleo",
            "multiplos_candidatos_ao_gabarito",
        }:
            reparo_prioritario += (
                "CORREÇÃO OBRIGATÓRIA DO NÚCLEO: "
                "não repita a estrutura da tentativa anterior. "
                "Não use pergunta binária; não escreva 'funcional ou não funcional'; "
                "não coloque alternativas A), B), C), D) ou E) no enunciado; "
                "não inclua a resposta correta literalmente no enunciado. "
                "Descreva apenas UM caso e formule uma pergunta que permita "
                "cinco alternativas conceitualmente distintas. "
                "A resposta_correta deve ser curta e conceitual. "
            )

        if "iwf_repeticao_entrega_gabarito" in codigos:
            reparo_prioritario += (
                "Evite repetir no enunciado palavras que apareçam exclusivamente "
                "na resposta correta e possam funcionar como pista lexical. "
            )

        if "questao_multiconceito" in codigos:
            reparo_prioritario += (
                "CORREÇÃO OBRIGATÓRIA: avalie apenas UMA decisão. "
                "Se o item for de subnetting, pergunte somente pela máscara/prefixo. "
                "Não combine subnetting com roteamento no mesmo gabarito. "
            )

        if "gabarito_ipv4_inconsistente" in codigos:
            reparo_prioritario += (
                "CORREÇÃO OBRIGATÓRIA: refaça o cálculo de subnetting antes de "
                "escrever o gabarito e confira a explicação matematicamente. "
            )

        if "iwf_termo_absoluto" in codigos:
            reparo_prioritario += (
                "Reformule o cenário evitando termos absolutos desnecessários "
                "como sempre, nunca, todos e nenhum. "
            )

        if "selecao_de_protocolo_potencialmente_ambigua" in codigos:
            reparo_prioritario += (
                "CORREÇÃO OBRIGATÓRIA: não pergunte 'qual protocolo' e não use apenas "
                "TCP ou UDP como resposta. Pergunte: 'Considerando exclusivamente TCP "
                "e UDP, qual comparação descreve corretamente os serviços oferecidos?'. "
                "A resposta deve comparar ambos, por exemplo: 'TCP oferece entrega "
                "confiável e ordenada; UDP reduz a sobrecarga sem oferecer essas "
                "garantias'. Não repita a resposta no enunciado."
            )
        payload = {
            "solicitacao": specification,
            "referencia": referencia.to_dict(),
            "corrija": feedback,
            "reparo_prioritario": reparo_prioritario,
            "schema": {"enunciado": "string", "resposta_correta": "string", "explicacao": "string",
                       "competencia": "string", "habilidade": "string", "objeto_conhecimento": "string",
                       "tem_imagem": False, "recurso_visual": None},
        }
        pedido = json.dumps(payload, ensure_ascii=False)
        if reparo_prioritario:
            pedido = reparo_prioritario + "\n\n" + pedido
        data = json.loads(self.caller(SYSTEM_NUCLEO, pedido))
        token_usage = getattr(self.caller, "last_usage", None)
        if "dependencia_visual" in data:
            dependencia = data.pop("dependencia_visual")
            if isinstance(dependencia, dict):
                data.setdefault("tem_imagem", bool(dependencia.get("necessaria") or dependencia.get("tem_imagem")))
                data.setdefault("recurso_visual", dependencia.get("recurso") or dependencia.get("descricao"))
            elif isinstance(dependencia, bool):
                data.setdefault("tem_imagem", dependencia); data.setdefault("recurso_visual", None)
            elif dependencia:
                data.setdefault("tem_imagem", True); data.setdefault("recurso_visual", str(dependencia))
            else:
                data.setdefault("tem_imagem", False); data.setdefault("recurso_visual", None)
        proibidos = {"alternativas", "distratores", "correta"} & data.keys()
        if proibidos:
            raise ValueError(f"LLM violou o contrato do núcleo: {sorted(proibidos)}")
        provenance = {"modelo": self.model, "prompt_version": "enade-stem-1.2.0"}
        if token_usage: provenance["token_usage_remote"] = dict(token_usage)
        return NucleoQuestao(**data), provenance


class TinyLlamaLoraDistractorGenerator:
    """Adapter real e lazy para o TinyLlama + LoRA treinado para a HAILA."""
    def __init__(self, adapter_path: str | Path, base_model: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"):
        self.adapter_path, self.base_model = Path(adapter_path), base_model
        self.model = f"{base_model}+LoRA:{self.adapter_path.name}"
        self._pipeline = None

    def _load(self):
        if not self.adapter_path.exists():
            raise RuntimeError(f"adapter SLM não encontrado: {self.adapter_path}")
        try:
            from peft import PeftModel
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
        except ImportError as exc:
            raise RuntimeError("integração SLM requer transformers e peft") from exc
        tokenizer = AutoTokenizer.from_pretrained(str(self.adapter_path))
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        base = AutoModelForCausalLM.from_pretrained(
            self.base_model, torch_dtype=torch.float32, low_cpu_mem_usage=True
        )
        model = PeftModel.from_pretrained(base, str(self.adapter_path))
        model.eval()
        self._pipeline = pipeline("text-generation", model=model, tokenizer=tokenizer)

    def __call__(self, nucleo, feedback):
        if self._pipeline is None: self._load()
        # O LoRA foi ajustado com o prompt canônico, sem mensagens de reparo.
        # As red flags servem para rejeitar/amostrar novamente, não para mudar
        # a distribuição de entrada do modelo pequeno.
        prompt = criar_prompt_distratores(
            nucleo.enunciado,
            nucleo.resposta_correta,
            None,
        )
        raw = self._pipeline(
            prompt,
            max_new_tokens=int(os.getenv("HAILA_SLM_MAX_NEW_TOKENS", "512")),
            do_sample=True,
            temperature=float(os.getenv("HAILA_SLM_TEMPERATURE", "0.3")),
            top_p=float(os.getenv("HAILA_SLM_TOP_P", "0.85")),
            repetition_penalty=float(os.getenv("HAILA_SLM_REPETITION_PENALTY", "1.15")),
            no_repeat_ngram_size=int(os.getenv("HAILA_SLM_NO_REPEAT_NGRAM_SIZE", "3")),
            return_full_text=False,
        )[0]["generated_text"]
        data = _extrair_json(raw)
        distratores, normalizacoes = normalizar_distratores(data)
        return distratores, {"modelo": self.model, "adapter_path": str(self.adapter_path),
                             "normalizacoes": normalizacoes, "prompt_version": "slm-distractors-3.0.0"}


class QwenDistractorGenerator:
    """Qwen pequeno local, com LoRA opcional, usando o template de chat nativo."""
    def __init__(self, base_model: str, adapter_path: str | Path | None = None):
        self.base_model = base_model
        self.adapter_path = Path(adapter_path) if adapter_path else None
        sufixo = f"+LoRA:{self.adapter_path.name}" if self.adapter_path else ":base"
        self.model = f"{base_model}{sufixo}"
        self._model = None
        self._tokenizer = None

    def _load(self):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("integração Qwen requer torch e transformers") from exc

        torch.set_num_threads(int(os.getenv("HAILA_SLM_THREADS", "4")))
        origem_tokenizer = str(self.adapter_path) if self.adapter_path else self.base_model
        self._tokenizer = AutoTokenizer.from_pretrained(origem_tokenizer, use_fast=True)
        self._tokenizer.pad_token = self._tokenizer.pad_token or self._tokenizer.eos_token
        base = AutoModelForCausalLM.from_pretrained(
            self.base_model,
            dtype=torch.float32,
            low_cpu_mem_usage=True,
        )
        if self.adapter_path:
            if not self.adapter_path.exists():
                raise RuntimeError(f"adapter Qwen não encontrado: {self.adapter_path}")
            from peft import PeftModel
            # Na inferência o adaptador é imutável. Fundi-lo no modelo-base
            # remove a camada PEFT de cada passo de geração e reduz a latência
            # em CPU sem alterar os pesos aprendidos.
            base = PeftModel.from_pretrained(base, str(self.adapter_path)).merge_and_unload()
        base.config.use_cache = True
        self._model = base.eval()

    def __call__(self, nucleo, feedback):
        if self._model is None:
            self._load()
        import torch

        # Mantemos o prompt idêntico ao usado no ajuste. Injetar a descrição
        # longa da falha anterior fez este modelo pequeno abandonar o schema.
        # Saídas parciais são acumuladas abaixo, sempre com rastreabilidade.
        usuario = criar_prompt_distratores(
            nucleo.enunciado,
            nucleo.resposta_correta,
            None,
        )
        rejeitados = resumir_feedback_distratores(feedback)
        codigos_feedback = {
            str(item.get("codigo") or item.get("code") or "")
            for item in (feedback or [])
        }

        instrucao_reparo = ""

        if rejeitados:
            instrucao_reparo = (
                " Esta é uma nova tentativa. Não repita estas alternativas "
                f"rejeitadas: {json.dumps(rejeitados, ensure_ascii=False)}. "
                "Substitua-as por erros conceituais diferentes e plausíveis."
            )

        if codigos_feedback & {
            "distrator_parafraseia_gabarito",
            "copia_normalizada_gabarito",
        }:
            instrucao_reparo += (
                " Não gere singular/plural, flexões, abreviações, erros ortográficos "
                "ou reformulações lexicais da resposta correta. Use conceitos vizinhos "
                "que sejam realmente incorretos no cenário."
            )
        texto = self._tokenizer.apply_chat_template(
            [
                {"role": "system", "content": SYSTEM_DISTRACTORES_QWEN + instrucao_reparo},
                {"role": "user", "content": usuario},
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
        entrada = self._tokenizer(
            texto,
            return_tensors="pt",
            truncation=True,
            max_length=int(os.getenv("HAILA_SLM_MAX_INPUT_TOKENS", "2048")),
        )
        max_amostras = max(1, int(os.getenv("HAILA_QWEN_MAX_AMOSTRAS", "3")))
        tamanho_pool = max(4, int(os.getenv("HAILA_QWEN_CANDIDATE_POOL", "8")))
        acumulados: list[DistratorGerado] = []
        vistos: set[str] = {chave_semantica_curta(t) for t in rejeitados}
        chave_gabarito = chave_semantica_curta(nucleo.resposta_correta)
        normalizacoes: list[str] = []
        brutos: list[str] = []
        input_tokens_total = 0
        output_tokens_total = 0

        for numero_amostra in range(1, max_amostras + 1):
            with torch.inference_mode():
                ids = self._model.generate(
                    **entrada,
                    max_new_tokens=int(os.getenv("HAILA_SLM_MAX_NEW_TOKENS", "512")),
                    do_sample=True,
                    temperature=float(os.getenv("HAILA_SLM_TEMPERATURE", "0.3")),
                    top_p=float(os.getenv("HAILA_SLM_TOP_P", "0.85")),
                    repetition_penalty=float(os.getenv("HAILA_SLM_REPETITION_PENALTY", "1.15")),
                    no_repeat_ngram_size=int(os.getenv("HAILA_SLM_NO_REPEAT_NGRAM_SIZE", "3")),
                    pad_token_id=self._tokenizer.eos_token_id,
                )
            input_tokens_total += int(entrada["input_ids"].shape[1])
            output_tokens_total += int(ids.shape[1] - entrada["input_ids"].shape[1])
            bruto = self._tokenizer.decode(
                ids[0][entrada["input_ids"].shape[1]:],
                skip_special_tokens=True,
            )
            brutos.append(bruto)
            try:
                data = _extrair_json(bruto)
            except ValueError:
                continue

            try:
                parciais, reparos = normalizar_distratores_parciais(data)
            except ValueError:
                continue
            normalizacoes.extend(
                f"amostra_{numero_amostra}:{reparo}" for reparo in reparos
            )
            for distrator in parciais:
                if re.search(r"<\s*[A-Z][A-Z0-9_-]*\s*>", distrator.texto):
                    normalizacoes.append(
                        f"amostra_{numero_amostra}:placeholder_descartado"
                    )
                    continue
                motivo_lexical = motivo_distrator_lexicalmente_suspeito(
                    nucleo,
                    distrator.texto,
                )

                if motivo_lexical:
                    normalizacoes.append(
                        f"amostra_{numero_amostra}:"
                        f"candidato_lexical_descartado:"
                        f"{motivo_lexical}"
                    )
                    continue

                chave = chave_semantica_curta(distrator.texto)
                if chave and chave == chave_gabarito:
                    normalizacoes.append(
                        f"amostra_{numero_amostra}:copia_do_gabarito_descartada"
                    )
                    continue
                if chave and chave not in vistos:
                    vistos.add(chave)
                    acumulados.append(distrator)
            if len(acumulados) >= tamanho_pool:
                break

        if len(acumulados) >= 4:
            return acumulados[:tamanho_pool], {
                "modelo": self.model,
                "adapter_path": str(self.adapter_path) if self.adapter_path else None,
                "normalizacoes": normalizacoes,
                "amostras": len(brutos),
                "candidatos_gerados": len(acumulados[:tamanho_pool]),
                "feedback_aplicado": bool(rejeitados),
                "alternativas_rejeitadas": rejeitados,
                "prompt_version": "qwen-distractors-1.6.0",
                "token_usage_local": {
                    "input_tokens": input_tokens_total,
                    "output_tokens": output_tokens_total,
                    "total_tokens": input_tokens_total + output_tokens_total,
                },
            }

        amostras_brutas = [texto.strip().replace("\n", " ")[:180] for texto in brutos]
        raise ValueError(
            "Qwen não reuniu 4 distratores distintos; "
            f"candidatos={len(acumulados)}; amostras={max_amostras}; "
            f"inicios={amostras_brutas!r}"
        )


class GroqBestOfNSelector:
    """Seleciona quatro itens de um pool criado exclusivamente pela SLM."""
    def __init__(self, caller, model):
        self.caller, self.model = caller, model

    def __call__(self, nucleo, candidatos):
        payload = {
            "enunciado": nucleo.enunciado,
            "resposta_correta": nucleo.resposta_correta,
            "candidatos": [
                {"indice": indice, "texto": candidato.texto}
                for indice, candidato in enumerate(candidatos)
            ],
            "schema": {"indices": ["quatro inteiros distintos"]},
        }
        system = (
            "Você é o seletor de candidatos da HAILA. A SLM já gerou todos os "
            "candidatos; você não pode criar nem reescrever alternativas. Escolha "
            "exatamente quatro índices. Priorize conceitos reais, incorretos para o "
            "cenário, plausíveis para estudantes, relevantes e distintos. Exclua "
            "cópias ou paráfrases do gabarito, palavras inventadas, erros gramaticais, "
            "alternativas vagas e possíveis respostas corretas. Responda apenas JSON."
        )
        data = json.loads(self.caller(system, json.dumps(payload, ensure_ascii=False)))
        indices = data.get("indices")
        if not isinstance(indices, list) or len(indices) != 4:
            raise ValueError("seletor semântico não devolveu quatro índices")
        if any(type(i) is not int or i < 0 or i >= len(candidatos) for i in indices):
            raise ValueError("seletor semântico devolveu índice inválido")
        if len(set(indices)) != 4:
            raise ValueError("seletor semântico repetiu índices")
        return [candidatos[i] for i in indices], {
            "modelo": self.model,
            "indices_selecionados": indices,
        }


class DeterministicPoolSelector:
    """Escolhe quatro candidatos da SLM sem gerar ou reescrever conteúdo."""
    model = "deterministic-pool-selector-v1"

    @staticmethod
    def _palavras(texto: str) -> list[str]:
        base = unicodedata.normalize("NFKD", str(texto).casefold())
        base = "".join(c for c in base if not unicodedata.combining(c))
        return re.findall(r"[a-z0-9]+", base)

    def __call__(self, nucleo, candidatos):
        tamanho_gabarito = max(1, len(self._palavras(nucleo.resposta_correta)))
        pontuados = []
        for indice, candidato in enumerate(candidatos):
            palavras = self._palavras(candidato.texto)
            tamanho = max(1, len(palavras))
            # Premia paralelismo de extensão e conteúdo específico. O índice
            # estabiliza empates para que a mesma entrada produza a mesma saída.
            desvio = abs(tamanho - tamanho_gabarito) / tamanho_gabarito
            especificidade = len(set(palavras)) / tamanho
            pontuados.append((desvio, -especificidade, indice))
        indices = [indice for _, _, indice in sorted(pontuados)[:4]]
        if len(indices) != 4:
            raise ValueError("pool da SLM não contém quatro candidatos selecionáveis")
        return [candidatos[i] for i in indices], {
            "modelo": self.model,
            "indices_selecionados": indices,
            "criterio": "paralelismo_de_extensao_e_especificidade_lexical",
        }



def _token_qualidade(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto).casefold())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", base)


def _base_flexao_portugues(token: str) -> str:
    # Plurais frequentes suficientes para não tratar flexão como corrupção.
    # Ex.: requisito/requisitos e funcional/funcionais.
    if len(token) > 6 and token.endswith("ais"):
        return token[:-3] + "al"
    if len(token) > 6 and token.endswith("eis"):
        return token[:-3] + "el"
    if len(token) > 6 and token.endswith("ois"):
        return token[:-3] + "ol"
    if len(token) > 6 and token.endswith("oes"):
        return token[:-3] + "ao"
    if len(token) > 4 and token.endswith("s"):
        return token[:-1]
    return token


def _flexao_simples(a: str, b: str) -> bool:
    return _base_flexao_portugues(a) == _base_flexao_portugues(b)


def _motivo_candidato_pos_filtro(nucleo, texto: str) -> str | None:
    bruto = str(texto).strip()
    if re.search(r"^\s*(?:\([A-E]\)|[A-E][\)\].:\-])\s*", bruto, re.I):
        return "rotulo_de_alternativa_embutido"

    tokens_candidato = re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]*", bruto)
    tokens_gabarito = re.findall(
        r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]*",
        str(nucleo.resposta_correta),
    )
    bases_gabarito = [_token_qualidade(x) for x in tokens_gabarito]

    for token in tokens_candidato:
        base = _token_qualidade(token)
        if len(base) < 6:
            continue
        for origem in bases_gabarito:
            if len(origem) < 6 or base == origem:
                continue
            if _flexao_simples(base, origem):
                continue
            if base[:4] != origem[:4]:
                continue
            if abs(len(base) - len(origem)) > 4:
                continue
            sim = SequenceMatcher(None, base, origem).ratio()
            if sim >= 0.80:
                return (
                    f'possivel_deformacao_lexical:{token}~{origem}:'
                    f'{sim:.2f}'
                )
    return None


def _filtrar_pool_final(nucleo, candidatos):
    validos = []
    rejeitados = []
    for candidato in candidatos:
        motivo = _motivo_candidato_pos_filtro(nucleo, candidato.texto)
        if motivo:
            rejeitados.append({"texto": candidato.texto, "motivo": motivo})
        else:
            validos.append(candidato)
    return validos, rejeitados


class BestOfNDistractorGenerator:
    """Gera N pela SLM e reduz para quatro sem permitir criação pelo seletor."""
    def __init__(self, generator, selector):
        self.generator, self.selector = generator, selector
        self.model = f"best-of-n({getattr(generator, 'model', 'slm')})"

    def __call__(self, nucleo, feedback):
        candidatos, provenance = self.generator(nucleo, feedback)
        candidatos, rejeitados_pos_filtro = _filtrar_pool_final(nucleo, candidatos)
        if rejeitados_pos_filtro:
            provenance = dict(
                provenance,
                pos_filtro_rejeitados=rejeitados_pos_filtro,
            )
        if len(candidatos) < 4:
            raise ValueError(
                "pool insuficiente após filtro de qualidade; "
                f"validos={len(candidatos)}; rejeitados={rejeitados_pos_filtro}"
            )
        if len(candidatos) == 4:
            return candidatos, dict(provenance, selecao="pool_exato")
        escolhidos, selecao = self.selector(nucleo, candidatos)
        tipo_selecao = (
            "deterministic_best_of_n"
            if getattr(self.selector, "model", "").startswith("deterministic-")
            else "groq_best_of_n"
        )
        return escolhidos, dict(
            provenance,
            selecao=tipo_selecao,
            candidatos_no_pool=len(candidatos),
            seletor=selecao,
        )


def _extrair_json(raw: str) -> Any:
    """Recupera a estrutura mesmo quando o SLM repete texto após o primeiro JSON."""
    decoder = json.JSONDecoder()
    for inicio, caractere in enumerate(raw):
        if caractere not in "[{":
            continue
        try:
            data, _ = decoder.raw_decode(raw[inicio:])
            if isinstance(data, (dict, list)):
                return data
        except json.JSONDecodeError:
            pass

    # Alguns modelos pequenos devolvem a representação Python com aspas
    # simples. literal_eval é restrito a literais e não executa código.
    candidatos = []
    for abertura, fechamento in (("{", "}"), ("[", "]")):
        inicio, fim = raw.find(abertura), raw.rfind(fechamento)
        if inicio >= 0 and fim >= inicio:
            candidatos.append(raw[inicio:fim + 1])
    for candidato in candidatos:
        try:
            data = ast.literal_eval(candidato)
            if isinstance(data, (dict, list)):
                return data
        except (SyntaxError, ValueError):
            pass

    # Último recurso controlado: quatro linhas numeradas ou com marcadores.
    linhas = []
    padrao = re.compile(r"^\s*(?:\d+\s*[\).:\-]|[-*])\s*(.+?)\s*$")
    for linha in raw.splitlines():
        achado = padrao.match(linha)
        if achado:
            texto = achado.group(1).strip().rstrip(",").strip().strip("\"'")
            if texto:
                linhas.append(texto)
    if len(linhas) == 4:
        return linhas

    amostra = raw.strip().replace("\n", " ")[:240]
    raise ValueError(f"SLM não devolveu JSON de distratores válido; início={amostra!r}")


def normalizar_distratores(data: Any) -> tuple[list[DistratorGerado], list[str]]:
    saida, normalizacoes = normalizar_distratores_parciais(data)
    if len(saida) != 4:
        raise ValueError(
            f"SLM deve devolver exatamente 4 distratores; recebeu {len(saida)}"
        )
    return saida, normalizacoes


def normalizar_distratores_parciais(data: Any) -> tuple[list[DistratorGerado], list[str]]:
    """Normaliza de zero a N candidatos; o contrato exato é aplicado acima."""
    normalizacoes: list[str] = []

    # HAILA_V14_PARSER_TOLERANTE
    if isinstance(data, dict):
        aliases = {
            "distratores", "distrator", "distratos",
            "distrators", "distrutores", "alternativas",
        }
        candidatos_brutos = []

        for chave, valor in data.items():
            chave_norm = re.sub(r"[^a-z]", "", str(chave).casefold())
            eh_alias = chave_norm in aliases
            eh_variacao = chave_norm.startswith("distrat") or chave_norm.startswith("distor")
            campo_correto = "corret" in chave_norm or "gabarit" in chave_norm or "answer" in chave_norm

            if isinstance(valor, list) and (eh_alias or eh_variacao) and not campo_correto:
                candidatos_brutos.extend(valor)
                if chave != "distratores":
                    normalizacoes.append(f"{chave}->distratores")

        if candidatos_brutos:
            data = candidatos_brutos

    if not isinstance(data, list):
        raise ValueError("saída SLM não contém lista de distratores")

    saida = []
    for item in data:
        if isinstance(item, str):
            normalizacoes.append("string->objeto")
            item = {"texto": item}
        if not isinstance(item, dict):
            raise ValueError("distrator malformado")

        texto = item.get("texto") or item.get("distrator") or item.get("alternativa")
        if not texto:
            raise ValueError("distrator sem texto")

        texto = re.sub(r"\s+", " ", str(texto).replace("\\n", " ").strip())
        if not texto:
            continue

        saida.append(DistratorGerado(
            texto,
            str(item.get("erro", "")).strip(),
            str(item.get("por_que_e_falso", "")).strip(),
        ))

    return saida, normalizacoes

def stem_generator_from_env() -> EnadeStemGenerator:
    key = os.getenv("GROQ_API_KEY")
    if not key: raise RuntimeError("GROQ_API_KEY não configurada")
    from openai import OpenAI
    model = os.getenv("HAILA_STEM_MODEL", "openai/gpt-oss-120b")
    client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1",
                    timeout=float(os.getenv("HAILA_GROQ_TIMEOUT_SECONDS", "60")), max_retries=0)
    def call(system, user):
        r = client.chat.completions.create(model=model, messages=[{"role":"system","content":system},{"role":"user","content":user}],
                                           temperature=0.7, response_format={"type":"json_object"})
        usage = getattr(r, "usage", None)
        call.last_usage = {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }
        return r.choices[0].message.content or "{}"
    call.last_usage = None
    return EnadeStemGenerator(call, model)


_LOCAL_SLM_CACHE: dict[tuple[str, str, str], Any] = {}


def slm_generator_from_env() -> TinyLlamaLoraDistractorGenerator:
    from .hybrid import HybridDistractorGenerator

    backend = slm_backend()
    path = resolve_adapter_path(backend=backend)
    base_model = slm_base_model(backend)

    if backend not in {"qwen", "tinyllama"}:
        raise RuntimeError(f"HAILA_SLM_BACKEND inválido: {backend!r}")

    adapter_ok = adapter_is_complete(path)
    if backend == "qwen" and not adapter_ok and not allow_base_qwen():
        raise RuntimeError(
            "LoRA Qwen do HAILA não encontrado ou incompleto em "
            f"{path}. Esperados adapter_config.json e adapter_model.safetensors. "
            "Use HAILA_ALLOW_BASE_QWEN=1 apenas para ablação com o modelo base."
        )
    if backend == "tinyllama" and not adapter_ok:
        raise RuntimeError(
            f"adapter TinyLlama não encontrado ou incompleto em {path}"
        )

    # Em produção Qwen usa sempre o LoRA selecionado. O base puro só é usado
    # quando a ablação é habilitada explicitamente.
    effective_path = path if adapter_ok else None

    use_memory = os.getenv("HAILA_USE_CURATED_MEMORY", "1") == "1"
    use_rules = os.getenv("HAILA_USE_DETERMINISTIC_DISTRACTOR_RULES", "1") == "1"
    cache_key = (backend, base_model, str(effective_path or ""), use_memory, use_rules)
    hibrido = _LOCAL_SLM_CACHE.get(cache_key)
    if hibrido is None:
        slm = (
            QwenDistractorGenerator(base_model, effective_path)
            if backend == "qwen"
            else TinyLlamaLoraDistractorGenerator(effective_path, base_model)
        )
        hibrido = HybridDistractorGenerator(slm, use_memory=use_memory, use_rules=use_rules)
        _LOCAL_SLM_CACHE[cache_key] = hibrido
    return BestOfNDistractorGenerator(hibrido, DeterministicPoolSelector())
