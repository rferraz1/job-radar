_SCHEMA = """{
  "compat_score": <int 0-100>,
  "compat_reasoning": "<2-3 frases>",
  "salary_estimate": {"min": <int|null>, "max": <int|null>, "moeda": "BRL", "periodo": "mes",
                      "confianca": "alta|media|baixa", "base": "<de onde inferiu>"},
  "gaps": [{"requisito": "<texto>", "severidade": "bloqueante|importante|menor", "tenho_parcial": <bool>}],
  "strengths": ["<requisito batido ou projeto do CV>"],
  "verdict": "candidatar|avaliar|pular",
  "verdict_reason": "<uma linha>"
}"""

_INSTRUCOES = """Você avalia o encaixe entre UM candidato e UMA vaga, para uma pessoa em
transição de carreira (ex-personal trainer, ~6 meses de experiência formal em TI, forte em
projetos próprios de Python/JS/GenAI). Trilha alvo: {hint}.

Regras:
- Seja realista. Um score alto otimista é pior que um score baixo correto.
- Gap BLOQUEANTE (inglês fluente obrigatório, "N+ anos de experiência", graduação completa
  exigida, senioridade sênior/especialista) derruba compat_score para faixa baixa (<40),
  não importa quão bem as skills batem.
- salary_estimate: só preencha min/max com base real (faixa no anúncio, ou faixa típica
  clara do cargo+senioridade no Brasil). Sem base: min/max null, confianca "baixa".
- verdict reflete o conjunto (score + gaps + coerência com a transição), não só o número.

Responda SOMENTE com um objeto JSON neste formato, sem texto antes ou depois:
{schema}"""


def montar_prompt(job, descricao: str, cv_text: str, hint: str = "dev") -> str:
    cv = cv_text.strip() or "(sem CV disponível — avalie só pelo título/senioridade da vaga)"
    return (
        _INSTRUCOES.format(hint=hint, schema=_SCHEMA)
        + "\n\n=== VAGA ===\n"
        + f"Título: {job.titulo}\nEmpresa: {job.empresa}\nLocal: {job.local}\n"
        + f"Modalidade: {job.modalidade or 'não informada'}\n"
        + f"Senioridade (estimada do título): {job.senioridade}\n\n"
        + f"Descrição:\n{descricao.strip()[:8000]}\n\n"
        + "=== CANDIDATO (CV) ===\n"
        + cv[:8000]
    )
