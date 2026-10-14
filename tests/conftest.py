import pytest
from fastapi.testclient import TestClient

from app.main import app, get_client

CAFFEINE = {"item": {"value": "http://www.wikidata.org/entity/Q60235"},
            "itemLabel": {"value": "caffeine"},
            "itemDescription": {"value": "chemical compound"},
            "chebi": {"value": "27732"},
            "formula": {"value": "C8H10N4O2"},
            "mass": {"value": "194.08"}}


class FakeClient:
    """Faux client SPARQL : renvoie des résultats prédéfinis selon la requête."""

    def __init__(self, fail=False):
        self.fail = fail
        self.queries = []

    async def query(self, sparql):
        from app.sparql import SparqlError
        self.queries.append(sparql)
        if self.fail:
            raise SparqlError("boom")
        if "mwapi" in sparql:
            return [CAFFEINE]
        if '"99999999"' in sparql:
            return []
        if "?cls" in sparql:
            return [{"cls": {"value": "http://www.wikidata.org/entity/Q407595"},
                     "clsLabel": {"value": "purine alkaloid"},
                     "relation": {"value": "subclass_of"}}]
        if "?prop" in sparql:
            return [{"prop": {"value": "http://www.wikidata.org/prop/direct/P662"},
                     "value": {"value": "2519"}},
                    {"prop": {"value": "http://www.wikidata.org/prop/direct/P662"},
                     "value": {"value": "2519"}},
                    {"prop": {"value": "http://www.wikidata.org/prop/direct/P231"},
                     "value": {"value": "58-08-2"}}]
        return [CAFFEINE]


@pytest.fixture
def fake():
    return FakeClient()


@pytest.fixture
def client(fake):
    app.dependency_overrides[get_client] = lambda: fake
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
