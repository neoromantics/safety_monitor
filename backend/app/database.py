from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
os.makedirs(data_dir, exist_ok=True)
db_path = os.path.abspath(os.path.join(data_dir, "safety_system.db"))
DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    confidence = Column(Float)
    source = Column(String)
    model_info = Column(String)
    status = Column(String, default="open") # open, acknowledged, resolved

def init_db():
    Base.metadata.create_all(bind=engine)
