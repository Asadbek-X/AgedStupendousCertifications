from typing import Optional, Sequence, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy import BigInteger, String, select, delete, func, Integer, Float, DateTime, Text, Index, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert 
import logging

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[Optional[str]] = mapped_column(String)
    first_name: Mapped[Optional[str]] = mapped_column(String)
    language: Mapped[str] = mapped_column(String, default="uz")
    is_premium: Mapped[bool] = mapped_column(default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    views = relationship("MovieView", back_populates="user", cascade="all, delete-orphan")
    ratings = relationship("MovieRating", back_populates="user", cascade="all, delete-orphan")

class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (
        Index('idx_movie_code', 'code'),
        Index('idx_movie_title', 'title'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[int] = mapped_column(BigInteger, unique=True)
    file_id: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    genre: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    year: Mapped[Optional[int]] = mapped_column(Integer)
    country: Mapped[Optional[str]] = mapped_column(String)
    duration: Mapped[Optional[int]] = mapped_column(Integer)  # minutes
    language: Mapped[str] = mapped_column(String, default="uz")
    quality: Mapped[str] = mapped_column(String, default="HD")
    imdb_rating: Mapped[Optional[float]] = mapped_column(Float)
    thumbnail_file_id: Mapped[Optional[str]] = mapped_column(String)
    views_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    views = relationship("MovieView", back_populates="movie", cascade="all, delete-orphan")
    ratings = relationship("MovieRating", back_populates="movie", cascade="all, delete-orphan")

class RequiredChannel(Base):
    __tablename__ = "required_channels"
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    title: Mapped[str] = mapped_column(String)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

class MovieView(Base):
    __tablename__ = "movie_views"
    __table_args__ = (
        Index('idx_views_user_movie', 'user_id', 'movie_id'),
        Index('idx_views_date', 'viewed_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'))
    movie_id: Mapped[int] = mapped_column(Integer, ForeignKey('movies.id', ondelete='CASCADE'))
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="views")
    movie = relationship("Movie", back_populates="views")

class MovieRating(Base):
    __tablename__ = "movie_ratings"
    __table_args__ = (
        Index('idx_rating_user_movie', 'user_id', 'movie_id', unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'))
    movie_id: Mapped[int] = mapped_column(Integer, ForeignKey('movies.id', ondelete='CASCADE'))
    rating: Mapped[int] = mapped_column(Integer)  # 1-5
    review: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="ratings")
    movie = relationship("Movie", back_populates="ratings")

class Database:
    def __init__(self, db_url: str):
        self.engine = create_async_engine(
            db_url, 
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=False
        )
        self.session_maker = async_sessionmaker(
            self.engine, 
            expire_on_commit=False,
            class_=AsyncSession
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")

    # --- User Methods ---
    async def add_user(self, user_id: int, username: str, first_name: str = None):
        async with self.session_maker() as session:
            stmt = (
                pg_insert(User)
                .values(
                    id=user_id, 
                    username=username,
                    first_name=first_name,
                    last_active=datetime.utcnow()
                )
                .on_conflict_do_update(
                    index_elements=[User.id],
                    set_={'last_active': datetime.utcnow(), 'username': username}
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def get_user(self, user_id: int) -> Optional[User]:
        async with self.session_maker() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalars().first()

    async def get_all_user_ids(self) -> Sequence[int]:
        async with self.session_maker() as session:
            result = await session.execute(select(User.id))
            return result.scalars().all()

    async def get_users_count(self) -> int:
        async with self.session_maker() as session:
            result = await session.execute(select(func.count(User.id)))
            return result.scalar_one()

    async def get_active_users_count(self, days: int = 7) -> int:
        """So'nggi N kun ichida aktiv foydalanuvchilar soni"""
        async with self.session_maker() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            result = await session.execute(
                select(func.count(User.id)).where(User.last_active >= cutoff_date)
            )
            return result.scalar_one()

    # --- Movie Methods ---
    async def add_movie(
        self, 
        code: int, 
        file_id: str, 
        title: str, 
        genre: str,
        description: str = None,
        year: int = None,
        country: str = None,
        duration: int = None,
        quality: str = "HD",
        imdb_rating: float = None,
        thumbnail_file_id: str = None
    ) -> Movie:
        async with self.session_maker() as session:
            movie = Movie(
                code=code,
                file_id=file_id,
                title=title,
                genre=genre,
                description=description,
                year=year,
                country=country,
                duration=duration,
                quality=quality,
                imdb_rating=imdb_rating,
                thumbnail_file_id=thumbnail_file_id
            )
            session.add(movie)
            await session.commit()
            await session.refresh(movie)
            return movie

    async def get_movie_by_code(self, code: int) -> Optional[Movie]:
        async with self.session_maker() as session:
            result = await session.execute(
                select(Movie).where(Movie.code == code, Movie.is_active == True)
            )
            return result.scalars().first()

    async def get_movie_by_id(self, movie_id: int) -> Optional[Movie]:
        async with self.session_maker() as session:
            result = await session.execute(select(Movie).where(Movie.id == movie_id))
            return result.scalars().first()

    async def search_movies(self, query: str, limit: int = 10) -> Sequence[Movie]:
        """Kino qidirish"""
        async with self.session_maker() as session:
            search_pattern = f"%{query}%"
            result = await session.execute(
                select(Movie)
                .where(
                    Movie.is_active == True,
                    (Movie.title.ilike(search_pattern) | Movie.genre.ilike(search_pattern))
                )
                .order_by(Movie.views_count.desc())
                .limit(limit)
            )
            return result.scalars().all()

    async def get_movies_by_genre(self, genre: str, limit: int = 20) -> Sequence[Movie]:
        async with self.session_maker() as session:
            result = await session.execute(
                select(Movie)
                .where(Movie.genre.ilike(f"%{genre}%"), Movie.is_active == True)
                .order_by(Movie.views_count.desc())
                .limit(limit)
            )
            return result.scalars().all()

    async def get_top_movies(self, limit: int = 10) -> Sequence[Movie]:
        """Eng ko'p ko'rilgan kinolar"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(Movie)
                .where(Movie.is_active == True)
                .order_by(Movie.views_count.desc())
                .limit(limit)
            )
            return result.scalars().all()

    async def get_recent_movies(self, limit: int = 10) -> Sequence[Movie]:
        """Yangi qo'shilgan kinolar"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(Movie)
                .where(Movie.is_active == True)
                .order_by(Movie.added_at.desc())
                .limit(limit)
            )
            return result.scalars().all()

    async def get_movies_count(self) -> int:
        async with self.session_maker() as session:
            result = await session.execute(
                select(func.count(Movie.id)).where(Movie.is_active == True)
            )
            return result.scalar_one()

    async def update_movie(self, movie_id: int, **kwargs):
        """Kino ma'lumotlarini yangilash"""
        async with self.session_maker() as session:
            result = await session.execute(select(Movie).where(Movie.id == movie_id))
            movie = result.scalars().first()
            if movie:
                for key, value in kwargs.items():
                    if hasattr(movie, key):
                        setattr(movie, key, value)
                await session.commit()

    async def delete_movie(self, movie_id: int):
        """Kinoni o'chirish (soft delete)"""
        await self.update_movie(movie_id, is_active=False)

    # --- Channel Methods ---
    async def get_required_channels(self) -> Sequence[RequiredChannel]:
        async with self.session_maker() as session:
            result = await session.execute(
                select(RequiredChannel)
                .where(RequiredChannel.is_active == True)
                .order_by(RequiredChannel.priority.desc())
            )
            return result.scalars().all()

    async def count_required_channels(self) -> int:
        async with self.session_maker() as session:
            result = await session.execute(
                select(func.count()).select_from(RequiredChannel)
                .where(RequiredChannel.is_active == True)
            )
            return result.scalar_one()

    async def add_required_channel(self, channel_id: int, title: str, priority: int = 0):
        async with self.session_maker() as session:
            channel = RequiredChannel(channel_id=channel_id, title=title, priority=priority)
            session.add(channel)
            await session.commit()

    async def delete_required_channel(self, channel_id: int):
        async with self.session_maker() as session:
            stmt = delete(RequiredChannel).where(RequiredChannel.channel_id == channel_id)
            await session.execute(stmt)
            await session.commit()

    # --- Views & Ratings ---
    async def add_movie_view(self, user_id: int, movie_id: int):
        """Kino ko'rilganini qayd etish"""
        async with self.session_maker() as session:
            # Ko'rishni qayd qilish
            view = MovieView(user_id=user_id, movie_id=movie_id)
            session.add(view)

            # Ko'rishlar sonini oshirish
            result = await session.execute(select(Movie).where(Movie.id == movie_id))
            movie = result.scalars().first()
            if movie:
                movie.views_count += 1

            await session.commit()

    async def add_rating(self, user_id: int, movie_id: int, rating: int, review: str = None):
        """Kinoga baho berish"""
        async with self.session_maker() as session:
            stmt = (
                pg_insert(MovieRating)
                .values(user_id=user_id, movie_id=movie_id, rating=rating, review=review)
                .on_conflict_do_update(
                    index_elements=['user_id', 'movie_id'],
                    set_={'rating': rating, 'review': review}
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def get_movie_rating(self, movie_id: int) -> Tuple[float, int]:
        """Kino reytingini olish (o'rtacha baho, baholar soni)"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(
                    func.avg(MovieRating.rating),
                    func.count(MovieRating.id)
                ).where(MovieRating.movie_id == movie_id)
            )
            avg_rating, count = result.first()
            return (round(avg_rating, 1) if avg_rating else 0.0, count or 0)

    async def get_user_movie_rating(self, user_id: int, movie_id: int) -> Optional[MovieRating]:
        """Foydalanuvchining kinoga bergan bahoini olish"""
        async with self.session_maker() as session:
            result = await session.execute(
                select(MovieRating).where(
                    MovieRating.user_id == user_id,
                    MovieRating.movie_id == movie_id
                )
            )
            return result.scalars().first()

    # --- Statistics ---
    async def get_user_stats(self, user_id: int) -> dict:
        """Foydalanuvchi statistikasi"""
        async with self.session_maker() as session:
            # Ko'rilgan kinolar soni
            views_result = await session.execute(
                select(func.count(MovieView.id)).where(MovieView.user_id == user_id)
            )
            views_count = views_result.scalar_one()

            # Berilgan baholar soni
            ratings_result = await session.execute(
                select(func.count(MovieRating.id)).where(MovieRating.user_id == user_id)
            )
            ratings_count = ratings_result.scalar_one()

            return {
                'views_count': views_count,
                'ratings_count': ratings_count
            }

    async def get_global_stats(self) -> dict:
        """Umumiy statistika"""
        async with self.session_maker() as session:
            users_count = await self.get_users_count()
            movies_count = await self.get_movies_count()

            views_result = await session.execute(select(func.count(MovieView.id)))
            total_views = views_result.scalar_one()

            return {
                'users_count': users_count,
                'movies_count': movies_count,
                'total_views': total_views
            }