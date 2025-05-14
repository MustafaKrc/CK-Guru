from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# Import SQLAlchemy stuff needed for testing expressions
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Session, aliased

# Import models used
from shared.db.models import BotPattern, CKMetric, CommitGuruMetric
from shared.db.models.bot_pattern import PatternTypeEnum

# Import functions and classes to test
from worker.dataset.services.dataset_steps import (
    CK_METRIC_COLUMNS,  # Import for checking columns
)
from worker.dataset.services.dataset_steps import (
    calculate_delta_metrics,
    get_bot_filter_condition,
    get_parent_ck_metrics,
)

# --- Mock Setup ---


# Mock the base class for SQLAlchemy models for type hinting
class MockBase(DeclarativeBase):
    pass


class MockCommitGuruMetric(MockBase):
    __tablename__ = "commit_guru_metrics_mock"
    id = sa.Column(sa.Integer, primary_key=True)
    author_name = sa.Column(sa.String)
    # Add other columns if needed by specific tests, but author_name is key for bot filter


# --- Tests for get_bot_filter_condition ---


# Helper to compile and check SQL fragment (simplistic check)
def check_sql(condition, expected_substrings, disallowed_substrings=None):
    """Compiles SQL condition and checks for substrings."""
    from sqlalchemy.dialects import postgresql

    compiled = condition.compile(dialect=postgresql.dialect())
    sql_string = str(compiled).lower()
    params = compiled.params
    # print(f"\nSQL: {sql_string}\nParams: {params}\n") # For debugging
    for sub in expected_substrings:
        assert sub.lower() in sql_string
    if disallowed_substrings:
        for sub in disallowed_substrings:
            assert (
                sub.lower() not in sql_string
            )  # Check things that *shouldn't* be there


def test_get_bot_filter_no_patterns():
    """Test when no bot patterns are provided."""
    cgm_alias = aliased(MockCommitGuruMetric)
    condition = get_bot_filter_condition([], cgm_alias)
    # A 'false' condition often compiles to something like '1 != 1' or 'false'
    # Check if it evaluates to false or its string representation indicates falsity
    assert str(condition) == "false"


def test_get_bot_filter_only_inclusion_exact():
    """Test only exact inclusion patterns."""
    patterns = [
        BotPattern(
            pattern="dependabot[bot]",
            pattern_type=PatternTypeEnum.EXACT,
            is_exclusion=False,
        )
    ]
    cgm_alias = aliased(MockCommitGuruMetric)
    condition = get_bot_filter_condition(patterns, cgm_alias)
    # Expects: alias.author_name = 'dependabot[bot]'
    check_sql(condition, ["commit_guru_metrics_mock_1.author_name = %(author_name_1)s"])


def test_get_bot_filter_only_inclusion_wildcard():
    """Test only wildcard inclusion patterns."""
    patterns = [
        BotPattern(
            pattern="*bot*", pattern_type=PatternTypeEnum.WILDCARD, is_exclusion=False
        )
    ]
    cgm_alias = aliased(MockCommitGuruMetric)
    condition = get_bot_filter_condition(patterns, cgm_alias)
    # Expects: alias.author_name LIKE '%bot%'
    check_sql(
        condition, ["commit_guru_metrics_mock_1.author_name like %(author_name_1)s"]
    )


def test_get_bot_filter_only_inclusion_regex():
    """Test only regex inclusion patterns."""
    patterns = [
        BotPattern(
            pattern="^[a-z]+-bot$",
            pattern_type=PatternTypeEnum.REGEX,
            is_exclusion=False,
        )
    ]
    cgm_alias = aliased(MockCommitGuruMetric)
    condition = get_bot_filter_condition(patterns, cgm_alias)
    # Expects: alias.author_name ~ '^[a-z]+-bot$' (or REGEXP_MATCH depending on dialect)
    check_sql(condition, ["commit_guru_metrics_mock_1.author_name ~ %(author_name_1)s"])


def test_get_bot_filter_only_exclusion_exact():
    """Test only exact exclusion patterns."""
    patterns = [
        BotPattern(
            pattern="admin", pattern_type=PatternTypeEnum.EXACT, is_exclusion=True
        )
    ]
    cgm_alias = aliased(MockCommitGuruMetric)
    condition = get_bot_filter_condition(patterns, cgm_alias)
    # Expects: NOT (alias.author_name = 'admin') -> compiles to != or similar
    check_sql(
        condition, ["commit_guru_metrics_mock_1.author_name = %(author_name_1)s"]
    )  # Should be simple negation
    # We can't reliably assert "not" or "!=" as it depends on compilation details
    # So check the core column/param and lack of complex operators.


