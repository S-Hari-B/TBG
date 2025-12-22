from tbg.core.rng import RNG


def test_rng_determinism_same_seed() -> None:
    rng_a = RNG(12345)
    rng_b = RNG(12345)

    ints_a = [rng_a.randint(1, 100) for _ in range(5)]
    ints_b = [rng_b.randint(1, 100) for _ in range(5)]
    floats_a = [rng_a.random() for _ in range(5)]
    floats_b = [rng_b.random() for _ in range(5)]
    choices_a = [rng_a.choice(["a", "b", "c"]) for _ in range(5)]
    choices_b = [rng_b.choice(["a", "b", "c"]) for _ in range(5)]

    assert ints_a == ints_b
    assert floats_a == floats_b
    assert choices_a == choices_b


def test_rng_different_seed() -> None:
    rng_a = RNG(11111)
    rng_b = RNG(22222)

    draws_a = [rng_a.randint(1, 100) for _ in range(5)]
    draws_b = [rng_b.randint(1, 100) for _ in range(5)]

    assert draws_a != draws_b

