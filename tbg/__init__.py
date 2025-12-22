"""Bootstrap package that forwards to the implementation under src/."""
from __future__ import annotations

from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent / "src" / "tbg"
__path__ = [str(_PKG_DIR)]
__file__ = str(_PKG_DIR / "__init__.py")

with open(__file__, "r", encoding="utf-8") as _handle:
    exec(compile(_handle.read(), __file__, "exec"), globals(), globals())


