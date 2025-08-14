from typing import Optional, Any, Sequence
from typing import Annotated
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, select

from src.app.additional.imdb_connect import *
from src.app.db import *
# from additional.imdb_connect import *
# from db import *

from sqlalchemy import update
from enum import Enum
from sqlalchemy.sql import func


# class RecomendationReasonEnum(Enum):
#     Other = 'Other'
#     RecentlyAdded = 'Recently Added or Timely'
#     Friends = 'Friends recommendation'
#     HighRating = 'High Rating or Popular'
#     SameDirector = 'Same Director, Actor, or Franchise'


class Movie(SQLModel, table=True):
    __tablename__ = "movies"
    imdb_id: str = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: Optional[str]
    poster_url: Optional[str]
    start_year: int
    average_score: Optional[float]

    def __init__(self, imdb_id, name, description, poster_url, start_year, **data: Any):
        super().__init__(**data)
        self.imdb_id = imdb_id
        self.name = name
        self.description = description
        self.poster_url = poster_url
        self.start_year = start_year
        self.average_score = None


class User(SQLModel, table=True):
    __tablename__ = "users"
    user_id: int = Field(index=True, primary_key=True)
    username: str = Field(index=True)
    password: str


    def __init__(self, username, password, **data: Any):
        super().__init__(**data)
        self.username = username
        self.password = password


class WatchLater(SQLModel, table=True):
    __tablename__ = "watch_later"
    id: int = Field(index=True, primary_key=True)
    user_id: int = Field(index=True)
    movie_id: str
    watched_at: Optional[date]
    score: Optional[int] = None
    recommendation_reason: Optional[str]

    def __init__(self, user_id, movie_id, recommendation_reason, score, watched_at, **data: Any):
        super().__init__(**data)
        self.user_id = user_id
        self.movie_id = movie_id
        self.recommendation_reason = recommendation_reason
        self.watched_at = watched_at
        self.score = score


def create_rand_movie() -> Movie:
    movie_info = get_rand_movie_info()
    return Movie(movie_info["imdb_id"], movie_info["name"], movie_info["description"],
                 movie_info["poster_url"], movie_info["start_year"])


def wrap_movie_info(movie_id: str) -> Movie:
    movie_info = get_movie_info(movie_id)
    return Movie(movie_info["imdb_id"], movie_info["name"], movie_info["description"],
                 movie_info["poster_url"], movie_info["start_year"])


SessionDep = Annotated[Session, Depends(get_session)]


def user_exist(username: str, session: SessionDep):
    statement = select(User).where(User.username == username)
    user = session.exec(statement).first()
    return bool(user)


def calculate_average_score(movie_id: str, session: SessionDep):
    average_score = session.query(func.avg(WatchLater.score).label('average')).filter(WatchLater.movie_id == movie_id and
                                                                      WatchLater.score is not None).scalar()
    statement = update(Movie).where(Movie.imdb_id == movie_id).values(average_score=average_score)
    session.exec(statement)
    session.commit()


app = FastAPI()


@app.post("/movies/")
def create_movie(movie: Movie, session: SessionDep) -> Movie:
    if session.get(Movie, movie.imdb_id):
        raise HTTPException(status_code=406, detail="This movie already exists")
    else:
        session.add(movie)
        session.commit()
        session.refresh(movie)
        return movie


@app.post("/movie/")
def create_movie(movie_id: str, session: SessionDep) -> Movie:
    if session.get(Movie, movie_id):
        raise HTTPException(status_code=406, detail="This movie already exists")
    else:
        movie = wrap_movie_info(movie_id)
        session.add(movie)
        session.commit()
        session.refresh(movie)
        return movie


@app.get("/movies/")
def read_movies(session: SessionDep, year: Optional[int] = None, limit: int = 10) -> Sequence[Movie]:
    if year:
        movies = session.exec(select(Movie).where(Movie.start_year == year).limit(limit)).all()
    else:
        movies = session.exec(select(Movie).limit(limit)).all()
    return movies


