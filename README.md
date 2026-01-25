# Echoes of the Cycle (v0.0.1)

Echoes of the Cycle is a demo / vertical slice of a deterministic, text-based RPG. Content is intentionally limited and reaching an ending is expected.

## Getting Started

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

## Running From Source

```bash
python -m tbg
```

Follow the on-screen menu to start a new game or exit. Starting a new game lets you supply a seed or have one generated for you. The seed is then used to seed the deterministic RNG.

Set `TBG_DEBUG=1` before launching if you want verbose debug output (story node ids, exact HP values, etc.).

## Config & Saves

Config and saves are stored in a user-writable directory:

- Windows: `%APPDATA%\EchoesOfTheCycle\`
  - Config: `config.json`
  - Saves: `saves\slot_#.json`
- macOS/Linux: `~/.config/echoes_of_the_cycle/`
  - Config: `config.json`
  - Saves: `saves/slot_#.json`

If `%APPDATA%` is unavailable, Windows falls back to `~/EchoesOfTheCycle/`.

## Building a Windows EXE (PyInstaller, onedir)

Install PyInstaller, then build:

```bash
python -m pip install pyinstaller
pyinstaller --clean --name "EchoesOfTheCycle" --onedir --console --paths src --add-data "data/definitions;data/definitions" src/tbg/__main__.py
```

The build output will be in `dist/EchoesOfTheCycle/`.

## Packaging for itch.io

- Zip the entire `dist/EchoesOfTheCycle/` folder.
- Run `EchoesOfTheCycle.exe` from inside the extracted folder.

## Resetting the Demo

Delete the config/saves directory listed above to reset:

- Windows: `%APPDATA%\EchoesOfTheCycle\`
- macOS/Linux: `~/.config/echoes_of_the_cycle/`

## Running the Tests

```bash
pytest
```

Pytest will pick up tests from the `tests/` folder. Behavior tests should assert invariants and logic without hardcoding production balance values.

Behavior test fixtures live under `tests/fixtures/data/definitions/` and provide a minimal, stable dataset for service/domain tests.

Balance snapshot tests (if added) should be marked with `@pytest.mark.balance_snapshot`. These are excluded by default; run them intentionally with:

```bash
pytest -m balance_snapshot
```
