# backend/app/models/ck_metric.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Index
from sqlalchemy.orm import relationship

# Import Base from the backend's base class definition
from shared.db.base_class import Base
from shared.db.models.repository import Repository

class CKMetric(Base):
    __tablename__ = 'ck_metrics'

    id = Column(Integer, primary_key=True, index=True)

    # Foreign key to the repository this metric belongs to
    repository_id = Column(Integer, ForeignKey('repositories.id'), nullable=False, index=True)
    # Link back to the Repository model (optional but good practice)
    repository = relationship("Repository") # Assumes you have a Repository model

    commit_hash = Column(String, nullable=False, index=True)
    file = Column(String, nullable=False) # Path to the source file

    # Rename 'class' column from CK output to avoid Python keyword conflict
    class_name = Column("class", String, nullable=True) # Map to 'class' column in DB

    # --- Common CK Metrics (Add ALL metrics present in your ck class.csv) ---
    # Add others as needed, use Float for most, Integer for counts like NOC
    cbo = Column(Float, nullable=True)
    wmc = Column(Float, nullable=True) # Or Integer if always whole number
    dic = Column(Integer, nullable=True)
    noc = Column(Integer, nullable=True)
    rfc = Column(Float, nullable=True) # Or Integer
    lcom = Column(Float, nullable=True)
    lcom_norm = Column("lcom*", Float, nullable=True) # Handle special chars in column name if needed
    loc = Column(Integer, nullable=True)
    dit = Column(Integer, nullable=True)
    nosi = Column(Integer, nullable=True) # Or Float
    # Add ALL other metrics from CK output: nom, nopm, nopa, etc.
    # Example:
    # nom = Column(Integer, nullable=True)
    # nopm = Column(Integer, nullable=True)
    # ...

    # Add table args for composite indexes if needed, e.g., for faster lookups
    # __table_args__ = (Index('ix_ckmetric_repo_commit_file', "repository_id", "commit_hash", "file"), )

    def __repr__(self):
        return f"<CKMetric(commit='{self.commit_hash}', file='{self.file}', class='{self.class_name}')>"