@app.get("/movies/{movie_id}")
def read_movie(movie_id: str, session: SessionDep) -> Movie:
    """
    Get a movie with all the information:

    - **imdb_id**: each item must have a imdb id
    - **name**: each item must have a name
    - **description**: plot description
    - **poster_url**: optional poster url
    - **start_year**: required
    """
    movie = session.get(Movie, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


@app.delete("/movies/")
def delete_movie(session: SessionDep, movie_id: str):
    movie = session.get(Movie, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    session.delete(movie)
    session.commit()
    return {"msg": "Deleted"}


@app.get("/login/")
def login(username: str, password: str, session: SessionDep):
    statement = select(User).where(User.username == username)
    user = session.exec(statement).all()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user[0].password != password:
        raise HTTPException(status_code=401, detail="Wrong password")
    return {"msg": "Logged in"}


@app.get("/users/")
def read_user_info(user_id: int, session: SessionDep):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.put("/users/")
def update_user_info(user: User, session: SessionDep) -> User:
    old_user = session.get(User, user.user_id)
    if old_user:
        user_data = user.model_dump(exclude_unset=True)
        old_user.sqlmodel_update(user_data)
        session.commit()
        return old_user
    else:
        raise HTTPException(status_code=404, detail="User not found")


@app.post("/register/")
def create_user(user: User, session: SessionDep) -> User:
    if not user_exist(user.username, session):
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    else:
        raise HTTPException(status_code=401, detail="This username is occupied")


@app.post("/watched/")
def create_watched_record(watch_later: WatchLater, session: SessionDep) -> WatchLater:
    statement = select(WatchLater).where(WatchLater.user_id == watch_later.user_id,
                                         WatchLater.movie_id == watch_later.movie_id)
    old_watch_later = session.exec(statement).first()
    if old_watch_later is not None:
        update_watch_later_record(watch_later, session)
    else:
        if watch_later.score is not None:
            if watch_later.score < 1 or watch_later.score > 10:
                raise HTTPException(status_code=422, detail="The score should be between 1 and 10")
        if watch_later.watched_at is not None:
            if watch_later.watched_at > date.today():
                raise HTTPException(status_code=422, detail="The watch date should be before or equal today")
        session.add(watch_later)
        session.commit()
        session.refresh(watch_later)
        if watch_later.score is not None:
            calculate_average_score(watch_later.movie_id, session)
    return watch_later


@app.put("/watched/")
def update_watch_later_record(new_watch_later: WatchLater, session: SessionDep):
    statement = select(WatchLater).where(WatchLater.user_id == new_watch_later.user_id,
                                         WatchLater.movie_id == new_watch_later.movie_id)
    old_watch_later = session.exec(statement).first()
    if not old_watch_later:
        raise HTTPException(status_code=404, detail="Record not found")
    if new_watch_later.watched_at is not None:
        if new_watch_later.watched_at > date.today():
            raise HTTPException(status_code=422, detail="The watch date should be before or equal today")
    else:
        new_watch_later.watched_at = date.today()
    if new_watch_later.score is not None:
        if new_watch_later.score < 1 or new_watch_later.score > 10:
            raise HTTPException(status_code=422, detail="The score should be between 1 and 10")
    watch_later_data = new_watch_later.model_dump(exclude_unset=True)
    old_watch_later.sqlmodel_update(watch_later_data)
    session.commit()
    calculate_average_score(new_watch_later.movie_id, session)
    return old_watch_later


@app.post("/watchlater/")
def create_watch_later_record(watch_later: WatchLater, session: SessionDep) -> WatchLater:
    statement = select(WatchLater).where(WatchLater.user_id == watch_later.user_id,
                                         WatchLater.movie_id == watch_later.movie_id)
    old_watch_later = session.exec(statement).first()
    if old_watch_later is not None:
        update_watch_later_record(watch_later, session)
        return watch_later
    else:
        session.add(watch_later)
        session.commit()
        session.refresh(watch_later)
        return watch_later


@app.get("/watchlater/{user_id}")
def read_users_watch_later(user_id: int, session: SessionDep) -> list[WatchLater]:
    user = session.get(User, user_id)
    if user is not None:
        statement = (select(WatchLater).where(WatchLater.watched_at == None, WatchLater.user_id == user_id))
        watch_later = session.exec(statement).all()
        if len(watch_later) == 0:
            raise HTTPException(status_code=404, detail="Empty watch later list")
        return watch_later
    else:
        raise HTTPException(status_code=404, detail="User not found")


@app.get("/watched/{user_id}")
def read_users_watched(user_id: int, session: SessionDep) -> list[WatchLater]:
    user = session.get(User, user_id)
    if user is not None:
        statement = (select(WatchLater).where(WatchLater.watched_at is not None, WatchLater.user_id == user_id))
        watch_later = session.exec(statement).all()
        if len(watch_later) == 0:
            raise HTTPException(status_code=404, detail="Empty watch later list")
        return watch_later
    else:
        raise HTTPException(status_code=404, detail="User not found")


@app.get("/")
def read_root():
    return {"Cool": "Movies"}