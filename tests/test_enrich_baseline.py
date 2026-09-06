from enrich.baseline import carregar_cv


def test_carrega_html_limpo(tmp_path):
    f = tmp_path / "cv.html"
    f.write_text("<html><body><h1>Rodolfo</h1><p>Python &amp; Node</p><script>x=1</script></body></html>")
    txt = carregar_cv(str(f))
    assert "Rodolfo" in txt
    assert "Python & Node" in txt
    assert "x=1" not in txt  # script removido


def test_arquivo_inexistente_retorna_vazio(caplog):
    assert carregar_cv("/nao/existe/cv.html") == ""


def test_cacheia_por_path(tmp_path):
    f = tmp_path / "cv.html"
    f.write_text("<body>v1</body>")
    assert "v1" in carregar_cv(str(f))
    f.write_text("<body>v2</body>")
    assert "v1" in carregar_cv(str(f))  # cache — não relê
