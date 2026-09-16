# Komandaro documentation

| | English | Français |
|---|---|---|
| Start here — the ideas in plain words | [How it works](en/how-it-works.md) | [Comment ça marche](fr/how-it-works.md) |
| Step by step, with running code | [Tutorial](en/tutorial.md) | [Tutoriel](fr/tutorial.md) |
| Patterns and snippets | [Examples](en/examples.md) | [Exemples](fr/examples.md) |
| Every public name | [API reference](en/api.md) | [Référence de l'API](fr/api.md) |
| Design, diagrams, roadmap | [Architecture](en/architecture.md) | [Architecture](fr/architecture.md) |

The complete example application is in [`../examples/notebook/`](../examples/notebook/).

Every `pycon` block in these pages is executed by the test suite
(`python -m pytest` runs `--doctest-glob=*.md` over `docs/`), so the
documentation cannot silently drift from the code. Use the `python -m`
form: a bare `pytest` may be the system's, outside your virtual environment.
