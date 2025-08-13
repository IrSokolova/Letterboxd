import pytest

from src.app.main import app
from fastapi.testclient import TestClient

from src.app.additional import imdb_connect

client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"Cool": "Movies"}


def test_read_movie():
    response = client.get("/movies/tt0110912")
    assert response.status_code == 200
    assert response.json() == {
        "poster_url": "https://m.media-amazon.com/images/M/MV5BYTViYTE3ZGQtNDBlMC00ZTAyLTkyODMtZGRiZDg0MjA2YThkXkEyXkFqcGc@._V1_.jpg",
        "name": "Pulp Fiction",
        "imdb_id": "tt0110912",
        "start_year": 1994,
        "description": "The lives of two mob hitmen, a boxer, a gangster and his wife, and a pair of diner bandits intertwine in four tales of violence and redemption."
    }


def test_read_bad_movie():
    response = client.get("/movies/tt0110900")
    assert response.status_code == 404
    assert response.json() == {
        "detail": "Movie not found"
    }


test_movie_to_add = {
    "imdb_id": "tt10676052",
    "name": "The Fantastic Four: First Steps",
    "description": "Forced to balance their roles as heroes with the strength of their family bond, the Fantastic Four must defend Earth from a ravenous space god called Galactus and his enigmatic Herald, Silver Surfer.",
    "poster_url": "https://m.media-amazon.com/images/M/MV5BOGM5MzA3MDAtYmEwMi00ZDNiLTg4MDgtMTZjOTc0ZGMyNTIwXkEyXkFqcGc@._V1_.jpg",
    "start_year": 2025
}

@pytest.mark.skip
def test_add_movie():
    response = client.post("/movies/", json=test_movie_to_add)
    assert response.status_code == 200

    response = client.get(f"/movies/{test_movie_to_add['imdb_id']}")
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["imdb_id"] == test_movie_to_add['imdb_id']
    assert response_json["name"] == "The Fantastic Four: First Steps"
    assert response_json["description"] == "Forced to balance their roles as heroes with the strength of their family bond, the Fantastic Four must defend Earth from a ravenous space god called Galactus and his enigmatic Herald, Silver Surfer."
    assert response_json["poster_url"] == "https://m.media-amazon.com/images/M/MV5BOGM5MzA3MDAtYmEwMi00ZDNiLTg4MDgtMTZjOTc0ZGMyNTIwXkEyXkFqcGc@._V1_.jpg"
    assert response_json["start_year"] == 2025


def test_add_existing_movie():
    response = client.post("/movies/", json=test_movie_to_add)
    assert response.status_code == 406