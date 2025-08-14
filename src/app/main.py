import re
from typing import Optional, Any, Sequence, Literal
from typing import Annotated
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, status, Query, Path
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, select
from starlette.responses import Response

from src.app.additional.imdb_connect import *
from src.app.db import *
# from additional.imdb_connect import *
# from db import *

from sqlalchemy import update, UniqueConstraint
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
    start_year: int = Field(index=True)
    average_score: Optional[float] = Field(index=True)

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
    username: str = Field(index=True, unique=True, nullable=False)
    password: str


    def __init__(self, username, password, **data: Any):
        super().__init__(**data)
        self.username = username
        self.password = password


class WatchLater(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="watch_later"),)
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
    if movie_info:
        return Movie(movie_info["imdb_id"], movie_info["name"], movie_info["description"],
                 movie_info["poster_url"], movie_info["start_year"])
    return movie_info


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


@app.post("/movies/",response_model=Movie, status_code=status.HTTP_201_CREATED)
def create_movie(movie: Movie, session: SessionDep) -> Movie:
    if not re.fullmatch(r"tt\d{7,8}", movie.imdb_id):
        raise HTTPException(status_code=422, detail="Invalid imdb_id format")
    session.add(movie)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Movie with this imdb_id already exists")

    session.refresh(movie)
    return movie


@app.post("/movie/",response_model=Movie, status_code=status.HTTP_201_CREATED)
def create_movie(movie_id: str, session: SessionDep) -> Movie:
    if not re.fullmatch(r"tt\d{7,8}", movie_id):
        raise HTTPException(status_code=422, detail="Invalid imdb_id format")

    movie = wrap_movie_info(movie_id)
    if movie is None:
        raise HTTPException(status_code=404,
                            detail="Movie not found in source")

    session.add(movie)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Movie with this imdb_id already exists")

    session.refresh(movie)
    return movie


@app.get("/movies/")
def read_movies(
    session: SessionDep,
    year: Optional[int] = Query(default=None, ge=1870, le=2100),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    order: Literal["asc", "desc"] = "desc",
) -> Sequence[Movie]:
    statement = select(Movie)

    if year is not None:
        statement = statement.where(Movie.start_year == year)
        statement = statement.order_by(Movie.imdb_id if order == "asc" else Movie.imdb_id.desc())
    else:
        if order == "asc":
            statement = statement.order_by(Movie.start_year.asc(), Movie.imdb_id.asc())
        else:
            statement = statement.order_by(Movie.start_year.desc(), Movie.imdb_id.desc())

    statement = statement.offset(offset).limit(limit)
    return session.exec(statement).all()


@app.get("/movies/{movie_id}")
def read_movie(movie_id: str, session: SessionDep) -> Movie:
    """
    Get a movie with all the information:

    - **imdb_id**: each movie must have an imdb id
    - **name**: each movie must have a name
    - **description**: plot description
    - **poster_url**: optional poster url
    - **start_year**: required
    """
    movie = session.get(Movie, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


@app.delete("/movies/", status_code=status.HTTP_204_NO_CONTENT)
def delete_movie(session: SessionDep, movie_id: str) -> Response:
    movie = session.get(Movie, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    session.delete(movie)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
def read_user_info(
    user_id: Annotated[int, Query(ge=1)],
    session: SessionDep,
):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.put("/users/")
def update_user_info(user: User, session: SessionDep):
    old_user = session.get(User, user.user_id)
    if not old_user:
        raise HTTPException(status_code=404, detail="User not found")

    data = user.model_dump(exclude_unset=True, exclude={"user_id"})

    for k, v in data.items():
        setattr(old_user, k, v)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists"
        )

    session.refresh(old_user)
    return {"msg": "Record updated"}


@app.post("/register/", status_code=status.HTTP_201_CREATED)
def create_user(user: User, session: SessionDep) -> User:
    try:
        session.add(user)
        session.commit()
        session.refresh(user)
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Username already taken")

    return user


@app.post("/watched/", status_code=status.HTTP_201_CREATED)
def create_watched_record(watch_later: WatchLater, session: SessionDep) -> WatchLater:
    user = session.get(User, watch_later.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    movie = session.get(Movie, watch_later.movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    if watch_later.score is not None and not (1 <= watch_later.score <= 10):
        raise HTTPException(status_code=422, detail="The score should be between 1 and 10")
    if watch_later.watched_at is not None and watch_later.watched_at > date.today().isoformat():
        raise HTTPException(status_code=422, detail="The watch date should be before or equal today")

    try:
        session.add(watch_later)
        session.commit()
        session.refresh(watch_later)
        if watch_later.score is not None:
            calculate_average_score(watch_later.movie_id, session)
        return watch_later
    except IntegrityError:
        session.rollback()
        updated = update_watch_later_record(watch_later, session)  # should return the DB entity
        if watch_later.score is not None:
            calculate_average_score(watch_later.movie_id, session)
        return updated


@app.put("/watched/")
def update_watch_later_record(new_watch_later: WatchLater, session: SessionDep):
    statement = select(WatchLater).where(
        WatchLater.user_id == new_watch_later.user_id,
        WatchLater.movie_id == new_watch_later.movie_id,
    )
    old = session.exec(statement).one_or_none()
    if old is None:
        raise HTTPException(status_code=404, detail="Record not found")

    data = new_watch_later.model_dump(exclude_unset=True, exclude={"user_id", "movie_id"})



    if "watched_at" in data:
        if data["watched_at"] is not None:
            if data["watched_at"] > date.today():
                raise HTTPException(status_code=422, detail="The watch date should be before or equal today")
        else:
            data["watched_at"] = date.today()

    if "score" in data:
        if data["score"] is not None and not (1 <= data["score"] <= 10):
            raise HTTPException(status_code=422, detail="The score should be between 1 and 10")

    for k, v in data.items():
        setattr(old, k, v)

    # Recompute average only if score actually changed
    score_changed = "score" in data and data["score"] != old.score

    session.flush()  # persist changes so calculations see them
    if score_changed:
        calculate_average_score(old.movie_id, session)

    session.commit()
    session.refresh(old)
    return old


@app.post("/watchlater/", status_code=status.HTTP_201_CREATED)
def create_watch_later_record(watch_later: WatchLater, session: SessionDep) -> WatchLater:
    user = session.get(User, watch_later.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    movie = session.get(Movie, watch_later.movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    try:
        session.add(watch_later)
        session.commit()
        session.refresh(watch_later)
        return watch_later
    except IntegrityError:
        session.rollback()
        updated = update_watch_later_record(watch_later, session)
        return updated

@app.get("/watchlater/{user_id}")
def read_users_watch_later(
    user_id: Annotated[int, Path(ge=1)],
    session: SessionDep,
) -> list[WatchLater]:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    statement = (
        select(WatchLater)
        .where(
            WatchLater.user_id == user_id,
            WatchLater.watched_at.is_(None)
        )
        .order_by(WatchLater.movie_id)
    )
    items = session.exec(statement).all()

    return items


@app.get("/watched/{user_id}")
def read_users_watched(
    user_id: Annotated[int, Path(ge=1)],
    session: SessionDep,
) -> list[WatchLater]:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    statement = (
        select(WatchLater)
        .where(
            WatchLater.user_id == user_id,
            WatchLater.watched_at.is_not(None)
        )
        .order_by(WatchLater.watched_at.desc(), WatchLater.movie_id)
    )
    return session.exec(statement).all()


@app.get("/")
def read_root():
    return {"Cool": "Movies"}