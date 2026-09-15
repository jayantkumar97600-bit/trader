from sqlalchemy import create_engine, String, Float, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

class Base(DeclarativeBase): pass
class Trade(Base):
    __tablename__="trades"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    timestamp:Mapped[str]=mapped_column(String(64))
    asset:Mapped[str]=mapped_column(String(32))
    direction:Mapped[str]=mapped_column(String(8))
    entry:Mapped[float]=mapped_column(Float)
    stop_loss:Mapped[float]=mapped_column(Float)
    take_profit:Mapped[float]=mapped_column(Float)
    quantity:Mapped[float]=mapped_column(Float)
    score:Mapped[float]=mapped_column(Float)
    result:Mapped[str]=mapped_column(String(32),default="OPEN")
    r_multiple:Mapped[float|None]=mapped_column(Float,nullable=True)
    notes:Mapped[str|None]=mapped_column(Text,nullable=True)

engine=create_engine("sqlite:///./trading.db",connect_args={"check_same_thread":False})
Base.metadata.create_all(engine)
Session=sessionmaker(bind=engine)

def add_trade(data):
    s=Session(); t=Trade(**data); s.add(t); s.commit(); s.refresh(t)
    out={c.name:getattr(t,c.name) for c in Trade.__table__.columns}; s.close(); return out

def list_trades():
    s=Session(); rows=s.query(Trade).order_by(Trade.id.desc()).all()
    out=[{c.name:getattr(r,c.name) for c in Trade.__table__.columns} for r in rows]; s.close(); return out
