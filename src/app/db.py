from sqlalchemy import create_engine, update
from dotenv import load_dotenv
import os
from sqlmodel import Session
from functools import lru_cache


load_dotenv()

USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")
DATABASE_URL = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"


@lru_cache()
def get_engine():
    return create_engine(DATABASE_URL)


try:
    with get_engine().connect() as connection:
        print("Connection successful!")
except Exception as e:
    print(f"Failed to connect: {e}")


def get_session():
    with Session(get_engine()) as session:
        yield session