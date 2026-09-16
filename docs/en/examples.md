# Examples

*Version française : [`docs/fr/examples.md`](../fr/examples.md)*

Short, self-contained patterns. Each block runs as a doctest. The complete
application example is [`examples/notebook/`](../../examples/notebook/)
(logic in `notebook.py`, generated command line in `cli.py`); the
[tutorial](tutorial.md) walks through it.

## A counter (the smallest possible command)

```pycon
>>> from komandaro import SimpleCommandFactory
>>> from komandaro.i18n import _

>>> class Counter:
...     value = 0

>>> def inc(counter):
...     counter.value += 1
...     return counter.value

>>> def dec(counter, result):
...     counter.value -= 1

>>> Increment = SimpleCommandFactory(inc, dec, _("Increment"))
>>> c = Counter()
>>> Increment(c).execute(), Increment(c).execute()
(1, 2)
>>> c.value
2

```

No schema, no parameters: the phase-1 style still works.

## A text buffer with insert/delete and a history

```pycon
>>> from zope.interface import Interface
>>> from zope.schema import Int, TextLine
>>> from komandaro import Invoker, Registry

>>> class Buffer:
...     def __init__(self):
...         self.text = ""

>>> class IInsert(Interface):
...     at = Int(title=_("Offset"), min=0)
...     text = TextLine(title=_("Text"), min_length=1)

>>> def insert(buf, at, text):
...     buf.text = buf.text[:at] + text + buf.text[at:]

>>> def undo_insert(buf, result, at, text):
...     buf.text = buf.text[:at] + buf.text[at + len(text) :]

>>> Insert = SimpleCommandFactory(insert, undo_insert, _("Insert"), schema=IInsert, id="insert")

>>> registry = Registry()
>>> _e = registry.register(Insert)
>>> buf = Buffer()
>>> editor = Invoker(buf, registry)
>>> editor.run("insert", at=0, text="world")
>>> editor.run("insert", at=0, text="hello ")
>>> buf.text
'hello world'
>>> editor.undo()
>>> buf.text
'world'
>>> editor.redo()
>>> buf.text
'hello world'

```

## Delete with a memento

Deleting a slice destroys information; capture it first.

```pycon
>>> class IDelete(Interface):
...     at = Int(title=_("Offset"), min=0)
...     length = Int(title=_("Length"), min=1)

>>> def delete(buf, at, length):
...     buf.text = buf.text[:at] + buf.text[at + length :]

>>> def undo_delete(buf, removed, at, length):
...     buf.text = buf.text[:at] + removed + buf.text[at:]

>>> def snapshot_delete(buf, at, length):
...     return buf.text[at : at + length]

>>> Delete = SimpleCommandFactory(
...     delete, undo_delete, _("Delete"), schema=IDelete, snapshot=snapshot_delete, id="delete"
... )
>>> _e = registry.register(Delete)
>>> editor.run("delete", at=0, length=6)
>>> buf.text
'world'
>>> editor.history[-1].memento
'hello '
>>> editor.undo()
>>> buf.text
'hello world'

```

## A bank transfer: two commands, one atomic action

If the deposit fails, the withdrawal is undone automatically.

