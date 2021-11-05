from fmf.plugins.pytest import TMT


@TMT.tag("Tier1")
@TMT.summary("Rewritten")
def test_pass():
    assert True
