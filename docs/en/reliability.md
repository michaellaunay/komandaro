# Reliability, security boundaries and migration

This page describes the changes after 0.3.0. They are unreleased until the
maintainer selects a new version and publishes it. The public call signatures
remain largely unchanged; several previously accepted behaviours are rejected.

## Authorization is evaluated at each transition

With a policy, `Invoker.run`, `undo` and `redo` authorize the **current** subject
against the root command and every descendant of built-in `Macro` objects,
before calling execute/undo/redo callbacks. A denial leaves both history stacks
unchanged and emits `DENIED` for the refused command. Revoking a permission can
therefore make an existing undo entry temporarily inaccessible. Restoring the
permission allows a new attempt. This intentionally replaces 0.3.0's rule that
history operations bypassed authorization.

All nodes must reference the exact `Invoker.context` object (`is`, not `==`).
A tree cannot contain the same instance twice, share a descendant, or contain a
cycle. Those errors are rejected before business execution. A custom composite
that is not a `Macro` subclass must implement its own authorization contract.

`IntFlag`/`Flag` permissions imply only values of the **same concrete enum**.
An integer, boolean, or numerically equal member of another enum cannot grant
the permission. Flat values and class hierarchies retain their existing rules.

No policy still means **allow all**. Direct calls to command methods do not
perform authorization. `Registry.allowed()` is only a menu filter: it sees
class metadata, not runtime children or instance-specific permissions. Keep
constructors, policies and schema/default factories trusted and side-effect-free;
they may execute before authorization. Registered plugins are Python code, not
a sandbox. Do not expose these facilities directly to untrusted Python objects.

Use separate histories for separate contexts and principals. Never share a mutable
`subject` across concurrent requests. A service may use a dedicated administrative
policy for recovery; it must authorize that operation itself instead of disabling
checks globally or calling undo directly on behalf of an untrusted client.

## Compensation is not a transaction

Each callback, including `_snapshot`, `_do`, `_undo`, `_redo` and factory functions,
must either succeed or leave the application context unchanged when it raises.
Komandaro cannot infer or undo writes performed by a callback that fails halfway.
Database transactions, external API idempotency, durable logs and crash recovery
belong to the application.

For a built-in macro, the entire descendant lifecycle is checked before a
transition. On failure, every **completed** step is compensated in reverse order.
On a failed undo, the completed undos are compensated with redo in forward order.
If recovery succeeds, the macro stays in its previous state; after a failed
initial execute, compensated children return to ready and their result/memento
is cleared. The failed macro may then be retried. A redo still uses the original
successful snapshot; a fresh execute attempt takes a new snapshot.

If compensation fails, all remaining compensations are still attempted. The
original exception and every compensation exception are preserved in a
`BaseExceptionGroup` (an `ExceptionGroup` when all members are ordinary exceptions).
The macro provides `IBrokenCommand`, exposes `is_broken=True` and rejects all
further transitions. A broken nested macro also makes its containing macro broken.
The application must inspect the errors, repair or reload its context explicitly,
and construct fresh commands/history. **Do not force state markers or call the
private `_reset_ready()` helper as a public recovery API.**

A failed run is not added to history. Failed undo/redo leave the stack entries in
place, including a now-broken command, so recovery information is not discarded.
`can_undo` and `can_redo` mean only that the corresponding stack is nonempty;
they do not promise permission, a usable command state, or callback success.

State transitions preserve unrelated directly provided Zope interfaces while
replacing state markers, including subinterfaces of those markers.

## Reentrancy, observers and concurrency

A command cannot start another transition on itself while it is running. A macro
cannot be edited during a transition. An invoker rejects nested run/undo/redo/clear
from callbacks, policies and observers while its operation is in progress. These
are synchronous reentrancy guards, **not locks** and not thread/async safety.
Serialize access to both the invoker and its mutable context externally.

Observers run after a successful transition has updated history. An observer's
ordinary `Exception` is logged through `komandaro.invoker`, and later observers
still receive the event. It cannot turn a successful operation into a reported
business failure or replace the exception from a failed callback. Logging handlers
must themselves be reliable. `KeyboardInterrupt`, `SystemExit` and other
process-control `BaseException`s are not swallowed: the caller may receive one
after history has already been updated.

Observers are notifications, not commit hooks. They must not mutate the command,
its parameters, the context or the history directly. `Event` is frozen, but its
`command` and `error` refer to live objects; events are not immutable audit records.
Persist an application-defined snapshot or use a transactional outbox when delivery
must be durable. Dispatch snapshots subscriptions for the current event; repeated
calls to a registration's unsubscribe function are harmless.

## History, defaults and identifiers

`limit=None` retains an unbounded undo history; `limit=0` retains no new undo entries.
Only nonnegative integers are accepted (booleans are rejected). Oldest undo entries
are dropped after a successful run or redo. Changing the limit affects the next
successful record; it does not immediately evict existing undo or redo entries.
This limits entry count, not memory occupied by contexts, parameters or mementos.

Static built-in container defaults are deeply copied when completing parameters
or describing a field, except vocabulary `Choice` defaults, whose identity must
be preserved. Object defaults and `defaultFactory` return values retain their
identity. Factories own their allocation policy and should create a fresh mutable
value when isolation is needed. Explicit user parameters retain their identity;
do not mutate them after validation while their command remains in history.

A registry alias becomes the created instance's `id`; the command class is not
modified. Events and instance-level policies consequently see the selected alias.
Explicit registry identifiers must be nonempty strings, not whitespace-only values.

Locale preference generators are materialized once for nested translations.
`C`, `POSIX`, their encoded variants and empty preferences do not suppress the
English fallback. Stored exception parameters take precedence over conflicting
formatting arguments supplied by a caller.

## Building and reviewing the change

`hatch_build.py` compiles the library catalogues automatically for wheel, source and
editable builds. Babel is a build dependency, not a runtime dependency. A source
distribution includes the hook, its helper and PO/POT sources; it can regenerate
all MO files. `python tools/check_catalogues.py` checks both the library and notebook
example domains, full identifiers and translation placeholders.

Run `python -m pytest --cov`, `ruff check .`, `ruff format --check .`, `mypy`, then
build distributions and run `python tools/check_dist.py` and
`python tools/smoke_wheel.py`. The smoke check downloads runtime dependencies into
a temporary virtual environment and imports the installed wheel with `python -I`.
See [releasing](releasing.md) for production tags and environment protections.

The dated [audit](../fr/audit-2026-09-16.md) records what was actually verified
locally and what still requires the complete CI environment. CI configuration is
not evidence that its new jobs have already passed.

## Demonstration CLI exit status

The Notebook example rejects ambiguous booleans and unterminated quoting.
One-shot commands return 0 on success, 2 for syntax/argument errors, and 1 for
known business failures. Both `--lang fr` and `--lang=fr` are supported; a missing
value is rejected. Interactive sessions survive these input errors. The example
is not a generic front end for every Zope field and is not persistent storage.
