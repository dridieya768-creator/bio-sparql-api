"""API REST de données biologiques interopérables (Wikidata / ChEBI via SPARQL)."""
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Query

from . import sparql
from .models import Compound, CompoundClass, CrossReferences, SearchResult
from .sparql import SparqlClient, SparqlError


@lru_cache
def get_client() -> SparqlClient:
    return SparqlClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    if get_client.cache_info().currsize:
        await get_client().aclose()


app = FastAPI(
    title="Bio SPARQL API",
    description="Interroge les données Wikidata/ChEBI (composés chimiques) via SPARQL "
                "et expose le résultat en JSON.",
    version="0.1.0",
    lifespan=lifespan,
)


def _chebi(value: str) -> str:
    try:
        return sparql.normalize_chebi_id(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


async def _run(client: SparqlClient, query: str):
    try:
        return await client.query(query)
    except SparqlError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


@app.get("/compounds/search", response_model=SearchResult, tags=["compounds"])
async def search_compounds(
    q: str = Query(..., min_length=2, max_length=100, description="Nom du composé"),
    limit: int = Query(10, ge=1, le=50),
    client: SparqlClient = Depends(get_client),
):
    bindings = await _run(client, sparql.build_search_query(q, limit))
    results = sparql.parse_search(bindings)
    return SearchResult(query=q, count=len(results), results=results)


@app.get("/compounds/{chebi_id}", response_model=Compound, tags=["compounds"])
async def get_compound(chebi_id: str, client: SparqlClient = Depends(get_client)):
    cid = _chebi(chebi_id)
    bindings = await _run(client, sparql.build_compound_query(cid))
    compound = sparql.parse_compound(bindings, cid)
    if compound is None:
        raise HTTPException(status_code=404, detail=f"ChEBI:{cid} introuvable dans Wikidata")
    return compound


@app.get("/compounds/{chebi_id}/classes", response_model=List[CompoundClass], tags=["compounds"])
async def get_classes(chebi_id: str, client: SparqlClient = Depends(get_client)):
    cid = _chebi(chebi_id)
    return sparql.parse_classes(await _run(client, sparql.build_classes_query(cid)))


@app.get("/compounds/{chebi_id}/xrefs", response_model=CrossReferences, tags=["compounds"])
async def get_xrefs(chebi_id: str, client: SparqlClient = Depends(get_client)):
    cid = _chebi(chebi_id)
    refs = sparql.parse_xrefs(await _run(client, sparql.build_xrefs_query(cid)))
    return CrossReferences(chebi_id=cid, references=refs)
