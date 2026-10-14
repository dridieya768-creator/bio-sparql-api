# Bio SPARQL API

API REST (FastAPI) qui interroge des données biologiques **interopérables** — composés chimiques de **Wikidata / ChEBI** — via des requêtes **SPARQL** et renvoie du **JSON**.

![CI](https://github.com/dridieya768-creator/bio-sparql-api/actions/workflows/ci.yml/badge.svg)

## Endpoints

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | état du service |
| GET | `/compounds/search?q=caffeine&limit=10` | recherche d'un composé par nom (seuls les items avec un identifiant ChEBI sont retournés) |
| GET | `/compounds/{chebi_id}` | fiche : libellé, description, formule, masse |
| GET | `/compounds/{chebi_id}/classes` | classes (instance de / sous-classe de) |
| GET | `/compounds/{chebi_id}/xrefs` | références croisées : PubChem, KEGG, HMDB, CAS, InChIKey, ChemSpider |

`chebi_id` accepte `27732` ou `CHEBI:27732`. Documentation interactive : `/docs` (Swagger).

Codes d'erreur : `404` composé introuvable, `422` paramètre invalide, `502` endpoint SPARQL indisponible.

## Lancer

```bash
# Docker (une commande)
docker build -t bio-sparql-api . && docker run -p 8000:8000 bio-sparql-api

# ou en local
pip install -r requirements.txt
uvicorn app.main:app --reload
```

```bash
curl "http://localhost:8000/compounds/search?q=caffeine"
curl "http://localhost:8000/compounds/27732"
curl "http://localhost:8000/compounds/27732/xrefs"
```

## Tests et qualité

```bash
pip install -r requirements-dev.txt
pytest                       # tests + couverture (le CI exige >= 80 %)
```

Les tests n'appellent jamais Wikidata : le client SPARQL est remplacé par un faux client (API) ou un `httpx.MockTransport` (client). Le workflow GitHub Actions lance les tests à chaque commit, puis construit l'image Docker et vérifie `/health`.

## Choix techniques

* **Sécurité des requêtes** : l'identifiant ChEBI est validé (chiffres uniquement) et les chaînes de recherche sont échappées avant d'être insérées dans le SPARQL (pas d'injection).
* **Latence** : cache mémoire à durée de vie (TTL 1 h) ; le premier appel dépend de Wikidata, les suivants sont servis depuis le cache.
* **Recherche** : service `wikibase:mwapi` (EntitySearch) plutôt qu'un `FILTER(CONTAINS(...))`, qui parcourrait toute la base.

## Mesurer la latence

```bash
uvicorn app.main:app &
python scripts/benchmark.py http://localhost:8000 20
```

Le script sépare le 1er appel (cache froid, requête réelle vers Wikidata) de la médiane des appels suivants (cache chaud).

## Licence

MIT
