# shared/db/models/ck_metric.py
from sqlalchemy import Column, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from shared.db.base_class import Base

# Assuming Repository model is also in shared/db/models
# from shared.db.models.repository import Repository # Not strictly needed for definition


class CKMetric(Base):
    # NOTE: Attribute names use CamelCase to directly match CK tool output headers,
    # deviating from Python's standard snake_case convention for easier mapping.
    # Explicit Column("DbName", ...) is used to ensure DB column names also match CK headers.
    # Keywords ('class', 'type') are handled explicitly.
    __tablename__ = "ck_metrics"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(
        Integer,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Link back to the Repository model (optional but good practice)
    repository = relationship("Repository")  # Assumes you have a Repository model

    commit_hash = Column(String, nullable=False, index=True)

    # --- CK Metrics (Using CamelCase Python attributes mapped to CamelCase DB columns) ---
    file = Column(String, nullable=False, index=True)
    # Explicit handling for keyword 'class'
    class_name = Column("class", String, nullable=True, index=True)
    # Explicit handling for keyword 'type'
    type_ = Column("type", String, nullable=True)

    cbo = Column(Float, nullable=True)
    # Python attribute 'cboModified' maps to DB column 'cboModified'
    cboModified = Column("cboModified", Float, nullable=True)
    fanin = Column(Integer, nullable=True)
    fanout = Column(Integer, nullable=True)
    wmc = Column(Float, nullable=True)
    dit = Column(Integer, nullable=True)
    noc = Column(Integer, nullable=True)
    rfc = Column(Float, nullable=True)
    lcom = Column(Float, nullable=True)
    lcom_norm = Column(Float, nullable=True)
    tcc = Column(Float, nullable=True)
    lcc = Column(Float, nullable=True)

    # --- Method Quantities ---
    totalMethodsQty = Column("totalMethodsQty", Integer, nullable=True)
    staticMethodsQty = Column("staticMethodsQty", Integer, nullable=True)
    publicMethodsQty = Column("publicMethodsQty", Integer, nullable=True)
    privateMethodsQty = Column("privateMethodsQty", Integer, nullable=True)
    protectedMethodsQty = Column("protectedMethodsQty", Integer, nullable=True)
    defaultMethodsQty = Column("defaultMethodsQty", Integer, nullable=True)
    visibleMethodsQty = Column("visibleMethodsQty", Integer, nullable=True)
    abstractMethodsQty = Column("abstractMethodsQty", Integer, nullable=True)
    finalMethodsQty = Column("finalMethodsQty", Integer, nullable=True)
    synchronizedMethodsQty = Column("synchronizedMethodsQty", Integer, nullable=True)

    # --- Field Quantities ---
    totalFieldsQty = Column("totalFieldsQty", Integer, nullable=True)
    staticFieldsQty = Column("staticFieldsQty", Integer, nullable=True)
    publicFieldsQty = Column("publicFieldsQty", Integer, nullable=True)
    privateFieldsQty = Column("privateFieldsQty", Integer, nullable=True)
    protectedFieldsQty = Column("protectedFieldsQty", Integer, nullable=True)
    defaultFieldsQty = Column("defaultFieldsQty", Integer, nullable=True)
    finalFieldsQty = Column("finalFieldsQty", Integer, nullable=True)
    synchronizedFieldsQty = Column("synchronizedFieldsQty", Integer, nullable=True)

    # --- Other Metrics ---
    nosi = Column(Integer, nullable=True)
    loc = Column(Integer, nullable=True)
    returnQty = Column("returnQty", Integer, nullable=True)
    loopQty = Column("loopQty", Integer, nullable=True)
    comparisonsQty = Column("comparisonsQty", Integer, nullable=True)
    tryCatchQty = Column("tryCatchQty", Integer, nullable=True)
    parenthesizedExpsQty = Column("parenthesizedExpsQty", Integer, nullable=True)
    stringLiteralsQty = Column("stringLiteralsQty", Integer, nullable=True)
    numbersQty = Column("numbersQty", Integer, nullable=True)
    assignmentsQty = Column("assignmentsQty", Integer, nullable=True)
    mathOperationsQty = Column("mathOperationsQty", Integer, nullable=True)
    variablesQty = Column("variablesQty", Integer, nullable=True)
    maxNestedBlocksQty = Column("maxNestedBlocksQty", Integer, nullable=True)
    anonymousClassesQty = Column("anonymousClassesQty", Integer, nullable=True)
    innerClassesQty = Column("innerClassesQty", Integer, nullable=True)
    lambdasQty = Column("lambdasQty", Integer, nullable=True)
    uniqueWordsQty = Column("uniqueWordsQty", Integer, nullable=True)
    modifiers = Column(Integer, nullable=True)
    logStatementsQty = Column("logStatementsQty", Integer, nullable=True)

    # --- Relationship (optional but useful) ---
    repository = relationship("Repository")  # Specify back_populates if needed

    __table_args__ = (
        UniqueConstraint(
            "repository_id", "commit_hash", "file", "class", name="uq_ck_metric_key"
        ),
        # You can add other indexes here if needed, e.g.:
        # Index('ix_ck_metric_repo_commit_file', 'repository_id', 'commit_hash', 'file'),
    )

    def __repr__(self):
        # Use the mapped attribute name 'class_name' here
        return f"<CKMetric(commit='{self.commit_hash}', file='{self.file}', class='{self.class_name}')>"
