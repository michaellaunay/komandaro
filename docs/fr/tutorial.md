# Tutoriel — d'une fonction à une commande annulable et multi-interface

*English version: [`docs/en/tutorial.md`](../en/tutorial.md)*

Dans ce tutoriel, vous écrivez la logique d'un petit **carnet de notes**
(une liste de notes) sous forme de commandes Komandaro, vous la pilotez
depuis Python, puis vous voyez une interface en ligne de commande générée
à partir d'elle. Le code final se trouve dans
[`examples/notebook/`](../../examples/notebook/) et il est couvert par la
suite de tests : tout ce qui suit s'exécute tel quel.

Chaque bloc de code est un doctest : `python -m pytest` l'exécute.

## 0. Installation

```bash
pip install "komandaro[dev]"
```

Python 3.12 ou plus récent. L'extra `[dev]` apporte `babel` (traductions)
et `pytest`.

## 1. Le contexte : l'état de votre application

Un **contexte** est l'objet, quel qu'il soit, qui porte l'état sur lequel
vos commandes agissent. Une dataclass, une session de base de données,
une racine de site Plone — Komandaro ne s'en préoccupe pas. Le nôtre est
une liste de notes :

```pycon
>>> from dataclasses import dataclass, field

>>> @dataclass
... class Notebook:
...     notes: list[str] = field(default_factory=list)

>>> nb = Notebook()

```

## 2. Une première commande : faire, défaire

Une commande est une **classe** construite à partir de deux fonctions :
l'une réalise l'opération et renvoie un résultat, l'autre l'annule. Les
deux reçoivent le contexte ; `undo` reçoit aussi le résultat de `do`.

```pycon
>>> from komandaro import SimpleCommandFactory
>>> from komandaro.i18n import _

>>> def add(notebook, text):
...     notebook.notes.append(text)
...     return len(notebook.notes)  # position de la nouvelle note

>>> def undo_add(notebook, position, text):
...     del notebook.notes[position - 1]

>>> Add = SimpleCommandFactory(add, undo_add, _("Add a note"), id="add")

```

`_("Add a note")` marque le nom comme traduisible (§8). `id="add"` est
l'identifiant stable que les frontaux utiliseront.

Pour exécuter la commande, on instancie la classe avec le contexte et les
paramètres, puis on appelle `execute()` :

```pycon
>>> cmd = Add(nb, text="Buy milk")
>>> cmd.execute()
1
>>> nb.notes
['Buy milk']
>>> cmd.undo()
>>> nb.notes
[]
>>> cmd.redo()
1

```

Les paramètres sont disponibles dans `cmd.params` ; le résultat de la
dernière exécution dans `cmd.result`.

### Une instance, une exécution

Une instance de commande ne s'exécute qu'une fois. Elle passe par trois
états — *prête*, *exécutée*, *annulée* — et refuse les appels qui ne
correspondent pas à son état :

```pycon
>>> from komandaro import CommandStateError
>>> cmd.is_ready, cmd.is_executed, cmd.is_undone
(False, True, False)
>>> try:
...     cmd.execute()
... except CommandStateError as error:
...     print(error)
Command Add a note has already been executed

```

Pour ajouter une autre note, on crée une autre instance :
`Add(nb, text="...")`. Chaque instance est la trace d'une action, ce dont
un historique d'annulation a précisément besoin.

## 3. Déclarer les paramètres avec un schéma

Jusqu'ici `Add` accepte n'importe quel mot-clé. Disons à Komandaro — et à
tout futur frontal — ce dont elle a besoin : un paramètre `text`, une
ligne non vide.

```pycon
>>> from zope.interface import Interface
>>> from zope.schema import TextLine

>>> class IText(Interface):
...     text = TextLine(title=_("Text"), description=_("Content of the note"), min_length=1)

>>> Add = SimpleCommandFactory(add, undo_add, _("Add a note"), schema=IText, id="add")

```

Les paramètres sont désormais **validés à la création de la commande**,
avant que quoi que ce soit ne s'exécute. Tous les problèmes sont signalés
ensemble :

```pycon
>>> from komandaro import ParameterError
>>> try:
...     Add(nb, text="", colour="red")
... except ParameterError as error:
...     for issue in error.issues:
...         print(issue.name, "->", issue)
colour -> Unknown parameter colour
text -> Invalid value for parameter text: Value is too short

```

Et le schéma **décrit** la commande, ce qu'une CLI transforme en options
et une page HTML en champs de formulaire :

```pycon
>>> from komandaro import describe
>>> for p in describe(Add.schema):
...     print(p.name, p.type, repr(p.title), p.required, p.python_type)
text TextLine 'Text' True <class 'str'>

```

