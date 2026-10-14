"""Client SPARQL (Wikidata) avec cache TTL + construction / parsing des requêtes.

Les fonctions de construction et de parsing sont pures (testables sans réseau).
"""
import re
import time
from typing import Any, Dict, List, Optional

import httpx

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "bio-sparql-api/0.1 (https://github.com/dridieya768-creator/bio-sparql-api)"

# Propriétés Wikidata d'identifiants externes pour un composé chimique
XREF_PROPERTIES = {
    "P662": "pubchem_cid",
    "P665": "kegg_id",
    "P2057": "hmdb_id",
    "P231": "cas_number",
    "P235": "inchikey",
    "P661": "chemspider_id",
}

_CHEBI_RE = re.compile(r"^(?:CHEBI:)?(\d{1,9})$", re.IGNORECASE)


class SparqlError(Exception):
    """Erreur lors de l'appel au endpoint SPARQL."""


def normalize_chebi_id(value: str) -> str:
    """'CHEBI:27732' ou '27732' -> '27732'. Lève ValueError si invalide.

    La validation stricte (chiffres uniquement) empêche toute injection SPARQL.
    """
    m = _CHEBI_RE.match(value.strip())
    if not m:
        raise ValueError(f"Identifiant ChEBI invalide : {value!r}")
    return m.group(1)


def escape_sparql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


# ---------- construction des requêtes ----------

def build_search_query(name: str, limit: int = 10) -> str:
    return f'''
SELECT ?item ?itemLabel ?itemDescription ?chebi WHERE {{
  SERVICE wikibase:mwapi {{
    bd:serviceParam wikibase:api "EntitySearch" .
    bd:serviceParam wikibase:endpoint "www.wikidata.org" .
    bd:serviceParam mwapi:search "{escape_sparql_string(name)}" .
    bd:serviceParam mwapi:language "en" .
    ?item wikibase:apiOutputItem mwapi:item .
  }}
  ?item wdt:P683 ?chebi .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT {int(limit)}
'''


def build_compound_query(chebi_id: str) -> str:
    cid = normalize_chebi_id(chebi_id)
    return f'''
SELECT ?item ?itemLabel ?itemDescription ?formula ?mass WHERE {{
  ?item wdt:P683 "{cid}" .
  OPTIONAL {{ ?item wdt:P274 ?formula . }}
  OPTIONAL {{ ?item wdt:P2067 ?mass . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 1
'''


def build_classes_query(chebi_id: str) -> str:
    cid = normalize_chebi_id(chebi_id)
    return f'''
SELECT DISTINCT ?cls ?clsLabel ?relation WHERE {{
  ?item wdt:P683 "{cid}" .
  {{ ?item wdt:P31 ?cls . BIND("instance_of" AS ?relation) }}
  UNION
  {{ ?item wdt:P279 ?cls . BIND("subclass_of" AS ?relation) }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 50
'''


def build_xrefs_query(chebi_id: str) -> str:
    cid = normalize_chebi_id(chebi_id)
    props = " ".join(f"wdt:{p}" for p in XREF_PROPERTIES)
    return f'''
SELECT ?prop ?value WHERE {{
  ?item wdt:P683 "{cid}" .
  VALUES ?prop {{ {props} }}
  ?item ?prop ?value .
}}
'''


# ---------- parsing des résultats ----------

def _val(binding: Dict[str, Any], key: str) -> Optional[str]:
    return binding.get(key, {}).get("value")


def qid_from_uri(uri: Optional[str]) -> Optional[str]:
    return uri.rsplit("/", 1)[-1] if uri else None


def parse_search(bindings: List[Dict]) -> List[Dict]:
    return [
        {
            "chebi_id": _val(b, "chebi"),
            "wikidata_id": qid_from_uri(_val(b, "item")),
            "label": _val(b, "itemLabel"),
            "description": _val(b, "itemDescription"),
        }
        for b in bindings
    ]


def parse_compound(bindings: List[Dict], chebi_id: str) -> Optional[Dict]:
    if not bindings:
        return None
    b = bindings[0]
    mass = _val(b, "mass")
    return {
        "chebi_id": normalize_chebi_id(chebi_id),
        "wikidata_id": qid_from_uri(_val(b, "item")),
        "label": _val(b, "itemLabel"),
        "description": _val(b, "itemDescription"),
        "formula": _val(b, "formula"),
        "mass": float(mass) if mass is not None else None,
    }


def parse_classes(bindings: List[Dict]) -> List[Dict]:
    return [
        {
            "wikidata_id": qid_from_uri(_val(b, "cls")),
            "label": _val(b, "clsLabel"),
            "relation": _val(b, "relation"),
        }
        for b in bindings
    ]


def parse_xrefs(bindings: List[Dict]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for b in bindings:
        name = XREF_PROPERTIES.get(qid_from_uri(_val(b, "prop")) or "")
        value = _val(b, "value")
        if name and value and value not in out.setdefault(name, []):
            out[name].append(value)
    return out


# ---------- client ----------

class SparqlClient:
    """Client asynchrone avec cache en mémoire (TTL) pour limiter la latence."""

    def __init__(self, endpoint: str = WIKIDATA_ENDPOINT, timeout: float = 10.0,
                 cache_ttl: float = 3600.0, cache_size: int = 512,
                 http: Optional[httpx.AsyncClient] = None):
        self.endpoint = endpoint
        self.cache_ttl = cache_ttl
        self.cache_size = cache_size
        self._cache: Dict[str, tuple] = {}
        self._http = http or httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
        )

    async def query(self, sparql: str) -> List[Dict]:
        now = time.monotonic()
        hit = self._cache.get(sparql)
        if hit and now - hit[0] < self.cache_ttl:
            return hit[1]
        try:
            resp = await self._http.get(self.endpoint, params={"query": sparql, "format": "json"})
            resp.raise_for_status()
            bindings = resp.json()["results"]["bindings"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise SparqlError(f"Échec de la requête SPARQL : {exc}") from exc
        if len(self._cache) >= self.cache_size:
            self._cache.pop(next(iter(self._cache)))  # éviction FIFO
        self._cache[sparql] = (now, bindings)
        return bindings

    async def aclose(self) -> None:
        await self._http.aclose()
