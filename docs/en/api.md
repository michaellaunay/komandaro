# API reference

*Version française : [`docs/fr/api.md`](../fr/api.md)*

Everything below is importable from `komandaro` unless a module is named.
Signatures are abbreviated; docstrings in the source are authoritative.

## Commands — `komandaro.command`

### `BaseCommand(context, **params)`

Abstract base of every command. Class attributes describe the command:

| attribute | meaning |
|---|---|
| `id: str` | stable identifier (default: lower-cased class name without `Command`) |
| `name: Message` | translatable short name |
| `description: Message` | translatable description |
| `schema: Interface \| None` | parameter schema; `None` accepts anything |

Instance attributes: `context`, `params` (validated), `result` (last
execute/redo), `memento` (value of `_snapshot()`, taken once).

| method / property | state required | effect |
|---|---|---|
| `execute() → result` | ready | `_snapshot()`, then `_do()`; becomes executed |
| `undo() → value` | executed | `_undo()`; becomes undone |
| `redo() → result` | undone | `_redo()` (default: `_do()`); becomes executed |
| `is_ready`, `is_executed`, `is_undone` | — | current state |

Hooks for subclasses: `_snapshot()` (default `None`), `_do()`, `_undo()`,
`_redo()`.

Raises `CommandStateError` when a method is called in the wrong state.

### `SimpleCommandFactory(do, undo, name, description="", class_name=None, *, schema=None, snapshot=None, id=None) → type[SimpleCommand]`

Builds a command **class** from functions:

* `do(context, **params) → result`
* `undo(context, state, **params)` where *state* is the memento when
  `snapshot` is given, the result otherwise
* `snapshot(context, **params) → memento` (optional)

### `SimpleCommand`

The base class returned by the factory; `do_it`, `undo_it`, `snapshot_it`
are static methods.

### `Macro(context, commands=(), name=None, description=None, **params)`

Composite command. `commands` are child *instances*. `add(cmd)` /
`remove(cmd)` while ready; `commands` property (tuple). Execution and redo
are atomic (children already run are undone on failure); undo runs in
reverse order. Subclasses may declare a `schema` and build children from
`self.params`.

### `CommandStateError(message, **params)`

`RuntimeError`; `str()` gives the message id, `translate(language,
localedir=None)` the localised text.

## Interfaces — `komandaro.interfaces`

`IContext`, `IBaseCommand` (name, description, context, result).
States, provided directly on instances: `ICommand` (`execute`),
`IExecutedCommand` (`undo`), `IUndoneCommand` (`redo`).
Kinds, declared on classes: `ISimpleCommand`, `IMacro` (`commands`,
`add`, `remove`).

## Schemas — `komandaro.schema`

| name | role |
|---|---|
| `validate(schema, params) → dict` | applies defaults, checks every field; raises `ParameterError` |
| `describe(schema) → list[ParameterInfo]` | ordered description for front ends |
| `fields(schema) → list[(name, field)]` | raw `zope.schema` fields in order |
| `is_schema(obj) → bool` | whether *obj* can be used as a schema |

`ParameterInfo` (frozen dataclass): `name`, `type` (field class name, e.g.
`"Int"`), `title`, `description`, `required`, `default`, `choices` (for
`Choice` fields), `field` (the `zope.schema` object), `python_type`.

`ParameterError(issues)` (`ValueError`): `issues: list[ParameterIssue]`;
`translate(language) → {name: text}`.
`ParameterIssue`: `name`, `message`, `params`; `translate(language)`.

## Registry — `komandaro.registry`

### `Registry()`

| member | role |
|---|---|
| `register(command, *, id=None, group=None, tags=(), replace=False) → Entry` | add a command class |
| `command(id=None, *, group=None, tags=())` | class decorator doing the same |
| `unregister(id)` | remove |
| `load_entry_points(group, *, registry_group=None) → list[Entry]` | register classes from `importlib.metadata` entry points; the entry-point name is the id |
| `get(id) → Entry`, `registry[id] → class`, `id in registry`, `len`, iteration (ordered) | lookup |
| `ids`, `groups → {group: [Entry]}`, `find(group=None, tag=None)` | browsing |
| `create(id, context, **params) → BaseCommand` | instantiate |

`Entry` (frozen dataclass): `id`, `command`, `group`, `tags`; properties
`name`, `description`, `parameters` (= `describe(command.schema)`).

`RegistryError(message, **params)` (`LookupError`): unknown or duplicate
id; `translate(language)`.

## Invoker — `komandaro.invoker`

### `Invoker(context, registry=None, *, limit=None)`

| member | role |
|---|---|
| `run(command_or_id, /, **params) → result` | execute and record; `params` only with an id |
| `undo() → value`, `redo() → result` | move between the two stacks |
| `clear()` | forget the history |
| `create(id, **params) → BaseCommand` | instantiate via the registry without running |
| `subscribe(handler) → unsubscribe` | observe `Event`s |
| `history`, `undone` (tuples, oldest first), `can_undo`, `can_redo`, `len`, iteration | introspection |

`limit` caps the undo stack (oldest entries are dropped).

`Event` (frozen dataclass): `kind: EventKind`, `command`, `error`, `at`
(UTC). `EventKind`: `EXECUTED`, `UNDONE`, `REDONE`, `FAILED`, `CLEARED`.

A failed `run` is not recorded; a failed `undo`/`redo` leaves the command
where it was. `HistoryError` (`RuntimeError`) when there is nothing to
undo/redo or no registry; `translate(language)`.

## Internationalisation — `komandaro.i18n`

| name | role |
|---|---|
| `Message(msgid, domain=DOMAIN)` | lazy translatable `str` subclass; `localize(language, localedir=None, **params)` |
| `make_gettext(domain) → _` | build a marker function for your domain |
| `_` | the library's own marker (domain `komandaro`) |
| `translate(message, language=None, localedir=None) → str` | translate a `Message` (plain `str` returned unchanged); falls back to the message id |
| `DOMAIN`, `DEFAULT_LOCALEDIR` | `"komandaro"`, the package's `locale/` directory |

`language` may be a code (`"fr"`), a preference list (`["fr_FR", "en"]`)
or `None` (process environment). Catalogues are
`<localedir>/<lang>/LC_MESSAGES/<domain>.mo`, compiled from `.po` files
with `pybabel compile`.

## Errors at a glance

| error | raised by | base |
|---|---|---|
| `CommandStateError` | execute/undo/redo in the wrong state, macro modified after execution | `RuntimeError` |
| `ParameterError` | command instantiation with bad parameters | `ValueError` |
| `RegistryError` | unknown or duplicate id | `LookupError` |
| `HistoryError` | nothing to undo/redo, no registry | `RuntimeError` |

All four have `translate(language)`; `str()` gives the untranslated
message.