def test_get_bot_filter_mixed_patterns():
    """Test a mix of inclusion and exclusion patterns."""
    patterns = [
        BotPattern(
            pattern="dependabot[bot]",
            pattern_type=PatternTypeEnum.EXACT,
            is_exclusion=False,
        ),
        BotPattern(
            pattern="*actions*",
            pattern_type=PatternTypeEnum.WILDCARD,
            is_exclusion=False,
        ),
        BotPattern(
            pattern="admin", pattern_type=PatternTypeEnum.EXACT, is_exclusion=True
        ),
        BotPattern(
            pattern="test-user", pattern_type=PatternTypeEnum.EXACT, is_exclusion=True
        ),
    ]
    cgm_alias = aliased(MockCommitGuruMetric)
    condition = get_bot_filter_condition(patterns, cgm_alias)
    # Expects roughly: NOT( (name = 'admin') OR (name = 'test-user') )
    #             AND ( (name = 'dependabot[bot]') OR (name LIKE '%actions%') )
    check_sql(
        condition,
        [
            "or",  # Basic structure now uses OR between exclusion OR and inclusion OR
            "author_name = %(author_name_1)s",  # admin (exclusion)
            "author_name = %(author_name_2)s",  # test-user (exclusion)
            "author_name = %(author_name_3)s",  # dependabot (inclusion)
            "author_name like %(author_name_4)s",  # actions (inclusion)
        ],
        disallowed_substrings=["and"],
    )  # Top level should now be OR


# --- Tests for get_parent_ck_metrics ---


@pytest.fixture
def mock_db_session():
    """Fixture for mocking SQLAlchemy Session."""
    session = MagicMock(spec=Session)
    execute_mock = MagicMock()
    session.execute.return_value = execute_mock
    scalars_mock = MagicMock()
    execute_mock.scalars.return_value = scalars_mock
    scalars_mock.all.return_value = []  # Default empty
    return session


def test_get_parent_metrics_all_found(mock_db_session):
    """Test when parents are found for all rows."""
    input_df = pd.DataFrame(
        {
            "repository_id": [1, 1],
            "commit_hash": ["c2", "c3"],
            "parent_hashes": ["c1", "c2 other"],  # Test multi-parent, uses first
            "file": ["a.py", "b.py"],
            "class_name": ["ClassA", "ClassB"],
            "id": [10, 11],  # Include index column if needed
        }
    )
    # Mock parent metrics found in DB
    parent_metric_c1 = CKMetric(
        repository_id=1,
        commit_hash="c1",
        file="a.py",
        class_name="ClassA",
        loc=10,
        wmc=5,
    )
    parent_metric_c2 = CKMetric(
        repository_id=1,
        commit_hash="c2",
        file="b.py",
        class_name="ClassB",
        loc=20,
        wmc=8,
    )
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = [
        parent_metric_c1,
        parent_metric_c2,
    ]

    result_df = get_parent_ck_metrics(mock_db_session, input_df)

    assert len(result_df) == 2
    assert list(result_df.index) == list(input_df.index)
    assert "_parent_metric_found" in result_df.columns
    assert result_df["_parent_metric_found"].all()  # All should be True
    assert "parent_loc" in result_df.columns
    assert "parent_wmc" in result_df.columns
    assert result_df.loc[input_df.index[0], "parent_loc"] == 10
    assert result_df.loc[input_df.index[0], "parent_wmc"] == 5
    assert result_df.loc[input_df.index[1], "parent_loc"] == 20
    assert result_df.loc[input_df.index[1], "parent_wmc"] == 8


def test_get_parent_metrics_some_not_found_db(mock_db_session):
    """Test when some parent metrics are not in the mocked DB response."""
    input_df = pd.DataFrame(
        {
            "repository_id": [1, 1],
            "commit_hash": ["c2", "c3"],
            "parent_hashes": ["c1", "c1_missing"],  # c1_missing won't be found
            "file": ["a.py", "b.py"],
            "class_name": ["ClassA", "ClassB"],
            "id": [10, 11],
        }
    )
    parent_metric_c1 = CKMetric(
        repository_id=1, commit_hash="c1", file="a.py", class_name="ClassA", loc=10
    )
    # Only return the metric for c1
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = [
        parent_metric_c1
    ]

    result_df = get_parent_ck_metrics(mock_db_session, input_df)

    assert len(result_df) == 2
    assert result_df.loc[input_df.index[0], "_parent_metric_found"] == True
    assert result_df.loc[input_df.index[1], "_parent_metric_found"] == False
    assert result_df.loc[input_df.index[0], "parent_loc"] == 10
    assert pd.isna(
        result_df.loc[input_df.index[1], "parent_loc"]
    )  # Should be NaN if not found


