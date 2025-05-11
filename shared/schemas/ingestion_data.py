# shared/schemas/ingestion_data.py
import math
from typing import Dict, List, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- CK Metric Payload ---


class CKMetricPayload(BaseModel):
    """Pydantic model for a single CK metric record before persistence."""

    # DB identifier fields (added during processing)
    repository_id: Optional[int] = None
    commit_hash: Optional[str] = None

    # Core CK fields (handle aliases)
    file: str  # File path is essential
    class_name: Optional[str] = Field(None, alias="class")
    type_: Optional[str] = Field(None, alias="type")

    # Numeric metrics (use Optional for flexibility)
    cbo: Optional[float] = None
    cboModified: Optional[float] = None
    fanin: Optional[int] = None
    fanout: Optional[int] = None
    wmc: Optional[float] = None
    dit: Optional[int] = None
    noc: Optional[int] = None
    rfc: Optional[float] = None
    lcom: Optional[float] = None
    lcom_norm: Optional[float] = None
    tcc: Optional[float] = None
    lcc: Optional[float] = None
    totalMethodsQty: Optional[int] = None
    staticMethodsQty: Optional[int] = None
    publicMethodsQty: Optional[int] = None
    privateMethodsQty: Optional[int] = None
    protectedMethodsQty: Optional[int] = None
    defaultMethodsQty: Optional[int] = None
    visibleMethodsQty: Optional[int] = None
    abstractMethodsQty: Optional[int] = None
    finalMethodsQty: Optional[int] = None
    synchronizedMethodsQty: Optional[int] = None
    totalFieldsQty: Optional[int] = None
    staticFieldsQty: Optional[int] = None
    publicFieldsQty: Optional[int] = None
    privateFieldsQty: Optional[int] = None
    protectedFieldsQty: Optional[int] = None
    defaultFieldsQty: Optional[int] = None
    finalFieldsQty: Optional[int] = None
    synchronizedFieldsQty: Optional[int] = None
    nosi: Optional[int] = None
    loc: Optional[int] = None
    returnQty: Optional[int] = None
    loopQty: Optional[int] = None
    comparisonsQty: Optional[int] = None
    tryCatchQty: Optional[int] = None
    parenthesizedExpsQty: Optional[int] = None
    stringLiteralsQty: Optional[int] = None
    numbersQty: Optional[int] = None
    assignmentsQty: Optional[int] = None
    mathOperationsQty: Optional[int] = None
    variablesQty: Optional[int] = None
    maxNestedBlocksQty: Optional[int] = None
    anonymousClassesQty: Optional[int] = None
    innerClassesQty: Optional[int] = None
    lambdasQty: Optional[int] = None
    uniqueWordsQty: Optional[int] = None
    modifiers: Optional[int] = None
    logStatementsQty: Optional[int] = None

    model_config = ConfigDict(
        populate_by_name=True,  # Allow using aliases during init
        extra="ignore",  # Ignore extra fields from input dict/df
    )

    # Validator to replace NaN/Inf with None for numeric fields
    @field_validator("*", mode="before")
    @classmethod
    def check_nan_inf(cls, v, field_info):
        if isinstance(v, (float, np.floating)) and (math.isnan(v) or math.isinf(v)):
            return None
        return v


# --- Commit Guru Metric Payload ---


class CommitGuruMetricPayload(BaseModel):
    """Pydantic model for Commit Guru metric data for one commit before persistence."""

    # DB identifier fields (added during processing)
    repository_id: Optional[int] = None

    # Core Commit Info
    commit_hash: str
    parent_hashes: Optional[str] = None
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    author_date: Optional[str] = (
        None  # Keep as string from git log? Or parse to datetime?
    )
    author_date_unix_timestamp: Optional[int] = None
    commit_message: Optional[str] = None

    # Bug Linking Info (set during processing/linking)
    is_buggy: bool = False  # Default
    fix: bool = False  # Set based on keywords during calculation
    fixing_commit_hashes: Optional[Dict[str, List[str]]] = None  # Set by LinkBugs step

    # Commit Guru Metrics
    files_changed: Optional[List[str]] = []
    ns: Optional[float] = None
    nd: Optional[float] = None
    nf: Optional[float] = None
    entropy: Optional[float] = None
    la: Optional[float] = None
    ld: Optional[float] = None
    lt: Optional[float] = None
    ndev: Optional[float] = None
    age: Optional[float] = None
    nuc: Optional[float] = None
    exp: Optional[float] = None
    rexp: Optional[float] = None
    sexp: Optional[float] = None

    model_config = ConfigDict(extra="ignore")

    # Validator to replace NaN/Inf with None for numeric fields
    @field_validator("*", mode="before")
    @classmethod
    def check_nan_inf(cls, v, field_info):
        if isinstance(v, (float, np.floating)) and (math.isnan(v) or math.isinf(v)):
            return None
        return v
