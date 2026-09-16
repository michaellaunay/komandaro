# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org).

## [Unreleased]

## [0.4.0] — 2026-09-16

### Security and compatibility
- Reauthorize the current subject on run, undo and redo, including all built-in
  macro descendants; reject foreign contexts, repeated instances and cycles.
  This intentionally tightens 0.3.0's undo/redo authorization policy.
- Separate Flag/IntFlag permission domains before equality comparisons.
- Preserve all compensation failures and expose `IBrokenCommand` / `is_broken`
  when application recovery is required. Reject reentrant transitions.
- Isolate ordinary observer exceptions from business outcomes; process-control
  exceptions remain visible. Observer notifications are not transaction hooks.

### Fixed
- Restore retryable macro states after compensated execute, undo and redo failures;
  preserve unrelated direct Zope markers while replacing state subinterfaces.
- Validate history limits before side effects and make unsubscribe idempotent.
- Isolate static container defaults while preserving Choice/factory/object identity;
  keep selected registry aliases on instances without mutating their classes.
- Stabilize language generators across nested messages, retain English fallback
  for C/POSIX variants, and handle duplicate error-formatting arguments.
- Compile catalogues automatically in clean wheel, sdist and editable builds;
  check complete gettext ids, contexts, plurals and placeholders.

- Reject malformed CLI quoting and boolean values; preserve non-zero exit
  status for invalid arguments and failed one-shot commands. Validate `--lang`.

### Changed
- Pin GitHub Actions to verified SHAs, disable persisted checkout credentials,
  and add Dependabot action updates and bounded job durations.
- Require matching version tags for every production publication. Run quality
  gates and installed-wheel smoke checks on Python 3.12, 3.13 and 3.14 before
  publishing; configuration alone is not a claim that these new jobs passed.
- Align Ruff and pre-commit on 0.16.8; update French and English API, architecture,
  tutorials, reliability and release documentation.

## [0.3.0] — 2026-09-16

Consolidation: closes what the initial audit left open before any front
end is built. Minor version because the message catalogue contract changes.

### Changed
- **Message identifiers.** Library messages are `snake_case` identifiers
  (`command_already_executed`, `nothing_to_undo`…) with the English text in
  the `en` catalogue; placeholders are `${name}` (`string.Template`) instead
  of `%(name)s`. `translate()` tries the requested language, then English,
  then returns the identifier. `str(error)` renders in the language of the
  process. Same convention as AlirPunkto. Applications keeping plain-text
  message ids still work.
- **Interfaces aligned with the implementation**: `IBaseCommand` declares
  `id`, `schema`, `permission`, `params`, `memento`; `ISimpleCommand`
  declares `do_it`/`undo_it`/`snapshot_it`; new `IEntry`, `IRegistry`,
  `IInvoker`, `IEvent`, `IPermissionPolicy`; `Registry`, `Entry`, `Invoker`,
  `Event` and the policies carry `@implementer`. `tests/test_interfaces.py`
  verifies every implementation (`verifyClass`/`verifyObject`).
- Decision recorded: `undo(context, state, **params)` is kept (`state` is
  the result, or the memento when a `snapshot` exists); no `Outcome` object.
- `IContext` is kept as an optional, never-checked marker.
- The example application uses identifiers and ships `en` and `fr`
  catalogues; `make_gettext("notebook", localedir)` binds its domain.
- GitHub Actions: `checkout@v7`, `setup-python@v7`, `upload-artifact@v7`,
  `download-artifact@v8` (removes the Node 20 deprecation warning).

### Added
- `komandaro.permissions`: a detachable permission model. `BaseCommand.permission`
  (any object, `None` = public); `Invoker(policy=..., subject=...)` checks
  `policy.permits(subject, required, command)` before running, raises
  `PermissionDeniedError` and emits a `denied` event; `Registry.allowed(policy,
  subject)` filters entries for menus. `SubjectPermissionsPolicy` handles flat
  names, `IntFlag` bit sets and permission-class hierarchies (diamond
  inheritance) through two replaceable functions; `AllowAll` permits all.
- `zope.schema` validation errors mapped to identifiers (`field_too_short`,
  `field_too_small`, `field_wrong_type`…) and translated; nested `Message`
  parameters are translated by `Message.localize`.
- `bind_domain(domain, localedir)`, `make_gettext(domain, localedir)`,
  `environment_languages()`, `FALLBACK_LANGUAGE`, `LOCALEDIRS`.
- `.pre-commit-config.yaml` (ruff, ruff-format, mypy, `.pot` freshness);
  `pre-commit` in the `dev` extra.
- 32 new tests (interfaces, permissions, i18n); documentation updated in both
  languages (tutorial: permissions and identifiers; how-it-works; API;
  architecture with the decisions recorded).

## [0.2.1] — 2026-09-16

Documentation release; first version published on PyPI.

### Added
- `Release` workflow: on a `v*` tag (or manually, with a TestPyPI dry run),
  checks the tag against the version, runs the tests, builds, verifies the
  distributions and publishes through PyPI trusted publishing.
  `docs/*/releasing.md` describe the one-time setup; `tests/test_version.py`
  keeps `__version__` and `pyproject.toml` in step.
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
