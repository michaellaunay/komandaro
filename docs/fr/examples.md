# Exemples

*English version: [`docs/en/examples.md`](../en/examples.md)*

Des patrons courts et autonomes. Chaque bloc s'exécute comme doctest.
L'application d'exemple complète est dans
[`examples/notebook/`](../../examples/notebook/) (logique dans
`notebook.py`, ligne de commande générée dans `cli.py`) ; le
[tutoriel](tutorial.md) la parcourt pas à pas.

## Un compteur (la plus petite commande possible)

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

Pas de schéma, pas de paramètres : le style de la phase 1 fonctionne toujours.

## Un tampon de texte avec insertion/suppression et historique

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

## Supprimer avec un mémento

Supprimer une tranche détruit de l'information ; capturez-la d'abord.

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

## Un virement bancaire : deux commandes, une action atomique

Si le dépôt échoue, le retrait est annulé automatiquement.

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
>>> bank.accounts  # le retrait a été annulé
{'alice': 70, 'bob': 30}

```

## Signaler les erreurs de validation dans la langue de l'utilisateur

```pycon
>>> from komandaro import ParameterError
>>> try:
...     Transfer(bank, source="alice", amount=0)
... except ParameterError as error:
...     for name, message in sorted(error.translate("fr").items()):
...         print(name, "->", message)
amount -> Valeur invalide pour le paramètre amount : Valeur trop petite
target -> Paramètre obligatoire manquant : target

```

La partie propre au champ (« Valeur trop petite ») est une erreur de
validation `zope.schema` associée à un identifiant de message Komandaro
(`field_too_small`) : elle est donc traduite comme le reste.

## Un journal d'audit à partir des événements de l'invocateur

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

`Event` porte aussi `error` (pour `failed`) et un horodatage UTC `at`.

## Une classe de commande avec un rétablissement particulier

```pycon
>>> from komandaro import BaseCommand

>>> class Stamp(BaseCommand):
...     """Ajoute un tampon ; redo ajoute un marqueur au lieu de répéter le tampon."""
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

## Charger des commandes depuis un autre paquet

Dans le `pyproject.toml` du paquet contributeur :

```toml
[project.entry-points."myapp.commands"]
export = "otherpkg.commands:Export"
```

Dans l'application :

```python
registry = Registry()
registry.load_entry_points("myapp.commands", registry_group="plugins")
```

Le nom de l'entry point devient l'identifiant de la commande.

## Découvrir ce qu'offre un registre

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

Ce tableau est la matière première de tout frontal.