## 4. Quand annuler demande plus que le résultat : le mémento

Renommer une note écrase l'ancien texte. Le résultat de `do` (le nouveau
texte) ne suffit pas pour annuler. Donnez à la fabrique une fonction
`snapshot` : elle s'exécute juste avant `do`, et sa valeur est transmise à
`undo` à la place du résultat.

```pycon
>>> from zope.schema import Int

>>> class IRename(Interface):
...     position = Int(title=_("Position"), min=1)
...     text = TextLine(title=_("New text"), min_length=1)

>>> def rename(notebook, position, text):
...     notebook.notes[position - 1] = text
...     return text

>>> def undo_rename(notebook, old_text, position, text):
...     notebook.notes[position - 1] = old_text

>>> def snapshot_rename(notebook, position, text):
...     return notebook.notes[position - 1]

>>> Rename = SimpleCommandFactory(
...     rename, undo_rename, _("Rename a note"), schema=IRename, snapshot=snapshot_rename, id="mv"
... )

>>> nb = Notebook(["Buy milk", "Call Bob"])
>>> cmd = Rename(nb, position=1, text="Buy oat milk")
>>> cmd.execute()
'Buy oat milk'
>>> cmd.memento
'Buy milk'
>>> cmd.undo()
>>> nb.notes
['Buy milk', 'Call Bob']

```

L'instantané est pris une seule fois, à la première exécution, si bien
que `redo()` restaure ensuite le même point de départ.

## 5. Écrire une commande sous forme de classe

