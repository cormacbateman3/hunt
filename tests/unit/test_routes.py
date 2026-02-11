def test_home_page(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"KeystoneBid" in response.data


def test_blueprint_scaffold_route(client):
    response = client.get("/listings/")

    assert response.status_code == 200
    assert b"Listings" in response.data
