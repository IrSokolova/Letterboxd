import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event
from sqlalchemy.engine import Engine

from src.app.main import app, Movie, User, get_session

USER = os.getenv("test_user")
PASSWORD = os.getenv("test_password")
HOST = os.getenv("test_host")
PORT = os.getenv("test_port")
DBNAME = os.getenv("test_dbname")
TEST_DATABASE_URL = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}"


@pytest.fixture(scope="session")
def engine() -> Engine:
    eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    SQLModel.metadata.create_all(eng)
    yield eng
    SQLModel.metadata.drop_all(eng)

@pytest.fixture
def db_session(engine: Engine):
    connection = engine.connect()
    session = Session(bind=connection)

    try:
        yield session
    finally:
        session.close()
        connection.close()

@pytest.fixture
def client(db_session: Session):
    def _override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()



def test_root(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"Cool": "Movies"}


def test_create_and_read_movie(client: TestClient, db_session: Session):
    payload = {
        "imdb_id": "tt0111161",
        "name": "The Shawshank Redemption",
        "description": "Hope is a good thing.",
        "poster_url": "https://example.org/poster.jpg",
        "start_year": 1994,
    }
    # Create
    r = client.post("/movies/", json=payload)
    assert r.status_code == 201, r.text
    # Read list
    r = client.get("/movies/")
    assert r.status_code == 200
    items = r.json()
    assert any(m["imdb_id"] == "tt0111161" for m in items)
    # Read single
    r = client.get("/movies/tt0111161")
    assert r.status_code == 200
    assert r.json()["name"] == "The Shawshank Redemption"

def test_delete_movie(client: TestClient):
    # Insert a movie, then delete it
    r = client.post("/movies/", json={
        "imdb_id": "tt0133093",
        "name": "The Matrix",
        "description": None,
        "poster_url": None,
        "start_year": 1999
    })
    assert r.status_code == 201
    # Delete
    r = client.delete("/movies/?movie_id=tt0133093")
    assert r.status_code == 204
    # Verify 404 afterwards
    r = client.get("/movies/tt0133093")
    assert r.status_code == 404

def test_register_and_login(client: TestClient):
    # Register
    r = client.post("/register/", json={
        "username": "testuser",
        "password": "testpass"
    })
    assert r.status_code == 201, r.text
    # Login OK
    r = client.get("/login/?username=testuser&password=testpass")
    assert r.status_code == 200
    assert r.json() == {"msg": "Logged in"}
    # Wrong username
    r = client.get("/login/?username=wronguser&password=testpass")
    assert r.status_code == 404
    # Wrong password
    r = client.get("/login/?username=testuser&password=wrongpass")
    assert r.status_code == 401

def test_update_user_info(client: TestClient):
    # Update not existing user info
    r = client.put("/users/", json={
        "user_id": 2,
        "username": "newuser",
        "password": "newpass"
    })
    assert r.status_code == 404
    # Get current user info
    r = client.get("/users/?user_id=1")
    data = r.json()
    assert r.status_code == 200
    assert data["username"] == "testuser"
    assert data["password"] == "testpass"
    # Update user info
    r = client.put("/users/", json={
        "user_id": 1,
        "username": "newuser",
        "password": "newpass"
    })
    # Verify new user info
    assert r.status_code == 200
    assert r.json() == {"msg": "Record updated"}
    r = client.get("/users/?user_id=1")
    data = r.json()
    assert r.status_code == 200
    assert data["username"] == "newuser"
    assert data["password"] == "newpass"

def test_read_movies(client: TestClient):
    # Add a couple of movies
    for i in range(3):
        client.post("/movies/", json={
            "imdb_id": f"tt000000{i}",
            "name": f"Movie {i}",
            "description": None,
            "poster_url": None,
            "start_year": 2000 + i
        })
    r = client.get("/movies/?limit=2")
    assert r.status_code == 200
    data = r.json()
    assert any(m["imdb_id"] == "tt0000002" for m in data)
    assert any(m["imdb_id"] == "tt0000001" for m in data)
    assert len(data) <= 2
    r = client.get("/movies/?year=2001")
    data = r.json()
    assert r.status_code == 200
    assert all(m["start_year"] == 2001 for m in data)

def test_create_movie_by_imdb_id(client: TestClient):
    # Add movie that is already in db
    r = client.post("/movie/?movie_id=tt0111161")
    assert r.status_code == 409
    # Add movie
    r = client.post("/movie/?movie_id=tt0361748")
    assert r.status_code == 201
    # Read movie and verify info
    r = client.get("/movies/tt0361748")
    assert r.status_code == 200
    assert r.json()["description"] == ("In Nazi-occupied France during World War II, a plan to assassinate Nazi leaders "
                                       "by a group of Jewish U.S. soldiers coincides with a theatre owner's vengeful plans for the same.")

def test_create_watched(client):
    wrong_payload = {
        "user_id": 1,
        "movie_id": "tt1234567",
        "recommendation_reason": "High Rating",
        "score": 8,
        "watched_at": "2024-01-01",
    }
    right_payload = {
        "user_id": 1,
        "movie_id": "tt0361748",
        "recommendation_reason": "High Rating",
        "score": 8,
        "watched_at": None,
    }
    resp = client.post("/watched/", json=wrong_payload)
    assert resp.status_code == 404
    resp = client.post("/watched/", json=right_payload)
    assert resp.status_code == 201

def test_create_watched_calculates_score(client):
    payload = {
        "user_id": 1,
        "movie_id": "tt0111161",
        "recommendation_reason": "High Rating",
        "score": 8,
        "watched_at": None,
    }
    data = client.get("/movies/tt0111161").json()
    assert data["average_score"] is None
    resp = client.post("/watched/", json=payload)
    assert resp.status_code == 201
    data = client.get("/movies/tt0111161").json()
    assert data["average_score"]  == 8.0

def test_create_watched_validation_bad_score(client):
    payload = {
        "user_id": 1,
        "movie_id": "tt0000001",
        "score": 11,
        "recommendation_reason": "High Rating",
        "watched_at": None
    }
    resp = client.post("/watched/", json=payload)
    assert resp.status_code == 422
    assert resp.json()["detail"] == "The score should be between 1 and 10"

def test_create_watched_validation_future_date(client):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    payload = {
        "user_id": 1,
        "movie_id": "tt0000001",
        "watched_at": tomorrow,
        "score": 7,
        "recommendation_reason": "High Rating"

    }
    resp = client.post("/watched/", json=payload)
    assert resp.status_code == 422
    assert resp.json()["detail"] == "The watch date should be before or equal today"






