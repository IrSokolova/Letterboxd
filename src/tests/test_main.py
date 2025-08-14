import os
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
    assert r.status_code == 200, r.text
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
    assert r.status_code == 200
    # Delete
    r = client.delete("/movies/?movie_id=tt0133093")
    assert r.status_code == 200
    assert r.json() == {"msg": "Deleted"}
    # Verify 404 afterwards
    r = client.get("/movies/tt0133093")
    assert r.status_code == 404

def test_register_and_login(client: TestClient):
    # Register
    r = client.post("/register/", json={
        "username": "testuser",
        "password": "testpass"
    })
    assert r.status_code == 200, r.text
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
    assert any(m["imdb_id"] == "tt0111161" for m in data)
    assert any(m["imdb_id"] == "tt0000000" for m in data)
    assert len(data) <= 2
