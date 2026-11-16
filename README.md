# DataOps Vélib'

Plateforme de données quotidienne autour du réseau Vélib' de Paris : ingestion de l'API
publique CityBikes, validation de contrat, stockage compatible S3, entrepôt DuckDB,
transformations dbt et page de santé des données.

## Démarrer en local

Prérequis : Docker Desktop avec Docker Compose.

```powershell
docker compose up --build
```

Le premier démarrage lance aussi une ingestion ; les suivants reprennent le même
instantané journalier sans créer de doublons. Prefect programme ensuite une exécution
quotidienne à 06:00 UTC. Interfaces :

- Santé des données : <http://localhost:8000>
- API santé : <http://localhost:8000/api/health>
- Métriques : <http://localhost:8000/api/metrics>
- Prefect : <http://localhost:4200>
- API S3 locale (LocalStack) : <http://localhost:4566>. Elle n'a pas de console
  web ; les identifiants locaux sont factices et ne fonctionnent pas sur AWS.

Les données sont enregistrées dans les volumes Docker `object-store-data`,
`warehouse-data` et `prefect-data`. `docker compose down -v` les supprime.

Le service S3 local utilise LocalStack. Les images MinIO configurées précédemment
ne pouvaient pas être récupérées publiquement dans cet environnement (401 sur Quay
et dépôt Docker Hub indisponible). LocalStack émule l'API S3 pour le développement ;
AWS utilise le service S3 réel.

## Ce que le projet démontre

- **Contrat par source** : `contracts/citybikes_velib.schema.json` est appliqué à
  chaque réponse avant toute écriture.
- **Ingestion idempotente** : la clé primaire `(snapshot_date, station_id)` fait
  un upsert DuckDB ; le JSON brut est écrit sous une clé déterministe par jour.
- **Couches dbt** : staging des stations puis agrégats quotidiens dans le mart ;
  les tests dbt contrôlent les clés, les valeurs nulles et les plages métier.
- **Orchestration** : Prefect effectue une première exécution au démarrage puis
  programme le pipeline quotidien.
- **Santé et alerte** : la page distingue la santé du service et la fraîcheur des
  données. `ALERT_WEBHOOK_URL` peut pointer vers un webhook compatible HTTP POST
  pour recevoir une alerte locale en cas d'échec ; les journaux Prefect/Docker
  conservent aussi l'erreur.
- **Idée ajoutée** : le mart calcule le taux de disponibilité des vélos et repère
  les stations momentanément sans vélo ni place libre ; la page explique la date
  du dernier instantané et expose ces indicateurs aux utilisateurs.

## Configuration locale

Compose utilise des identifiants factices uniquement contre le service S3 local.
Pour régler les options, copier `.env.example` vers `.env` puis éditer les valeurs.
`.env` est ignoré par Git ; n'y mettez jamais de vrais identifiants.

Réglages applicatifs optionnels : `CITYBIKES_NETWORK` (défaut `velib`),
`CITYBIKES_API_URL`, `SCHEDULE_CRON` (défaut `0 6 * * *`), `ALERT_WEBHOOK_URL`.

## CI et règles d'équipe

Le workflow `.github/workflows/ci.yml` valide le contrat, exécute les tests et
construit les modèles dbt sur une base temporaire à chaque pull request et push
sur `main`. Dans GitHub, activez la protection de `main` : pull request
obligatoire, au moins une revue, et le contrôle `quality-and-deploy / quality`
obligatoire. Aucun workflow ne pousse directement sur `main`.

## Déploiement AWS via GitHub Actions

Le job `deploy` du workflow `.github/workflows/ci.yml` déploie après validation
de `quality` à chaque push sur `main`. Il utilise OIDC pour assumer un rôle AWS,
publie l'image dans ECR et applique Terraform avant de
mettre à jour ECS. L'API ECS sert le tableau de bord ; EventBridge lance le même
pipeline chaque jour à 06:00 UTC. Les instantanés bruts et la base DuckDB publiée
sont conservés dans S3. Le pipeline local utilise Prefect ; le planificateur cloud
est EventBridge afin d'éviter de maintenir un serveur Prefect payant en permanence.

Préparation unique du compte AWS et du dépôt GitHub :

1. Créez un bucket S3 privé de state Terraform (versioning et chiffrement activés).
   Ce bucket n'est pas géré par le workflow car Terraform doit déjà avoir un backend
   durable avant son premier `apply`.
2. Créez un rôle IAM GitHub OIDC limité à ce dépôt et à la branche `main`, avec les
   permissions Terraform/ECR/ECS nécessaires. Aucun utilisateur ou access key IAM
   n'est requis.
3. Configurez le secret GitHub `AWS_ROLE_ARN` et les variables `AWS_REGION`,
   `TF_STATE_BUCKET`, `AWS_BUDGET_ALERT_EMAIL` et `API_ALLOWED_CIDR`. Pour cette
   dernière, préférez votre adresse IP publique suivie de `/32` ; n'ouvrez pas
   l'interface non authentifiée à `0.0.0.0/0`.
4. Le Terraform crée une alerte de budget mensuel (20 USD par défaut), le bucket S3
   chiffré, ECR, ECS, une alerte email pour les exécutions ECS en échec et la
   planification. Confirmez l'abonnement email SNS reçu au premier déploiement.
   Vérifiez le montant et les ressources
   dans `infra/terraform/variables.tf` avant le premier déploiement.
5. Pour supprimer les ressources du projet, exécutez `terraform destroy` depuis
   `infra/terraform` avec le même backend/variables. Le bucket de state doit être
   supprimé séparément après destruction ; vérifiez d'abord qu'il ne contient rien
   d'autre. Les ressources et coûts AWS sont la responsabilité du compte de l'équipe.

Le backend Terraform et l'accès OIDC nécessitent cette préparation administrative
unique ; ensuite, les mises à jour de la plateforme sont automatisées par la CI.
Les clés d'accès AWS ne sont jamais stockées dans le dépôt.

## Développement

```powershell
python -m pip install -e ".[dev]"
ruff check .
pytest
```

Les tests vérifient la validation du contrat, l'upsert idempotent et les indicateurs
du mart. L'endpoint API réel peut ne pas être joignable hors Docker.
