# TBG

Tiny Battleground (TBG) is a skeleton project built around a deterministic RNG core and a console UI.

## Getting Started

```
python -m pip install --upgrade pip
python -m pip install -e .
```

## Running the CLI

```
python -m tbg
```

Follow the on-screen menu to start a new game or exit. Starting a new game lets you supply a seed or have one generated for you. The seed is then used to seed the deterministic RNG.

## Running the Tests

```
pytest
```

Pytest will pick up tests from the `tests/` folder and verify the RNG contract.

