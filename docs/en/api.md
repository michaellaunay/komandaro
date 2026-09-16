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
| `permission: Any` | what a subject must hold to run the command; `None` = public |

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

Composite command. Children must be distinct instances in an acyclic tree.
`add(cmd)` / `remove(cmd)` are allowed while ready and idle; `commands` is a
tuple. Execute/redo run in order; undo runs in reverse. On failure, completed
steps are compensated and all compensation errors are retained. Successful
compensation restores a retryable state; otherwise the macro is broken
(`is_broken`, `IBrokenCommand`). This is not a transaction. Subclasses may
build children from validated `self.params`. See [reliability](reliability.md).

### `CommandStateError(message, **params)`

`RuntimeError`; `str()` renders in the process language;
`translate(language, localedir=None)` selects an explicit language.

## Interfaces — `komandaro.interfaces`

`IContext` (optional marker, never checked), `IBaseCommand` (`id`, `name`,
`description`, `schema`, `permission`, `context`, `params`, `result`,
`memento`).
States, provided directly on instances: `ICommand` (`execute`),
`IExecutedCommand` (`undo`), `IUndoneCommand` (`redo`),
`IBrokenCommand` (no permitted transition; application recovery required).
Kinds, declared on classes: `ISimpleCommand` (`do_it`, `undo_it`,
`snapshot_it`), `IMacro` (`commands`, `add`, `remove`).
Collaborators: `IEntry`, `IRegistry`, `IInvoker`, `IEvent`,
`IPermissionPolicy` (`implies`, `permits`). Every implementation is
verified against its interface by `tests/test_interfaces.py`.

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
`describe_error(error) → Message` maps a `zope.schema` validation error to
an identifier (`FIELD_ERRORS`: `field_too_short`, `field_too_long`,
`field_too_small`, `field_too_big`, `field_wrong_contained_type`,
`field_wrong_type`, `field_required_missing`,
`field_constraint_not_satisfied`, `field_not_unique`, `field_invalid_value`;
anything else `field_invalid`).

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
| `allowed(policy, subject) → list[Entry]` | entries the subject may run (all when `policy` is None) |
| `create(id, context, **params) → BaseCommand` | instantiate |

`Entry` (frozen dataclass): `id`, `command`, `group`, `tags`; properties
`name`, `description`, `permission`, `parameters` (= `describe(command.schema)`).

`RegistryError(message, **params)` (`LookupError`): unknown or duplicate
id; `translate(language)`.

## Invoker — `komandaro.invoker`

### `Invoker(context, registry=None, *, limit=None, policy=None, subject=None)`

| member | role |
|---|---|
| `run(command_or_id, /, **params) → result` | execute and record; `params` only with an id |
| `undo() → value`, `redo() → result` | move between the two stacks |
| `clear()` | forget the history |
| `create(id, **params) → BaseCommand` | instantiate via the registry without running |
| `subscribe(handler) → unsubscribe` | observe `Event`s |
| `history`, `undone` (tuples, oldest first), `can_undo`, `can_redo`, `len`, iteration | introspection |

`limit` accepts `None` (unbounded), zero, or a positive integer; booleans and
invalid values are rejected before execution. Trimming occurs after successful
run/redo; changing the limit does not immediately trim existing stacks.
With a policy, **run, undo and redo** authorize the current subject and every
macro descendant before any business callback. Refusal raises
`PermissionDeniedError` and emits `denied` for the refused child. All contexts
must be the identical object owned by the invoker. Isolate histories per
context and principal; `can_undo`/`can_redo` only indicate nonempty stacks.
Ordinary observer exceptions are logged, not propagated; process-control
exceptions still propagate after successful transitions have been recorded.
Reentrant run/undo/redo/clear raises `HistoryError`. See [reliability](reliability.md).

`Event` (frozen dataclass): `kind: EventKind`, `command`, `error`, `at`
(UTC). `EventKind`: `EXECUTED`, `UNDONE`, `REDONE`, `FAILED`, `DENIED`,
`CLEARED`.

A failed `run` is not recorded; a failed `undo`/`redo` leaves the command
where it was. `HistoryError` (`RuntimeError`) when there is nothing to
undo/redo or no registry; `translate(language)`.

## Permissions — `komandaro.permissions`

| name | role |
|---|---|
| `SubjectPermissionsPolicy(held=default_held, implies=default_implies)` | the default policy: permits when one permission the subject holds implies the required one |
| `AllowAll()` | permits everything |
| `default_held(subject)` | `None` → nothing; `subject.permissions` if present; a bare iterable, flag, name or class → itself |
| `default_implies(held, required)` | equality; `held & required == required` for `Flag`s; `issubclass(held, required)` for classes (diamond inheritance works); `isinstance(held, required)` |
| `PermissionDeniedError(command_id, permission, subject=None)` | raised by the invoker; `translate(language)` |
| `describe_permission(permission) → str` | readable name of a permission of any model |
| `Policy` | `typing.Protocol` mirror of `IPermissionPolicy` for type checkers |

Permissions themselves are opaque to Komandaro: strings, `IntFlag` members,
classes of a hierarchy — the policy alone gives them meaning.

## Internationalisation — `komandaro.i18n`

| name | role |
|---|---|
| `Message(msgid, domain=DOMAIN)` | lazy translatable `str` subclass; `localize(language, localedir=None, **params)` substitutes `${name}` placeholders and translates `Message` parameters first |
| `make_gettext(domain, localedir=None) → _` | build a marker function for your domain, binding its catalogue directory |
| `bind_domain(domain, localedir)` | declare where a domain's catalogues live (`LOCALEDIRS`) |
| `_` | the library's own marker (domain `komandaro`) |
| `translate(message, language=None, localedir=None) → str` | translate a `Message` (plain `str` returned unchanged); tries the language, then English, then returns the identifier |
| `environment_languages(environ=None) → list[str]` | languages of the process (`LANGUAGE`, `LC_ALL`, `LC_MESSAGES`, `LANG`) |
| `DOMAIN`, `DEFAULT_LOCALEDIR`, `FALLBACK_LANGUAGE`, `LOCALEDIRS` | `"komandaro"`, the package's `locale/`, `"en"`, the domain → directory map |

Message ids are `snake_case` identifiers (`command_already_executed`);
the English text lives in the `en` catalogue. `language` may be a code
(`"fr"`), a preference list (`["fr_FR", "de"]`) or `None` (process
environment). Catalogues are `<localedir>/<lang>/LC_MESSAGES/<domain>.mo`,
compiled from `.po` files with `pybabel compile`.

## Errors at a glance

| error | raised by | base |
|---|---|---|
| `CommandStateError` | execute/undo/redo in the wrong state, macro modified after execution | `RuntimeError` |
| `ParameterError` | command instantiation with bad parameters | `ValueError` |
| `RegistryError` | unknown or duplicate id | `LookupError` |
| `HistoryError` | nothing to undo/redo, no registry | `RuntimeError` |
| `PermissionDeniedError` | the policy refused a command | `RuntimeError` |

All five have `translate(language)`; `str()` gives the message in the
language of the process (English when it has none).

## Reliability and migration

See [failure, permission, defaults and observer contracts](reliability.md).
