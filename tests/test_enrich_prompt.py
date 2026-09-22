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


def test_modalidade_confirmada_nao_aparece_ressalva():
    p = montar_prompt(_job(), "desc", "cv", hint="dev")
    assert "Modalidade: Remoto\n" in p


def test_modalidade_nao_confirmada_aparece_ressalva():
    job = Job(titulo="Suporte Jr", empresa="X", local="Brasília, DF",
               link="http://x/2", site="LinkedIn", modalidade="Remoto",
               modalidade_confirmada=False)
    p = montar_prompt(job, "desc", "cv", hint="dev")
    assert "NÃO CONFIRMADA" in p
    assert "Remoto (NÃO CONFIRMADA" in p
