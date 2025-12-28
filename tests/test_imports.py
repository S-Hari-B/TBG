def test_import_tbg_package() -> None:
    import importlib

    module = importlib.import_module("tbg")
    assert module is not None


def test_import_rng_no_side_effects() -> None:
    from tbg.core.rng import RNG

    rng = RNG(42)
    value = rng.randint(0, 1)
    assert value in (0, 1)

