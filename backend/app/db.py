import logging
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from . import config
from .models import Base, User, KnowledgeBase, Document
from .security import hash_password

log = logging.getLogger("cloudrag.db")
engine = None
replica_engine = None
SessionLocal = None
active_database = "uninitialized"
startup_warning = ""


def _sqlite_engine():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    eng = create_engine(f"sqlite:///{config.SQLITE_PATH}", connect_args={"check_same_thread": False, "timeout": 20})
    @event.listens_for(eng, "connect")
    def configure_sqlite(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()
    return eng


def _mysql_engine(host: str):
    url = URL.create("mysql+pymysql", username=config.RDS_USER, password=config.RDS_PASSWORD,
                     host=host, port=config.RDS_PORT, database=config.RDS_DATABASE,
                     query={"charset": "utf8mb4"})
    return create_engine(url, pool_pre_ping=True, pool_recycle=1500, pool_size=4,
                         max_overflow=2, connect_args={"connect_timeout": 4, "read_timeout": 12, "write_timeout": 12})


def initialize():
    global engine, replica_engine, SessionLocal, active_database, startup_warning
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    if not config.ADMIN_PASSWORD or len(config.ADMIN_PASSWORD) < 12:
        raise RuntimeError("ADMIN_PASSWORD must be at least 12 characters; use deploy.sh")
    if config.DB_MODE not in ("auto", "sqlite", "rds"):
        raise RuntimeError("DB_MODE must be auto, sqlite, or rds")
    chosen = None
    if config.DB_MODE != "sqlite" and config.RDS_HOST:
        try:
            chosen = _mysql_engine(config.RDS_HOST)
            with chosen.connect() as conn:
                conn.execute(text("SELECT 1"))
            Base.metadata.create_all(bind=chosen)
            active_database = "RDS MySQL"
            log.info("Connected to Huawei RDS MySQL")
        except Exception as exc:
            if chosen is not None:
                chosen.dispose()
            if config.DB_MODE == "rds":
                raise RuntimeError(f"RDS mode requires a working RDS database: {type(exc).__name__}: {exc}") from exc
            startup_warning = "RDS unreachable; using local SQLite. Data is NOT migrated automatically when switching modes."
            log.warning("RDS unavailable (%s); falling back to local SQLite", type(exc).__name__)
            chosen = None
    elif config.DB_MODE == "rds":
        raise RuntimeError("RDS_HOST is required when DB_MODE=rds")
    if chosen is None:
        chosen = _sqlite_engine()
        Base.metadata.create_all(bind=chosen)
        active_database = "Local SQLite"
        log.info("Using persistent local SQLite database")
    engine = chosen
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    if active_database == "RDS MySQL" and config.RDS_REPLICA_HOST:
        try:
            replica_engine = _mysql_engine(config.RDS_REPLICA_HOST)
            with replica_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            log.warning("Replica unavailable (%s); analytics will use primary", type(exc).__name__)
            if replica_engine:
                replica_engine.dispose()
            replica_engine = None
    with SessionLocal() as session:
        # Interrupted jobs must be retryable after a restart.
        for interrupted in session.query(Document).filter(Document.state == "processing").all():
            interrupted.state = "failed"
            interrupted.error = "Interrupted by application restart. Use Retry to re-index."
        admin = session.query(User).filter(User.email == config.ADMIN_EMAIL).first()
        if not admin:
            session.add(User(email=config.ADMIN_EMAIL, role="admin", password_hash=hash_password(config.ADMIN_PASSWORD)))
            log.info("Created initial admin account")
        if not session.query(KnowledgeBase).first():
            session.add(KnowledgeBase(name="CloudNova Technologies", description="Sample company knowledge base for the Huawei Cloud RAG laboratory"))
        session.commit()


def get_db():
    if SessionLocal is None:
        raise RuntimeError("Database not initialized")
    with SessionLocal() as session:
        yield session


def reporting_session():
    """Read-only reports can use replica when available. A replica may be delayed."""
    return sessionmaker(bind=replica_engine or engine, autoflush=False, expire_on_commit=False)()
