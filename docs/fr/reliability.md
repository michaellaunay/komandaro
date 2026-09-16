# Fiabilité, frontières de sécurité et migration

Cette page décrit les changements après 0.3.0. Ils restent non publiés jusqu'au
choix d'une nouvelle version par le mainteneur. Les signatures publiques changent
peu, mais plusieurs comportements auparavant acceptés sont désormais refusés.

## Une autorisation à chaque transition

Avec une politique, `Invoker.run`, `undo` et `redo` contrôlent le **sujet courant**
pour la commande racine et tous les descendants des `Macro` intégrées, avant les
callbacks execute/undo/redo. Un refus conserve les deux piles et émet `DENIED`
pour la commande refusée. Révoquer une permission peut donc rendre une ancienne
entrée d'annulation temporairement inaccessible ; son rétablissement permet de
réessayer. Ce choix durcit volontairement la règle 0.3.0 qui dispensait les
opérations d'historique de contrôle d'autorisation.

Tous les nœuds doivent référencer l'objet exact `Invoker.context` (`is`, non `==`).
Un arbre ne peut contenir ni cycle, ni instance répétée, ni descendant partagé.
Ces erreurs sont refusées avant exécution métier. Un composite personnalisé qui
n'hérite pas de `Macro` doit définir son propre contrat d'autorisation.

Une permission `IntFlag`/`Flag` n'implique que des valeurs de la **même énumération
concrète**. Un entier, un booléen ou une valeur numériquement égale d'une autre
énumération ne donne pas ce droit. Les valeurs simples et les hiérarchies de
classes conservent leurs règles habituelles.

Sans politique, **tout reste autorisé**. Les méthodes appelées directement sur
les commandes n'effectuent pas le contrôle de permissions. `Registry.allowed()`
est un filtre de présentation fondé sur les classes, pas une frontière de
sécurité : il ne voit ni les descendants construits, ni une permission propre à
l'instance. Constructeurs, politiques, schémas et fabriques de valeurs par défaut
doivent être fiables et sans effets de bord ; certains s'exécutent avant
l'autorisation. Les plugins enregistrés exécutent du Python : ce n'est pas un
bac à sable pour des objets ou du code non fiables.

Séparez les historiques par contexte et principal. Ne partagez pas un `subject`
mutable entre requêtes concurrentes. Une réparation administrative peut employer
une politique dédiée, explicitement autorisée par l'application ; elle ne doit
pas désactiver globalement les contrôles ou appeler directement undo pour le
compte d'un client non fiable.

## La compensation n'est pas une transaction

Chaque callback — notamment `_snapshot`, `_do`, `_undo`, `_redo` et les fonctions
de fabrique — doit réussir ou laisser le contexte applicatif inchangé s'il lève
une exception. Komandaro ne peut pas deviner les écritures partielles d'un
callback interrompu et les réparer. Transactions de base de données, idempotence
des appels externes, journal durable et reprise après crash restent applicatifs.

Une macro contrôle les états de tous ses descendants avant de commencer. En cas
d'échec, toutes les étapes **terminées** sont compensées dans l'ordre inverse.
Si un undo échoue, les annulations déjà terminées sont compensées par redo dans
l'ordre de réexécution. Une compensation réussie conserve l'état précédent de la
macro ; après un premier execute échoué, les enfants compensés redeviennent prêts
et leurs résultat/mémento sont effacés. La macro peut alors être réessayée. Redo
réutilise le snapshot de l'exécution réussie ; un nouvel essai d'execute en prend
un nouveau.

Si une compensation échoue, les suivantes sont néanmoins tentées. L'exception
initiale et toutes les erreurs de réparation sont conservées dans un
`BaseExceptionGroup` (`ExceptionGroup` si tous ses membres sont des exceptions
ordinaires). La macro fournit `IBrokenCommand`, expose `is_broken=True` et refuse
toute transition. Une macro imbriquée devenue inutilisable rend aussi son parent
inutilisable. L'application doit examiner les erreurs, réparer ou recharger le
contexte, puis recréer commandes et historique. **Ne forcez pas les marqueurs et
n'utilisez pas `_reset_ready()` comme API publique de réparation.**

Un run échoué n'entre pas dans l'historique. Un undo/redo échoué conserve son
entrée, même devenue inutilisable, pour ne pas supprimer les informations de
réparation. `can_undo` et `can_redo` indiquent seulement une pile non vide ; ils
ne garantissent ni les permissions, ni un état utilisable, ni le succès métier.

Les transitions préservent les interfaces Zope directement fournies qui sont
indépendantes de l'état, mais remplacent les marqueurs d'état et leurs
sous-interfaces.

## Réentrance, observateurs et concurrence

