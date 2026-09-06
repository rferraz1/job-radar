from enrich.prompt import montar_prompt
from job import Job


def _job():
    return Job(titulo="DevOps Júnior", empresa="ACME", local="Recife, PE",
               link="http://x/1", site="Greenhouse", modalidade="Remoto")


def test_prompt_tem_vaga_cv_e_schema():
    p = montar_prompt(_job(), "Descrição: Terraform, AWS, CI/CD.", "CV: Rodolfo, Python, Node.", hint="platform-devops")
    assert "DevOps Júnior" in p and "ACME" in p
    assert "Terraform, AWS" in p
    assert "Rodolfo, Python, Node" in p
    assert "compat_score" in p and "salary_estimate" in p and "gaps" in p
    assert "bloqueante" in p  # instrução sobre gap bloqueante
    assert "JSON" in p


def test_cv_vazio_nao_quebra():
    p = montar_prompt(_job(), "desc", "", hint="dev")
    assert "sem cv" in p.lower() or "não informado" in p.lower()