La fabrique couvre la plupart des cas. Quand il vous faut davantage
(plusieurs méthodes, un `redo` particulier, de l'héritage), dérivez
`BaseCommand` et implémentez `_do`, `_undo`, éventuellement `_snapshot` et
`_redo`. Les méthodes publiques `execute`/`undo`/`redo` et la machine à
états sont fournies.

```pycon
>>> from komandaro import BaseCommand

>>> class Clear(BaseCommand):
...     id = "clear"
...     name = _("Clear the notebook")
...     description = _("Remove every note")
...
...     def _snapshot(self):
...         return list(self.context.notes)
...
...     def _do(self):
...         count = len(self.context.notes)
...         self.context.notes.clear()
...         return count
...
...     def _undo(self):
...         self.context.notes[:] = self.memento

>>> cmd = Clear(nb)
>>> cmd.execute()
2
>>> nb.notes
[]
>>> cmd.undo()
>>> nb.notes
['Buy milk', 'Call Bob']

```

## 6. Plusieurs commandes en une : la macro

Une `Macro` exécute des commandes enfants dans l'ordre et les annule dans
l'ordre inverse. Elle est **atomique** : si un enfant échoue, les enfants
déjà exécutés sont annulés avant que l'erreur ne se propage. Ici,
importer plusieurs notes constitue une seule action dans l'historique :

```pycon
>>> from komandaro import Macro
>>> from zope.schema import List

>>> class IImport(Interface):
...     notes = List(title=_("Notes"), value_type=TextLine(), min_length=1)

>>> class Import(Macro):
...     id = "import"
...     name = _("Import notes")
...     schema = IImport
...
...     def __init__(self, context, **params):
...         super().__init__(context, **params)
...         for text in self.params["notes"]:
...             self.add(Add(context, text=text))

>>> macro = Import(nb, notes=["Water plants", "Pay rent"])
>>> macro.execute()
[3, 4]
>>> nb.notes
['Buy milk', 'Call Bob', 'Water plants', 'Pay rent']
>>> macro.undo()
[None, None]
>>> nb.notes
['Buy milk', 'Call Bob']

```

## 7. Registre et invocateur : ce qu'un frontal utilise

Deux objets transforment un tas de classes de commandes en application :

* le **registre** est le catalogue : id → classe de commande, avec des
  groupes ;
* l'**invocateur** exécute les commandes sur un contexte, tient
  l'historique annuler/rétablir et prévient les observateurs.

```pycon
>>> from komandaro import Registry, Invoker

>>> registry = Registry()
>>> for cls in (Add, Rename, Import):
...     _entry = registry.register(cls, group="notes")
>>> _entry = registry.register(Clear, group="danger")
>>> registry.ids
['add', 'mv', 'import', 'clear']

>>> nb = Notebook()
>>> invoker = Invoker(nb, registry)
>>> invoker.run("add", text="Buy milk")
1
>>> invoker.run("add", text="Call Bob")
2
>>> invoker.run("mv", position=2, text="Call Alice")
'Call Alice'
>>> nb.notes
['Buy milk', 'Call Alice']
>>> invoker.undo()
>>> invoker.undo()
>>> nb.notes
['Buy milk']
>>> invoker.redo()
2
>>> [cmd.id for cmd in invoker.history]
['add', 'add']
>>> invoker.can_redo
True

```

Exécuter une nouvelle commande après une annulation vide la pile de
rétablissement, comme dans n'importe quel éditeur. Les erreurs sont typées
et traduisibles :

```pycon
>>> from komandaro import HistoryError, RegistryError
>>> invoker.run("add", text="x")
3
>>> invoker.can_redo
False
>>> try:
...     invoker.run("nope")
... except RegistryError as error:
...     print(error)
Unknown command nope

```

### Écouter ce qui se passe

Abonnez un gestionnaire pour recevoir un `Event` à chaque transition.
C'est ainsi qu'une interface rafraîchit son bouton *annuler*, ou qu'un
journal d'audit enregistre les actions :

```pycon
>>> log = []
>>> unsubscribe = invoker.subscribe(lambda e: log.append((e.kind.value, e.command.id)))
>>> invoker.undo()
>>> invoker.redo()
3
>>> log
[('undone', 'add'), ('redone', 'add')]
>>> unsubscribe()

```

## 8. Traduire noms, libellés et erreurs

Chaque chaîne enveloppée dans `_()` est un message gettext paresseux. Rien
n'est traduit tant qu'un frontal ne demande pas une langue — un même
processus serveur peut donc servir en même temps des utilisateurs
francophones et espérantophones.

La bibliothèque traduit ses propres messages (catalogues `en`, `fr`,
`eo`) :

```pycon
>>> from komandaro import translate
>>> try:
...     Add(nb, text="x").undo()
... except CommandStateError as error:
...     print(error.translate("fr"))
...     print(error.translate("eo"))
La commande Add a note ne peut pas être annulée dans son état actuel
La komando Add a note ne povas esti malfarita en sia nuna stato

```

Les messages de votre application vivent dans **leur propre domaine**.
Créez le marqueur une fois :

```python
from komandaro import make_gettext

_ = make_gettext("notebook")
```

puis extrayez, traduisez et compilez avec Babel :

```bash
pybabel extract -F babel.cfg -o locale/notebook.pot monappli/
pybabel init -i locale/notebook.pot -d locale -D notebook -l fr
# éditer locale/fr/LC_MESSAGES/notebook.po
pybabel compile -d locale -D notebook
```

et traduisez au moment du rendu avec `translate(message, "fr", localedir)`.
L'application d'exemple fait exactement cela : voir
[`examples/notebook/locale/`](../../examples/notebook/locale/).

```pycon
>>> from pathlib import Path
>>> from examples.notebook.notebook import Add as NotebookAdd
>>> localedir = Path("examples/notebook/locale")
>>> translate(NotebookAdd.name, "fr", localedir)
'Ajouter une note'
>>> translate(NotebookAdd.name, "de", localedir)  # pas de catalogue : l'identifiant du message
'Add a note'

```

## 9. Un frontal, (presque) gratuitement

Rien de ce qui précède ne mentionne un terminal ou un navigateur. Un
frontal n'a besoin que de **lire le registre** pour présenter les
commandes, et de **piloter l'invocateur** pour exécuter le choix de
l'utilisateur. [`examples/notebook/cli.py`](../../examples/notebook/cli.py)
le fait avec `argparse` en une centaine de lignes : une sous-commande par
entrée du registre, une option par `ParameterInfo`, `--help` traduit.

```pycon
>>> from examples.notebook.cli import Session
>>> session = Session(lang="en")
>>> session.run_line('add --text "Buy milk"')
[executed] Add a note
1
True
>>> session.run_line("mv --position 1 --text Milk")
[executed] Rename a note
Milk
True
>>> session.run_line("undo")
[undone] Rename a note
True
>>> session.run_line("list")
1. Buy milk
True

```

`lang="en"` fixe la langue des libellés. Sans lui, `Session()` suit la
locale de votre shell (`LANGUAGE`, `LC_ALL`, `LANG`) : sur une machine en
français, la même session affiche `[executed] Ajouter une note` — c'est la
fonctionnalité à l'œuvre, mais pas ce qu'un doctest peut attendre.

La même session en français :

```pycon
>>> Session(lang="fr").run_line("undo")
! Rien à annuler
True

```

Essayez-la de façon interactive :

```bash
python -m examples.notebook.cli --lang fr
```

La phase 3 de la feuille de route transforme ce pilote écrit à la main en
un `komandaro.cli` réutilisable, et ajoute des frontaux HTML, TUI et
JSON/MCP sur le même principe. Lisez [`how-it-works.md`](how-it-works.md)
pour les idées derrière chaque pièce, [`examples.md`](examples.md) pour
d'autres patrons et [`architecture.md`](architecture.md) pour la
conception.