Une commande ne peut pas démarrer une seconde transition sur elle-même pendant
son exécution. Une macro ne peut pas être modifiée pendant une transition. Un
invocateur refuse run/undo/redo/clear imbriqués depuis un callback, une politique
ou un observateur tant que l'opération courante n'est pas terminée. Ces gardes
sont synchrones : **ce ne sont pas des verrous** et ils ne rendent pas le moteur
sûr en accès multithread ou asynchrone. Sérialisez extérieurement l'accès à
l'invocateur et à son contexte mutable.

Les observateurs reçoivent l'événement après mise à jour de l'historique d'une
transition réussie. Une `Exception` ordinaire d'observateur est journalisée par
`komandaro.invoker` ; les observateurs suivants restent appelés. Elle ne remplace
pas une exception métier et ne fait pas passer une opération réussie pour un
échec. Les gestionnaires de journaux doivent eux-mêmes être fiables.
`KeyboardInterrupt`, `SystemExit` et les autres `BaseException` de contrôle du
processus ne sont pas absorbées : elles peuvent parvenir à l'appelant alors que
l'historique a déjà été mis à jour.

Les observateurs sont des notifications, pas des hooks de commit. Ils ne doivent
pas modifier directement commande, paramètres, contexte ou historique. `Event`
est figé, mais `command` et `error` désignent des objets vivants : ce n'est pas
un enregistrement d'audit immuable. Persistez un instantané applicatif ou employez
un outbox transactionnel si la livraison doit être durable. Les abonnements de
l'événement courant sont pris en instantané ; le désabonnement est idempotent.

## Historique, défauts et identifiants

`limit=None` conserve un historique sans plafond ; `limit=0` ne retient aucune
nouvelle entrée d'annulation. Seuls les entiers positifs ou nuls sont acceptés,
à l'exclusion des booléens. La réduction intervient après run/redo réussi. Une
modification de `limit` s'applique au prochain enregistrement réussi ; elle ne
purge pas immédiatement les anciennes entrées des piles. Le plafond porte sur
le nombre d'entrées, pas sur la mémoire des contextes, paramètres ou mémentos.

Les conteneurs intégrés employés comme défauts statiques sont copiés profondément
lors de la validation ou de la description d'un champ. Les défauts de vocabulaire
`Choice` sont exclus de cette copie pour préserver leur identité. Les objets
applicatifs et retours de `defaultFactory` conservent aussi leur identité : la
fabrique doit créer une valeur mutable neuve quand une isolation est nécessaire.
Les paramètres explicitement fournis conservent leur identité ; ne les modifiez
pas après validation tant que la commande est utilisée dans l'historique.

L'alias d'enregistrement devient l'`id` de l'instance créée, sans modifier la
classe. Événements et politiques travaillant sur les instances voient donc
l'alias choisi. Un identifiant explicite de registre doit être une chaîne non
vide, pas uniquement des espaces.

Les générateurs de préférences linguistiques sont matérialisés une seule fois
pour les traductions imbriquées. `C`, `POSIX`, leurs variantes encodées et les
préférences vides ne bloquent pas le repli anglais. Les paramètres enregistrés
dans une exception priment sur les arguments de formatage homonymes de l'appelant.

## Construire et relire la modification

`hatch_build.py` compile automatiquement les catalogues de la bibliothèque pour
les roues, distributions sources et installations éditables. Babel est une
dépendance de construction, pas d'exécution. Le sdist contient hook, helper et
sources PO/POT pour reconstruire les MO. `python tools/check_catalogues.py`
vérifie les domaines de la bibliothèque et de l'exemple : identifiants complets,
contextes, pluriels et substitutions.

Exécutez `python -m pytest --cov`, `ruff check .`, `ruff format --check .`, `mypy`,
puis construisez les distributions et lancez `python tools/check_dist.py` et
`python tools/smoke_wheel.py`. Ce dernier télécharge les dépendances d'exécution
dans un environnement temporaire et importe la roue avec `python -I`. Le guide
[de publication](releasing.md) détaille étiquettes et protections nécessaires.

L'[audit daté](audit-2026-09-16.md) distingue les vérifications réellement faites
localement de celles qui restent à exécuter dans la CI complète. Ajouter une
matrice à la configuration ne prouve pas que ses nouveaux jobs sont déjà verts.

## Statut de la CLI de démonstration

L'exemple Notebook refuse les booléens ambigus et les guillemets non fermés.
Une commande ponctuelle renvoie 0 en cas de succès, 2 pour une erreur de syntaxe
ou d'arguments, et 1 pour une erreur métier connue. `--lang fr` et `--lang=fr`
sont acceptés ; une valeur absente est refusée. La session interactive conserve
ces erreurs sans quitter immédiatement. L'exemple n'est pas un frontal générique
pour tous les champs Zope et ne constitue pas un stockage persistant.