def test_get_parent_metrics_no_parent_hash(mock_db_session):
    """Test when a commit has no parent hash (e.g., initial commit)."""
    input_df = pd.DataFrame(
        {
            "repository_id": [1],
            "commit_hash": ["c1_initial"],
            "parent_hashes": [None],  # No parent
            "file": ["a.py"],
            "class_name": ["ClassA"],
            "id": [10],
        }
    )
    # Mock DB returns nothing (though it shouldn't even be queried)
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = []

    result_df = get_parent_ck_metrics(mock_db_session, input_df)

    assert len(result_df) == 1
    assert result_df.loc[input_df.index[0], "_parent_metric_found"] == False
    assert pd.isna(result_df.loc[input_df.index[0], "parent_loc"])
    mock_db_session.execute.assert_not_called()  # Should not query DB if no lookup keys


def test_get_parent_metrics_empty_input(mock_db_session):
    """Test with an empty input DataFrame."""
    input_df = pd.DataFrame(
        columns=[
            "repository_id",
            "commit_hash",
            "parent_hashes",
            "file",
            "class_name",
            "id",
        ]
    )
    result_df = get_parent_ck_metrics(mock_db_session, input_df)
    assert result_df.empty
    assert "_parent_metric_found" in result_df.columns  # Check schema still created
    mock_db_session.execute.assert_not_called()


# --- Tests for calculate_delta_metrics ---


def test_calculate_delta_metrics_basic():
    """Test basic delta calculation."""
    input_df = pd.DataFrame(
        {
            "loc": [100, 50],
            "wmc": [10, 20],
            "parent_loc": [90, 45],
            "parent_wmc": [8, 22],
            "_parent_metric_found": [True, True],
            "other_col": ["a", "b"],  # Non-metric column
        }
    )
    result_df = calculate_delta_metrics(input_df)

    assert "d_loc" in result_df.columns
    assert "d_wmc" in result_df.columns
    assert "parent_loc" not in result_df.columns  # Parent cols dropped
    assert "parent_wmc" not in result_df.columns
    assert "other_col" in result_df.columns  # Other cols kept

    pd.testing.assert_series_equal(
        result_df["d_loc"], pd.Series([10.0, 5.0]), check_names=False
    )
    pd.testing.assert_series_equal(
        result_df["d_wmc"], pd.Series([2.0, -2.0]), check_names=False
    )


def test_calculate_delta_metrics_parent_not_found():
    """Test delta calculation when parent was not found."""
    input_df = pd.DataFrame(
        {
            "loc": [100, 50],
            "parent_loc": [90, np.nan],  # NaN for second row's parent
            "_parent_metric_found": [True, False],
        }
    )
    result_df = calculate_delta_metrics(input_df)

    assert result_df.loc[0, "d_loc"] == 10.0
    assert pd.isna(result_df.loc[1, "d_loc"])  # Delta should be NaN


def test_calculate_delta_metrics_with_nans():
    """Test delta calculation with NaNs in current or parent."""
    input_df = pd.DataFrame(
        {
            "loc": [100, np.nan, 50],
            "parent_loc": [90, 45, np.nan],
            "_parent_metric_found": [
                True,
                True,
                True,
            ],  # Assume parent row existed but value was NaN
        }
    )
    result_df = calculate_delta_metrics(input_df)

    assert result_df.loc[0, "d_loc"] == 10.0
    assert pd.isna(result_df.loc[1, "d_loc"])  # Current is NaN
    assert pd.isna(result_df.loc[2, "d_loc"])  # Parent is NaN


def test_calculate_delta_metrics_non_numeric():
    """Test delta calculation with non-numeric data."""
    input_df = pd.DataFrame(
        {
            "loc": [100, "abc"],  # Non-numeric 'abc'
            "parent_loc": [90, 45],
            "_parent_metric_found": [True, True],
        }
    )
    result_df = calculate_delta_metrics(input_df)

    assert result_df.loc[0, "d_loc"] == 10.0
    assert pd.isna(
        result_df.loc[1, "d_loc"]
    )  # Non-numeric coerces to NaN, delta is NaN


def test_calculate_delta_metrics_empty_input():
    """Test delta calculation with empty input."""
    input_df = pd.DataFrame(columns=["loc", "parent_loc", "_parent_metric_found"])
    result_df = calculate_delta_metrics(input_df)
    assert result_df.empty
    assert "d_loc" in result_df.columns  # Check delta column exists in schema


def test_calculate_delta_metrics_preserves_index():
    """Test that the index is preserved."""
    input_df = pd.DataFrame(
        {
            "loc": [100, 50],
            "parent_loc": [90, 45],
            "_parent_metric_found": [True, True],
        },
        index=[10, 20],
    )  # Custom index
    result_df = calculate_delta_metrics(input_df)
    assert list(result_df.index) == [10, 20]
