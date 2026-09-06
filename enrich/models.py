# enrich/models.py
import json
from dataclasses import dataclass, field, asdict

_VERDICTS = {"candidatar", "avaliar", "pular"}
_SEVERIDADES = {"bloqueante", "importante", "menor"}
_CONFIANCAS = {"alta", "media", "baixa"}


@dataclass
class SalaryEstimate:
    min: int | None = None
    max: int | None = None
    moeda: str = "BRL"
    periodo: str = "mes"
    confianca: str = "baixa"
    base: str = ""

    @classmethod
    def from_dict(cls, d: dict | None) -> "SalaryEstimate":
        d = d or {}
        conf = str(d.get("confianca", "baixa")).lower()
        return cls(
            min=_int_ou_none(d.get("min")),
            max=_int_ou_none(d.get("max")),
            moeda=str(d.get("moeda", "BRL")),
            periodo=str(d.get("periodo", "mes")),
            confianca=conf if conf in _CONFIANCAS else "baixa",
            base=str(d.get("base", "")),
        )


@dataclass
class Gap:
    requisito: str
    severidade: str = "importante"
    tenho_parcial: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "Gap":
        sev = str(d.get("severidade", "importante")).lower()
        return cls(
            requisito=str(d.get("requisito", "")).strip(),
            severidade=sev if sev in _SEVERIDADES else "importante",
            tenho_parcial=bool(d.get("tenho_parcial", False)),
        )


@dataclass
class Analysis:
    compat_score: int
    compat_reasoning: str
    salary_estimate: SalaryEstimate
    gaps: list[Gap] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    verdict: str = "avaliar"
    verdict_reason: str = ""
    descricao_parcial: bool = False  # True quando a análise usou só o texto do card

    @classmethod
    def from_dict(cls, d: dict) -> "Analysis":
        obrigatorios = ("compat_score", "compat_reasoning", "verdict")
        faltando = [k for k in obrigatorios if k not in d]
        if faltando:
            raise ValueError(f"Analysis.from_dict: campos faltando: {faltando}")
        try:
            score = int(round(float(d["compat_score"])))
        except (TypeError, ValueError):
            raise ValueError(f"compat_score não numérico: {d['compat_score']!r}")
        score = max(0, min(100, score))
        verdict = str(d["verdict"]).lower().strip()
        return cls(
            compat_score=score,
            compat_reasoning=str(d["compat_reasoning"]).strip(),
            salary_estimate=SalaryEstimate.from_dict(d.get("salary_estimate")),
            gaps=[Gap.from_dict(g) for g in (d.get("gaps") or []) if isinstance(g, dict)],
            strengths=[str(s).strip() for s in (d.get("strengths") or []) if str(s).strip()],
            verdict=verdict if verdict in _VERDICTS else "avaliar",
            verdict_reason=str(d.get("verdict_reason", "")).strip(),
            descricao_parcial=bool(d.get("descricao_parcial", False)),
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    def resumo_curto(self) -> str:
        s = self.salary_estimate
        sal = f"R$ {s.min}–{s.max}" if s.min is not None and s.max is not None else "salário n/d"
        blk = sum(1 for g in self.gaps if g.severidade == "bloqueante")
        return f"{self.compat_score}% · {sal} · {blk} gap(s) bloqueante(s) · {self.verdict}"


def _int_ou_none(v):
    try:
        return int(round(float(v))) if v is not None else None
    except (TypeError, ValueError):
        return None
