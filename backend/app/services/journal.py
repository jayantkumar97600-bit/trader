from sqlalchemy import create_engine, String, Float, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[str] = mapped_column(String(64))
    asset: Mapped[str] = mapped_column(String(32))
    direction: Mapped[str] = mapped_column(String(8))
    entry: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    take_profit: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    result: Mapped[str] = mapped_column(String(32), default="OPEN")
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_timestamp: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exit_timestamp: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees: Mapped[float | None] = mapped_column(Float, nullable=True)


engine = create_engine(
    "sqlite:///./trading.db",
    connect_args={"check_same_thread": False},
)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def _trade_dict(t: Trade) -> dict:
    return {
        c.name: getattr(t, c.name)
        for c in Trade.__table__.columns
    }


def add_trade(data):
    s = Session()

    try:
        t = Trade(**data)
        s.add(t)
        s.commit()
        s.refresh(t)
        return _trade_dict(t)
    finally:
        s.close()


def list_trades():
    s = Session()

    try:
        rows = (
            s.query(Trade)
            .order_by(Trade.id.desc())
            .all()
        )

        return [_trade_dict(r) for r in rows]
    finally:
        s.close()


def get_open_trades():
    s = Session()

    try:
        rows = (
            s.query(Trade)
            .filter(Trade.result == "OPEN")
            .order_by(Trade.id.asc())
            .all()
        )

        return [_trade_dict(r) for r in rows]
    finally:
        s.close()


def close_trade(
    trade_id: int,
    exit_price: float,
    exit_timestamp: str,
    exit_reason: str,
    fees: float = 0.0,
):
    s = Session()

    try:
        trade = (
            s.query(Trade)
            .filter(Trade.id == trade_id)
            .first()
        )

        if trade is None:
            raise ValueError(f"Trade {trade_id} not found.")

        if trade.result != "OPEN":
            raise ValueError(
                f"Trade {trade_id} is already closed."
            )

        entry = float(trade.entry)
        stop_loss = float(trade.stop_loss)
        exit_price = float(exit_price)

        risk_per_unit = abs(entry - stop_loss)

        if risk_per_unit <= 0:
            raise ValueError(
                f"Trade {trade_id} has invalid risk distance."
            )

        if trade.direction == "LONG":
            pnl_per_unit = exit_price - entry
        elif trade.direction == "SHORT":
            pnl_per_unit = entry - exit_price
        else:
            raise ValueError(
                f"Trade {trade_id} has invalid direction: "
                f"{trade.direction}"
            )

        r_multiple = pnl_per_unit / risk_per_unit

        trade.result = "CLOSED"
        trade.exit_timestamp = exit_timestamp
        trade.exit_price = exit_price
        trade.exit_reason = exit_reason
        trade.r_multiple = r_multiple
        trade.fees = float(fees)

        s.commit()
        s.refresh(trade)

        return _trade_dict(trade)

    finally:
        s.close()
