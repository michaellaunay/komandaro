# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org).

## [0.2.1] — 2026-09-16

Documentation release.

### Added
- Documentation set in English and French under `docs/`: *How it works*
  (the ideas in plain words), *Tutorial* (step by step, every block
  executed by the test suite), *Examples* (patterns: counter, text buffer,
  memento, atomic bank transfer, audit log, custom redo, entry points),
  *API reference*, plus the refreshed *Architecture*; `docs/README.md`
  index and a Documentation section in the README.
- `examples/notebook/`: the tutorial application — its logic as commands
  (`notebook.py`), a command line generated from the registry (`cli.py`,
  interactive or one-shot, `--lang`), and a French catalogue in its own
  gettext domain. Covered by `tests/test_examples.py`.
- pytest now runs every ```pycon block under `docs/` (`--doctest-glob=*.md`);
  a session fixture compiles the `.po` catalogues so tests and doctests
  translate without a prior `pybabel compile`.

### Changed
- Tests are run as `python -m pytest` (documented everywhere): a bare
  `pytest` may resolve to a system-wide install outside the virtual
  environment. The test session pins `LANGUAGE=en` so that untranslated
  expectations hold on machines with another locale; the tutorial's CLI
  session passes `lang="en"` explicitly and explains why.
- `Macro.__init__` accepts `**params` validated against the subclass
  `schema` (the keyword names `commands`, `name`, `description` stay
  reserved), so macros can build their children from parameters.

## [0.2.0] — 2026-09-16

Phase 2: commands describe themselves; an invoker runs them.

### Added
- `komandaro.schema`: parameter schemas as `zope.interface` interfaces of
  `zope.schema` fields; `validate()` (all issues reported at once, defaults
  applied, translatable `ParameterError`/`ParameterIssue`) and `describe()`
  (`ParameterInfo` records for front ends).
- Commands take keyword parameters: `Cmd(context, **params)`, validated
  against `Cmd.schema` and exposed as `cmd.params`; `do_it(context, **params)`,
  `undo_it(context, state, **params)`.
- Memento hook: `BaseCommand._snapshot()` / `SimpleCommandFactory(...,
  snapshot=fn)`; the value is kept in `cmd.memento` and handed to `undo`.
- Stable command ids (`BaseCommand.id`, derived from the class name or set
  explicitly).
- `komandaro.registry`: `Registry` (ids, groups, tags, decorator,
  entry-point loading, `create()`), `Entry`, `RegistryError`.
- `komandaro.invoker`: `Invoker` (run by id or instance, undo/redo stacks,
  optional history limit, `Event`/`EventKind` observers, `clear()`),
  `HistoryError`.
- 8 new translatable messages, catalogues `en`/`fr`/`eo` complete.
- 27 new tests; architecture docs (EN/FR) gain sections on schemas,
  registry and invoker with two new Mermaid diagrams each.

### Changed
- New dependency: `zope.schema`.
- `Invoker`, `Registry`, `describe`, `validate` and the error classes are
  exported from the package root.

### Compatibility
- Phase-1 code keeps working: commands without a schema accept any
  parameters, and `do(context)` / `undo(context, result)` functions are
  called unchanged when no parameters are given.

## [0.1.0] — 2026-09-16

Phase 1: rebirth of the 2014 `ecreall.command` prototype as **Komandaro**.

### Added
- `SimpleCommandFactory`, `SimpleCommand`, `Macro` with an explicit
  ready → executed → undone state machine on marker interfaces.
- Atomic macros: a failing sub-command triggers the undo of the ones
  already executed.
- gettext internationalisation (`komandaro.i18n`): lazy `Message`, per-call
  `translate()`, catalogues `en`, `fr`, `eo`.
- Test suite (pytest, doctests of the README), GitHub Actions CI on
  Python 3.12 and 3.13 (ruff, mypy, pytest with coverage).
- Architecture documentation in English and French with Mermaid diagrams.
- AGPL-3.0-or-later licence.

### Fixed (compared with `ecreall.command` 0.1dev)
- `NameError` on `name = name` in the factory's class body.
- `TypeError`: do/undo functions were bound as methods; now static methods.
- `return result` instead of `self.result` in `execute()`.
- `noLongerProvides` on a class-level interface (`ValueError`); state markers
  are now set with `directlyProvides`, kinds stay on the class.
- `IUndoneCommand` did not extend `IBaseCommand`.
- Python 3 support (`@implementer` instead of `implements`).
- Doctest syntax (`...` continuation lines) and completed example.
