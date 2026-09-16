"""Install a wheel and its runtime dependencies in a fresh temporary environment."""

import os
import subprocess
import tempfile
import venv
from pathlib import Path

SMOKE = r"""
import importlib.metadata
from komandaro import Invoker, Macro, SimpleCommandFactory, translate
from komandaro.i18n import _

assert importlib.metadata.version("komandaro")
for language in ("en", "fr", "eo"):
    assert translate(_("nothing_to_undo"), language) != "nothing_to_undo"
context = []
Add = SimpleCommandFactory(lambda c: c.append("ok"), lambda c, state: c.pop(), "Add")
invoker = Invoker(context)
invoker.run(Macro(context, [Add(context)]))
assert context == ["ok"]
invoker.undo()
assert context == []
invoker.redo()
assert context == ["ok"]
print("Installed wheel: import, translations, macro, undo and redo passed")
"""


def main() -> None:
    wheels = list(Path("dist").glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("expected exactly one wheel in dist/")
    wheel = wheels[0].resolve()
    with tempfile.TemporaryDirectory(prefix="komandaro-wheel-") as directory:
        root = Path(directory)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        executable = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run([str(executable), "-m", "pip", "install", str(wheel)], cwd=root, check=True)
        # -I excludes the working directory, user packages and PYTHONPATH.
        subprocess.run([str(executable), "-I", "-c", SMOKE], cwd=root, check=True)


if __name__ == "__main__":
    main()
