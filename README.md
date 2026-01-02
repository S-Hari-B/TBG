# TBG

Text Based Game (TBG) is a skeleton project built around a deterministic RNG core and a console UI.

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

Data definitions live in `data/definitions/*.json` and are loaded through the data-layer repositories (no presentation or domain code reads JSON directly).

Set `TBG_DEBUG=1` before launching if you want verbose debug output (story node ids, exact HP values, etc.).

## Running the Tests

```
pytest
```

Pytest will pick up tests from the `tests/` folder, including data-layer suites that rely on `tmp_path` overrides so the real JSON files remain untouched.

