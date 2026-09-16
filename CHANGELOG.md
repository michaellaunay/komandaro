# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org).

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
