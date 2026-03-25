from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class WeaponCategory(Base):
    __tablename__ = "weapon_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True, comment="分类名称")
    slug = Column(String(50), nullable=False, unique=True, comment="URL标识")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    weapons = relationship("Weapon", back_populates="category")


class Weapon(Base):
    __tablename__ = "weapons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="武器名称")
    slug = Column(String(100), nullable=False, unique=True, comment="URL标识")
    category_id = Column(Integer, ForeignKey("weapon_categories.id"), comment="分类ID")
    image_url = Column(String(500), comment="武器图片URL")
    source_url = Column(String(500), comment="来源页面URL")
    code_count = Column(Integer, default=0, comment="改枪码数量")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    category = relationship("WeaponCategory", back_populates="weapons")
    gun_codes = relationship("GunCode", back_populates="weapon", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_slug", "slug"),
        Index("idx_category", "category_id"),
    )


class GunCode(Base):
    __tablename__ = "gun_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    weapon_id = Column(Integer, ForeignKey("weapons.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(200), nullable=False, comment="改枪码")
    description = Column(String(500), comment="描述")
    value = Column(String(50), comment="价值")
    copy_count = Column(Integer, default=0, comment="复制次数")
    likes = Column(Integer, default=0, comment="点赞数")
    is_hot = Column(Boolean, default=False, comment="是否热门")
    image_url = Column(String(500), comment="配件图URL")
    game_mode = Column(String(50), default="烽火地带", comment="游戏模式")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    weapon = relationship("Weapon", back_populates="gun_codes")

    __table_args__ = (
        Index("uk_code", "code", unique=True),
        Index("idx_weapon", "weapon_id"),
        Index("idx_copy_count", copy_count.desc()),
        Index("idx_likes", likes.desc()),
    )


class CraftingStation(Base):
    __tablename__ = "crafting_stations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_name = Column(String(50), nullable=False, comment="工作台名称")
    item_name = Column(String(100), nullable=False, comment="推荐物品名")
    hourly_profit = Column(Integer, default=0, comment="小时利润")
    item_image_url = Column(String(500), comment="物品图片URL")
    scraped_at = Column(DateTime, default=datetime.now, comment="爬取时间")

    __table_args__ = (Index("idx_station", "station_name"),)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), comment="活动标题")
    items = Column(JSON, comment="活动物品列表")
    countdown_hours = Column(Integer, comment="倒计时小时")
    scraped_at = Column(DateTime, default=datetime.now)


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(50), nullable=False, comment="任务名称")
    status = Column(Enum("running", "success", "failed"), nullable=False)
    items_scraped = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.now)
    finished_at = Column(DateTime)


_engine = None
_SessionLocal = None


def init_db(database_uri: str):
    global _engine, _SessionLocal
    _engine = create_engine(database_uri, pool_pre_ping=True, pool_recycle=3600)
    _SessionLocal = sessionmaker(bind=_engine)
    Base.metadata.create_all(_engine)


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionLocal()
