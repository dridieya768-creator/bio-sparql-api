def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_search(client):
    r = client.get("/compounds/search", params={"q": "caffeine"})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    assert data["results"][0]["chebi_id"] == "27732"
    assert data["results"][0]["label"] == "caffeine"


def test_search_validation(client):
    assert client.get("/compounds/search", params={"q": "a"}).status_code == 422
    assert client.get("/compounds/search", params={"q": "ab", "limit": 500}).status_code == 422
    assert client.get("/compounds/search").status_code == 422


def test_get_compound(client):
    r = client.get("/compounds/CHEBI:27732")
    assert r.status_code == 200
    body = r.json()
    assert body["formula"] == "C8H10N4O2" and body["mass"] == 194.08


def test_compound_not_found(client):
    assert client.get("/compounds/99999999").status_code == 404


def test_invalid_id(client):
    assert client.get("/compounds/not-an-id").status_code == 422


def test_classes(client):
    r = client.get("/compounds/27732/classes")
    assert r.status_code == 200
    assert r.json() == [{"wikidata_id": "Q407595", "label": "purine alkaloid",
                         "relation": "subclass_of"}]


def test_xrefs(client):
    r = client.get("/compounds/27732/xrefs")
    assert r.status_code == 200
    assert r.json()["references"] == {"pubchem_cid": ["2519"], "cas_number": ["58-08-2"]}


def test_upstream_failure_returns_502(client, fake):
    fake.fail = True
    assert client.get("/compounds/27732").status_code == 502
