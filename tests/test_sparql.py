import asyncio

import httpx
import pytest

from app import sparql
from app.sparql import SparqlClient, SparqlError


def test_normalize_chebi_id():
    assert sparql.normalize_chebi_id("27732") == "27732"
    assert sparql.normalize_chebi_id("CHEBI:27732") == "27732"
    assert sparql.normalize_chebi_id(" chebi:15377 ") == "15377"


@pytest.mark.parametrize("bad", ["", "abc", '1" } DROP', "CHEBI:", "12 34", "-5"])
def test_normalize_rejects_invalid(bad):
    with pytest.raises(ValueError):
        sparql.normalize_chebi_id(bad)


def test_escape_prevents_injection():
    q = sparql.build_search_query('x" . ?s ?p ?o #', 5)
    assert 'mwapi:search "x\\" . ?s ?p ?o #"' in q
    assert "LIMIT 5" in q


def test_queries_embed_clean_id():
    for build in (sparql.build_compound_query, sparql.build_classes_query,
                  sparql.build_xrefs_query):
        assert 'wdt:P683 "27732"' in build("CHEBI:27732")


def test_parse_compound_and_missing():
    b = [{"item": {"value": "http://www.wikidata.org/entity/Q60235"},
          "itemLabel": {"value": "caffeine"}, "mass": {"value": "194.08"}}]
    c = sparql.parse_compound(b, "27732")
    assert c["wikidata_id"] == "Q60235" and c["mass"] == 194.08 and c["formula"] is None
    assert sparql.parse_compound([], "27732") is None


def test_parse_xrefs_dedup():
    b = [{"prop": {"value": "http://www.wikidata.org/prop/direct/P662"}, "value": {"value": "1"}},
         {"prop": {"value": "http://www.wikidata.org/prop/direct/P662"}, "value": {"value": "1"}},
         {"prop": {"value": "http://www.wikidata.org/prop/direct/P999"}, "value": {"value": "x"}}]
    assert sparql.parse_xrefs(b) == {"pubchem_cid": ["1"]}


def _mock_client(handler, **kw):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return SparqlClient(http=http, **kw)


def test_client_caches_results():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"results": {"bindings": [{"a": {"value": "1"}}]}})

    async def run():
        c = _mock_client(handler)
        r1 = await c.query("SELECT 1")
        r2 = await c.query("SELECT 1")
        await c.aclose()
        return r1, r2

    r1, r2 = asyncio.run(run())
    assert r1 == r2 and len(calls) == 1


def test_client_http_error_raises_sparql_error():
    async def run():
        c = _mock_client(lambda req: httpx.Response(500))
        try:
            await c.query("SELECT 1")
        finally:
            await c.aclose()

    with pytest.raises(SparqlError):
        asyncio.run(run())


def test_client_cache_eviction():
    def handler(request):
        return httpx.Response(200, json={"results": {"bindings": []}})

    async def run():
        c = _mock_client(handler, cache_size=2)
        for q in ("a", "b", "c"):
            await c.query(q)
        n = len(c._cache)
        await c.aclose()
        return n

    assert asyncio.run(run()) == 2