```pycon
>>> from komandaro import Macro

>>> class Bank:
...     def __init__(self):
...         self.accounts = {"alice": 100, "bob": 0}
...         self.frozen = set()

>>> class IMove(Interface):
...     account = TextLine(title=_("Account"))
...     amount = Int(title=_("Amount"), min=1)

>>> def withdraw(bank, account, amount):
...     if bank.accounts[account] < amount:
...         raise ValueError("insufficient funds")
...     bank.accounts[account] -= amount

>>> def undo_withdraw(bank, result, account, amount):
...     bank.accounts[account] += amount

>>> def deposit(bank, account, amount):
...     if account in bank.frozen:
...         raise ValueError(f"{account} is frozen")
...     bank.accounts[account] += amount

>>> def undo_deposit(bank, result, account, amount):
...     bank.accounts[account] -= amount

>>> Withdraw = SimpleCommandFactory(withdraw, undo_withdraw, _("Withdraw"), schema=IMove)
>>> Deposit = SimpleCommandFactory(deposit, undo_deposit, _("Deposit"), schema=IMove)

>>> class ITransfer(Interface):
...     source = TextLine(title=_("From"))
...     target = TextLine(title=_("To"))
...     amount = Int(title=_("Amount"), min=1)

>>> class Transfer(Macro):
...     name = _("Transfer")
...     schema = ITransfer
...
...     def __init__(self, bank, **params):
...         super().__init__(bank, **params)
...         p = self.params
...         self.add(Withdraw(bank, account=p["source"], amount=p["amount"]))
...         self.add(Deposit(bank, account=p["target"], amount=p["amount"]))

>>> bank = Bank()
>>> Transfer(bank, source="alice", target="bob", amount=30).execute()
[None, None]
>>> bank.accounts
{'alice': 70, 'bob': 30}

>>> bank.frozen.add("bob")
>>> try:
...     Transfer(bank, source="alice", target="bob", amount=30).execute()
... except ValueError as error:
...     print(error)
bob is frozen
>>> bank.accounts  # the withdrawal was rolled back
{'alice': 70, 'bob': 30}

```

## Reporting validation errors in the user's language

```pycon
>>> from komandaro import ParameterError
>>> try:
...     Transfer(bank, source="alice", amount=0)
... except ParameterError as error:
...     for name, message in sorted(error.translate("fr").items()):
...         print(name, "->", message)
amount -> Valeur invalide pour le paramètre amount : Value is too small
target -> Paramètre obligatoire manquant : target

```

(The field-level text "Value is too small" comes from `zope.schema`, which
has its own catalogues; wiring them is on the roadmap.)

## An audit log from invoker events

```pycon
>>> from komandaro import EventKind
>>> audit = []
>>> registry = Registry()
>>> _e = registry.register(Withdraw, id="withdraw")
>>> invoker = Invoker(bank, registry)
>>> stop = invoker.subscribe(
...     lambda e: audit.append(f"{e.kind.value:8} {e.command.id} {e.command.params}")
... )
>>> invoker.run("withdraw", account="alice", amount=20)
>>> invoker.undo()
>>> try:
...     invoker.run("withdraw", account="bob", amount=999)
... except ValueError:
...     pass
>>> for line in audit:
...     print(line)
executed withdraw {'account': 'alice', 'amount': 20}
undone   withdraw {'account': 'alice', 'amount': 20}
failed   withdraw {'account': 'bob', 'amount': 999}
>>> stop()

```

`Event` also carries `error` (for `failed`) and a UTC timestamp `at`.

## A command class with a custom redo

```pycon
>>> from komandaro import BaseCommand

>>> class Stamp(BaseCommand):
...     """Append a stamp; redo appends a marker instead of repeating the stamp."""
...
...     name = _("Stamp")
...
...     def _do(self):
...         self.context.append("stamp")
...
...     def _undo(self):
...         self.context.pop()
...
...     def _redo(self):
...         self.context.append("stamp (redone)")

>>> trail = []
>>> s = Stamp(trail)
>>> s.execute()
>>> s.undo()
>>> s.redo()
>>> trail
['stamp (redone)']

```

## Loading commands from another package

In the contributing package's `pyproject.toml`:

```toml
[project.entry-points."myapp.commands"]
export = "otherpkg.commands:Export"
```

In the application:

```python
registry = Registry()
registry.load_entry_points("myapp.commands", registry_group="plugins")
```

The entry-point name becomes the command id.

## Discovering what a registry offers

```pycon
>>> from komandaro import describe, translate
>>> registry = Registry()
>>> _e = registry.register(Insert, group="edit")
>>> _e = registry.register(Delete, group="edit")
>>> _e = registry.register(Transfer, id="transfer", group="bank")
>>> for entry in registry:
...     params = ", ".join(f"{p.name}:{p.type}" for p in entry.parameters)
...     print(f"{entry.group:5} {entry.id:9} {translate(entry.name, 'en'):9} ({params})")
edit  insert    Insert    (at:Int, text:TextLine)
edit  delete    Delete    (at:Int, length:Int)
bank  transfer  Transfer  (source:TextLine, target:TextLine, amount:Int)
>>> sorted(registry.groups)
['bank', 'edit']

```

That table is the raw material of every front end.
