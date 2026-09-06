from job import Job


def test_job_tem_descricao_e_analise_default():
    j = Job(titulo="X", empresa="Y", local="Z", link="http://x/1", site="S")
    assert j.descricao == ""
    assert j.analise is None
