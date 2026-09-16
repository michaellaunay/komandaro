# Référence de l'API

*English version: [`docs/en/api.md`](../en/api.md)*

Tout ce qui suit s'importe depuis `komandaro`, sauf mention d'un module.
Les signatures sont abrégées ; les docstrings du code source font foi.

## Commandes — `komandaro.command`

### `BaseCommand(context, **params)`

Base abstraite de toute commande. Les attributs de classe décrivent la
commande :

| attribut | signification |
|---|---|
| `id: str` | identifiant stable (défaut : nom de classe en minuscules sans `Command`) |
| `name: Message` | nom court traduisible |
| `description: Message` | description traduisible |
| `schema: Interface \| None` | schéma des paramètres ; `None` accepte tout |
| `permission: Any` | ce qu'un sujet doit détenir pour exécuter la commande ; `None` = publique |

Attributs d'instance : `context`, `params` (validés), `result` (dernier
execute/redo), `memento` (valeur de `_snapshot()`, prise une fois).

| méthode / propriété | état requis | effet |
|---|---|---|
| `execute() → result` | prête | `_snapshot()`, puis `_do()` ; devient exécutée |
| `undo() → value` | exécutée | `_undo()` ; devient annulée |
| `redo() → result` | annulée | `_redo()` (défaut : `_do()`) ; devient exécutée |
| `is_ready`, `is_executed`, `is_undone` | — | état courant |

Crochets pour les sous-classes : `_snapshot()` (défaut `None`), `_do()`,
`_undo()`, `_redo()`.

Lève `CommandStateError` quand une méthode est appelée dans le mauvais
état.

### `SimpleCommandFactory(do, undo, name, description="", class_name=None, *, schema=None, snapshot=None, id=None) → type[SimpleCommand]`

Construit une **classe** de commande à partir de fonctions :

* `do(context, **params) → result`
* `undo(context, state, **params)` où *state* est le mémento si
  `snapshot` est fourni, le résultat sinon
* `snapshot(context, **params) → memento` (optionnel)

### `SimpleCommand`

La classe de base renvoyée par la fabrique ; `do_it`, `undo_it`,
`snapshot_it` sont des méthodes statiques.

### `Macro(context, commands=(), name=None, description=None, **params)`

Commande composite. `commands` sont des *instances* enfants. `add(cmd)` /
`remove(cmd)` tant qu'elle est prête ; propriété `commands` (tuple).
L'exécution et le rétablissement sont atomiques (les enfants déjà
exécutés sont annulés en cas d'échec) ; l'annulation se fait en ordre
inverse. Les sous-classes peuvent déclarer un `schema` et construire leurs
enfants à partir de `self.params`.

### `CommandStateError(message, **params)`

`RuntimeError` ; `str()` donne l'identifiant du message,
`translate(language, localedir=None)` le texte localisé.

## Interfaces — `komandaro.interfaces`

`IContext` (marqueur optionnel, jamais vérifié), `IBaseCommand` (`id`,
`name`, `description`, `schema`, `permission`, `context`, `params`,
`result`, `memento`).
États, fournis directement sur les instances : `ICommand` (`execute`),
`IExecutedCommand` (`undo`), `IUndoneCommand` (`redo`).
Genres, déclarés sur les classes : `ISimpleCommand` (`do_it`, `undo_it`,
`snapshot_it`), `IMacro` (`commands`, `add`, `remove`).
Collaborateurs : `IEntry`, `IRegistry`, `IInvoker`, `IEvent`,
`IPermissionPolicy` (`implies`, `permits`). Chaque implémentation est
vérifiée contre son interface par `tests/test_interfaces.py`.

## Schémas — `komandaro.schema`

| nom | rôle |
|---|---|
| `validate(schema, params) → dict` | applique les défauts, vérifie chaque champ ; lève `ParameterError` |
| `describe(schema) → list[ParameterInfo]` | description ordonnée pour les frontaux |
| `fields(schema) → list[(name, field)]` | champs `zope.schema` bruts, dans l'ordre |
| `is_schema(obj) → bool` | si *obj* peut servir de schéma |

