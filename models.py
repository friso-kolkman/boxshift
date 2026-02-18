from datetime import date, datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Date, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="new")  # new / contacted / converted


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    vermogen_estimate = Column(Integer, default=0)
    broker = Column(String, default="degiro")  # degiro / ib / lynx / other
    situation = Column(String, default="particulier")  # particulier / startup_employee / dga
    created_at = Column(DateTime, default=datetime.utcnow)

    bvs = relationship("BV", back_populates="user")


class BV(Base):
    __tablename__ = "bvs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    kvk_number = Column(String, nullable=True)
    oprichtingsdatum = Column(Date, nullable=True)
    status = Column(String, default="pending")  # pending / active / inactive

    user = relationship("User", back_populates="bvs")
    transactions = relationship("Transaction", back_populates="bv")
    holdings = relationship("Holding", back_populates="bv")
    annual_reports = relationship("AnnualReport", back_populates="bv")
    vpb_filings = relationship("VPBFiling", back_populates="bv")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    bv_id = Column(Integer, ForeignKey("bvs.id"), nullable=False)
    date = Column(Date, nullable=False)
    type = Column(String, nullable=False)  # buy / sell / dividend / interest / cost / deposit / withdrawal
    ticker = Column(String, nullable=True)
    description = Column(String, nullable=False)
    quantity = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    amount = Column(Float, nullable=False)  # positive=in, negative=out
    currency = Column(String, default="EUR")
    broker_ref = Column(String, nullable=True)
    category = Column(String, nullable=True)  # AI-classified
    processed = Column(Boolean, default=False)

    bv = relationship("BV", back_populates="transactions")


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True)
    bv_id = Column(Integer, ForeignKey("bvs.id"), nullable=False)
    ticker = Column(String, nullable=False)
    name = Column(String, nullable=False)
    quantity = Column(Float, default=0)
    avg_cost_price = Column(Float, default=0)
    total_cost = Column(Float, default=0)

    bv = relationship("BV", back_populates="holdings")


class AnnualReport(Base):
    __tablename__ = "annual_reports"

    id = Column(Integer, primary_key=True)
    bv_id = Column(Integer, ForeignKey("bvs.id"), nullable=False)
    year = Column(Integer, nullable=False)
    balans = Column(JSON, nullable=True)
    winst_verlies = Column(JSON, nullable=True)
    status = Column(String, default="draft")  # draft / final
    generated_at = Column(DateTime, default=datetime.utcnow)

    bv = relationship("BV", back_populates="annual_reports")


class VPBFiling(Base):
    __tablename__ = "vpb_filings"

    id = Column(Integer, primary_key=True)
    bv_id = Column(Integer, ForeignKey("bvs.id"), nullable=False)
    year = Column(Integer, nullable=False)
    taxable_profit = Column(Float, default=0)
    vpb_amount = Column(Float, default=0)
    status = Column(String, default="draft")  # draft / ready / filed

    bv = relationship("BV", back_populates="vpb_filings")


def init_db(database_url):
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session
