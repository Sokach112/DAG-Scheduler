import uuid
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "scheduler.db")

engine = create_engine(
    f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class ProjectModel(Base):
    __tablename__ = "projects"
    prid = Column(String, primary_key=True, index=True,
                  default=lambda: uuid.uuid4().hex[:8])
    title = Column(String, default="Untitled Project")
    description = Column(Text, default="")
    origin = Column(DateTime, nullable=True)
    ddl = Column(DateTime, nullable=True)
    events_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow,
                        onupdate=datetime.utcnow)


Base.metadata.create_all(bind=engine)