`ParameterInfo` (dataclass figée) : `name`, `type` (nom de la classe de
champ, p. ex. `"Int"`), `title`, `description`, `required`, `default`,
`choices` (champs `Choice`), `field` (l'objet `zope.schema`),
`python_type`.

`ParameterError(issues)` (`ValueError`) : `issues: list[ParameterIssue]` ;
`translate(language) → {name: texte}`.
`ParameterIssue` : `name`, `message`, `params` ; `translate(language)`.
`describe_error(error) → Message` associe une erreur de validation
`zope.schema` à un identifiant (`FIELD_ERRORS` : `field_too_short`,
`field_too_long`, `field_too_small`, `field_too_big`,
`field_wrong_contained_type`, `field_wrong_type`, `field_required_missing`,
`field_constraint_not_satisfied`, `field_not_unique`, `field_invalid_value` ;
sinon `field_invalid`).

## Registre — `komandaro.registry`

### `Registry()`

| membre | rôle |
|---|---|
| `register(command, *, id=None, group=None, tags=(), replace=False) → Entry` | ajouter une classe de commande |
| `command(id=None, *, group=None, tags=())` | décorateur de classe équivalent |
| `unregister(id)` | retirer |
| `load_entry_points(group, *, registry_group=None) → list[Entry]` | enregistrer les classes exposées par des entry points `importlib.metadata` ; le nom de l'entry point devient l'id |
| `get(id) → Entry`, `registry[id] → classe`, `id in registry`, `len`, itération (ordonnée) | consultation |
| `ids`, `groups → {groupe: [Entry]}`, `find(group=None, tag=None)` | parcours |
| `allowed(policy, subject) → list[Entry]` | entrées que le sujet peut exécuter (toutes si `policy` vaut None) |
| `create(id, context, **params) → BaseCommand` | instancier |

`Entry` (dataclass figée) : `id`, `command`, `group`, `tags` ; propriétés
`name`, `description`, `permission`, `parameters` (= `describe(command.schema)`).

`RegistryError(message, **params)` (`LookupError`) : id inconnu ou en
double ; `translate(language)`.

## Invocateur — `komandaro.invoker`

### `Invoker(context, registry=None, *, limit=None, policy=None, subject=None)`

| membre | rôle |
|---|---|
| `run(command_or_id, /, **params) → result` | exécuter et enregistrer ; `params` seulement avec un id |
| `undo() → value`, `redo() → result` | déplacer entre les deux piles |
| `clear()` | oublier l'historique |
| `create(id, **params) → BaseCommand` | instancier via le registre sans exécuter |
| `subscribe(handler) → unsubscribe` | observer les `Event` |
| `history`, `undone` (tuples, du plus ancien au plus récent), `can_undo`, `can_redo`, `len`, itération | introspection |

`limit` plafonne la pile d'annulation (les entrées les plus anciennes sont
abandonnées). Avec une `policy`, `run` vérifie d'abord
`policy.permits(subject, command.permission, command)` et lève
`PermissionDeniedError` (événement `denied`) en cas de refus ; `subject`
est un simple attribut, réassignable par requête ou par session. Annuler
et rétablir ne sont jamais revérifiés.

`Event` (dataclass figée) : `kind: EventKind`, `command`, `error`, `at`
(UTC). `EventKind` : `EXECUTED`, `UNDONE`, `REDONE`, `FAILED`, `DENIED`,
`CLEARED`.

Un `run` qui échoue n'est pas enregistré ; un `undo`/`redo` qui échoue
laisse la commande où elle était. `HistoryError` (`RuntimeError`) quand il
n'y a rien à annuler/rétablir ou pas de registre ; `translate(language)`.

## Permissions — `komandaro.permissions`

| nom | rôle |
|---|---|
| `SubjectPermissionsPolicy(held=default_held, implies=default_implies)` | la politique par défaut : autorise quand une permission détenue par le sujet implique la permission requise |
| `AllowAll()` | autorise tout |
| `default_held(subject)` | `None` → rien ; `subject.permissions` si présent ; un itérable, un drapeau, un nom ou une classe nus → eux-mêmes |
| `default_implies(held, required)` | égalité ; `held & required == required` pour les `Flag` ; `issubclass(held, required)` pour les classes (l'héritage en losange fonctionne) ; `isinstance(held, required)` |
| `PermissionDeniedError(command_id, permission, subject=None)` | levée par l'invocateur ; `translate(language)` |
| `describe_permission(permission) → str` | nom lisible d'une permission, quel que soit le modèle |
| `Policy` | miroir `typing.Protocol` de `IPermissionPolicy` pour les vérificateurs de types |

Les permissions elles-mêmes sont opaques pour Komandaro : chaînes, membres
d'`IntFlag`, classes d'une hiérarchie — seule la politique leur donne un
sens.

## Internationalisation — `komandaro.i18n`

| nom | rôle |
|---|---|
| `Message(msgid, domain=DOMAIN)` | sous-classe de `str` traduisible paresseusement ; `localize(language, localedir=None, **params)` substitue les espaces réservés `${name}` et traduit d'abord les paramètres qui sont des `Message` |
| `make_gettext(domain, localedir=None) → _` | construit une fonction marqueur pour votre domaine, en liant le répertoire de ses catalogues |
| `bind_domain(domain, localedir)` | déclare où vivent les catalogues d'un domaine (`LOCALEDIRS`) |
| `_` | le marqueur de la bibliothèque (domaine `komandaro`) |
| `translate(message, language=None, localedir=None) → str` | traduit un `Message` (une `str` ordinaire est renvoyée telle quelle) ; essaie la langue, puis l'anglais, puis renvoie l'identifiant |
| `environment_languages(environ=None) → list[str]` | langues du processus (`LANGUAGE`, `LC_ALL`, `LC_MESSAGES`, `LANG`) |
| `DOMAIN`, `DEFAULT_LOCALEDIR`, `FALLBACK_LANGUAGE`, `LOCALEDIRS` | `"komandaro"`, le `locale/` du paquet, `"en"`, la table domaine → répertoire |

Les identifiants de message sont en `snake_case`
(`command_already_executed`) ; le texte anglais vit dans le catalogue `en`.
`language` peut être un code (`"fr"`), une liste de préférences
(`["fr_FR", "de"]`) ou `None` (environnement du processus). Les
catalogues sont `<localedir>/<lang>/LC_MESSAGES/<domain>.mo`, compilés
depuis les `.po` avec `pybabel compile`.

## Les erreurs en un coup d'œil

| erreur | levée par | base |
|---|---|---|
| `CommandStateError` | execute/undo/redo dans le mauvais état, macro modifiée après exécution | `RuntimeError` |
| `ParameterError` | instanciation d'une commande avec de mauvais paramètres | `ValueError` |
| `RegistryError` | id inconnu ou en double | `LookupError` |
| `HistoryError` | rien à annuler/rétablir, pas de registre | `RuntimeError` |
| `PermissionDeniedError` | la politique a refusé une commande | `RuntimeError` |

Les cinq ont `translate(language)` ; `str()` donne le message dans la
langue du processus (l'anglais s'il n'en a pas).
