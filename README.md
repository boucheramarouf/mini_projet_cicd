# Pipeline d'integration continue — transactions financieres

Projet pedagogique couvrant les niveaux 1 et 2, plus une livraison continue niveau 3 : le workflow GitHub Actions peut deployer automatiquement l'application sur une VM Linux via SSH et Docker Compose. Un dashboard Grafana est egalement provisionne avec les services.

## Architecture

```text
CSV deterministes -> LocalStack S3 (service local compatible S3) -> chargement/validation
                 -> transformations Python pures -> PostgreSQL
                 -> tests d'integration
```

Le generateur produit deux CSV de cinq transactions chacun. Les montants, IBAN, banques et dates sont stables, afin que les resultats soient reproductibles. Chaque transaction contient une date, les IBAN et pays source/destination, la banque source et le montant.

Les traitements calculent les sommes envoyees par IBAN d'origine et par banque, les sommes recues par IBAN, et le drapeau `is_over_5000` (strictement superieur a 5 000). Les fonctions de traitement ne font ni lecture de fichier, ni acces reseau ou base de donnees.

## Lancer avec Docker

Prerequis : Docker Desktop avec Docker Compose.

```powershell
docker compose up -d postgres localstack grafana
docker compose --profile pipeline run --build --rm pipeline
docker compose run --build --rm tests
```

Les CSV sources sont generes dans `data/generated/`, puis envoyes dans le bucket S3 `transactions` de LocalStack, expose sur le port hote 4567. PostgreSQL ecoute sur le port hote 5433 (ports internes aux conteneurs : 4566 et 5432).

Le tableau de bord provisionne est disponible sur <http://localhost:3000> (demonstration : `admin` / `admin`). Le datasource PostgreSQL et le dashboard se configurent automatiquement. Le dashboard affiche les sommes envoyees par IBAN et banque, les sommes recues, et les transactions superieures a 5 000. Changez ces identifiants avant tout usage partage.

Relancer la commande de pipeline ne duplique pas les donnees. La table `processed_files` impose une cle S3 unique et conserve l'empreinte SHA-256 : un objet identique est ignore; un objet remplace sous la meme cle est refuse. Pour retraiter un fichier modifie, envoyez-le sous une nouvelle cle S3.

## Lancer les tests localement

Python 3.12 recommande. Demarrer d'abord PostgreSQL et LocalStack S3 (par exemple avec Docker Compose), puis :

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q
```

Pour les tests d'integration hors Compose, definir les variables de connexion avec les valeurs de `.env.example`. `pytest` contient des tests unitaires (CSV, calculs et retries) et des tests d'integration qui ecrivent un objet unique dans S3 et verifient PostgreSQL.

## Demonstrations d'echec et retry

### Echec reproductible du traitement

Utilisez un prefixe S3 neuf pour ne pas confondre cette demonstration avec des fichiers deja traites :

```powershell
$env:S3_PREFIX = "failure-demo/"
docker compose --profile pipeline run --build --rm --entrypoint python pipeline -m data_pipeline.cli run-all --simulate-processing-failure
```

La commande doit echouer avec `Echec de traitement volontaire (demo)` avant toute insertion. Le journal de l'execution et sa capture sont conserves dans `captures/failure-processing.log` et `captures/echec-traitement.png`. Relancez ensuite la commande normale avec le meme prefixe : les fichiers valides sont traites.

```powershell
docker compose --profile pipeline run --build --rm pipeline
Remove-Item Env:S3_PREFIX
```

### Echec temporaire d'insertion et retry

```powershell
$env:S3_PREFIX = "retry-demo/"
$env:SIMULATE_INSERT_FAILURES = "1"
docker compose --profile pipeline run --build --rm pipeline
Remove-Item Env:SIMULATE_INSERT_FAILURES
Remove-Item Env:S3_PREFIX
```

Le journal affiche l'echec d'insertion simule, puis la tentative suivante; la preuve et sa capture sont dans `captures/retry-insertion.log` et `captures/retry-insertion.png`. L'insertion est transactionnelle et les cles uniques empechent un doublon si la transaction a deja ete validee. Le parametre est reserve a cette demonstration.

Pour montrer un echec de validation des donnees, modifiez temporairement un montant CSV en `NaN` et relancez le traitement; le fichier est refuse avec son numero de ligne. Remettez ensuite le fichier valide. Les deux captures incluses proviennent des executions reelles de cette pipeline; aucune capture n'a ete dessinee ou simulee.

## Schema relationnel

- `processed_files` : cle S3, empreinte SHA-256 et date de traitement.
- `transactions` : transactions chargees avec contrainte d'unicite fichier/ligne et drapeau de seuil.
- `outgoing_by_iban`, `outgoing_by_bank`, `incoming_by_iban` : sommes agregees, mises a jour dans la meme transaction PostgreSQL que les transactions.

## CI et amelioration niveau 3

Le workflow `.github/workflows/ci.yml` demarre PostgreSQL et LocalStack S3, puis execute les tests unitaires et d'integration dans Docker. Docker Compose fournit le deploiement reproductible de la pipeline et du tableau de bord. L'OCR, les modeles de langage, le deploiement cloud et Kubernetes ne sont pas inclus.

### CD vers une machine virtuelle

Le workflow `.github/workflows/deploy-vm.yml` deploie sur une VM Linux possedant Docker Engine et le plugin Docker Compose. Il se declenche sur `workflow_dispatch` (action manuelle) ou a la publication d'un tag Git `v*`. Il transfere le code et un fichier `.env` protege, demarre PostgreSQL, LocalStack S3 et Grafana, puis execute la pipeline. La VM doit autoriser la connexion SSH du runner GitHub, avec la cle privee correspondante installee pour l'utilisateur de deploiement.

Dans les parametres GitHub, creer un environnement `production` et configurer ses secrets :

- `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` (cle privee au format OpenSSH), `DEPLOY_KNOWN_HOSTS` (cle d'hote de VM verifiee et epinglee, pas une valeur issue d'un `ssh-keyscan` non verifie), et facultativement `DEPLOY_PORT`.
- `POSTGRES_PASSWORD`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`.

Les cinq secrets de compte doivent contenir uniquement lettres, chiffres, point, tiret ou underscore pour rester compatibles avec le DSN PostgreSQL du conteneur. Dans les variables de l'environnement GitHub, `DEPLOY_PATH` est facultatif (defaut `/opt/mini-projet-data`). Les ports des services sont lies a l'interface locale de la VM par defaut : pour ouvrir Grafana a distance, utiliser un reverse proxy HTTPS protege ou un tunnel SSH, par exemple `ssh -L 3000:127.0.0.1:3000 utilisateur@vm`.

Avant le premier deploiement, installer Docker Compose sur la VM, creer l'environnement GitHub `production`, et s'assurer que le compte de deploiement peut executer Docker. Lancement manuel : onglet Actions > « CD - deploiement VM Docker » > « Run workflow ». Apres validation, publier un tag tel que `v1.0.0` pour les deploiements suivants. Les identifiants d'exemple dans `.env.example` sont reserves au developpement local.

## Configuration

Les valeurs de developpement sont dans `.env.example`. Pour un environnement partage, remplacez les identifiants de demonstration et stockez les secrets dans le gestionnaire de secrets de la plateforme CI.
