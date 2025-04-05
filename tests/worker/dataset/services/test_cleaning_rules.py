import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

# Import rule classes
from worker.dataset.services.cleaning_rules import (
    Rule0DropDuplicates,
    Rule2RemoveRecentCleanLastChange,
    Rule3RemoveEmptyClass,
    Rule4RemoveTrivialGetSet,
    Rule5RemoveNoAddedLines,
    Rule6RemoveCommentOnlyChange,
    Rule7RemoveTrivialMethodChange,
    Rule8RemoveTypeExceptionFiles,
    Rule9RemoveDeadCode,
    Rule10RemoveDataClass,
    Rule11RemoveNoCodeChange,
    Rule12RemoveMarginalChange,
    Rule13RemoveMinimalChange,
    Rule14FilterLargeCommits,
    RuleClusterLargeCommits,
    DEFAULT_X_COLUMNS, # Import if needed for cluster test setup
    DEFAULT_Y_COLUMN,
)

# Mock logger for all tests in this module
@pytest.fixture(autouse=True)
def mock_cleaning_rules_logging():
    with patch('worker.dataset.services.cleaning_rules.logger', MagicMock()):
        yield

# --- Test Data Helper ---
def create_df(data):
    """Helper to create DataFrame for tests."""
    return pd.DataFrame(data)

# --- Test Cases ---

# Rule 0: Drop Duplicates
def test_rule0_no_duplicates():
    rule = Rule0DropDuplicates()
    df = create_df({
        'commit_hash': ['h1', 'h2', 'h1'],
        'file': ['a.py', 'a.py', 'b.py'],
        'class_name': ['C1', 'C1', 'C2'],
        'id': [1, 2, 3]
    })
    result = rule.apply(df, {}, {})
    assert len(result) == 3
    pd.testing.assert_frame_equal(result.reset_index(drop=True), df.reset_index(drop=True))

def test_rule0_simple_duplicates():
    rule = Rule0DropDuplicates()
    df = create_df({
        'commit_hash': ['h1', 'h1', 'h2'],
        'file': ['a.py', 'a.py', 'b.py'],
        'class_name': ['C1', 'C1', 'C2'],
        'other_col': [10, 20, 30], # Keep first based on index
        'id': [1, 2, 3]
    })
    expected = create_df({
        'commit_hash': ['h1', 'h2'],
        'file': ['a.py', 'b.py'],
        'class_name': ['C1', 'C2'],
        'other_col': [10, 30],
        'id': [1, 3] # Keeps row with index 1, drops row with index 2
    })
    result = rule.apply(df, {}, {})
    # Need to reset index for comparison as drop_duplicates preserves original index
    pd.testing.assert_frame_equal(result.reset_index(drop=True), expected.reset_index(drop=True))

def test_rule0_duplicates_with_nan():
    rule = Rule0DropDuplicates()
    df = create_df({
        'commit_hash': ['h1', 'h1', 'h1', 'h2'],
        'file': ['a.py', 'a.py', 'a.py', 'b.py'],
        'class_name': ['C1', np.nan, 'C1', 'C2'],
        'id': [1, 2, 3, 4]
    })
    # Expectation: keeps first C1 (idx 1), keeps NaN (idx 2), drops second C1 (idx 3), keeps C2 (idx 4)
    expected_ids = [1, 2, 4]
    result = rule.apply(df, {}, {})
    assert sorted(result['id'].tolist()) == sorted(expected_ids)

def test_rule0_empty_df():
    rule = Rule0DropDuplicates()
    df = create_df({'commit_hash': [], 'file': [], 'class_name': [], 'id': []})
    result = rule.apply(df, {}, {})
    assert result.empty
    assert list(result.columns) == list(df.columns)

def test_rule0_missing_columns(caplog):
    rule = Rule0DropDuplicates()
    df = create_df({'commit_hash': ['h1'], 'id': [1]}) # Missing file, class_name
    result = rule.apply(df, {}, {})
    assert len(result) == 1 # No duplicates based on available columns
    pd.testing.assert_frame_equal(result.reset_index(drop=True), df.reset_index(drop=True))
    # assert "Rule 0 skipped" in caplog.text # Check log if needed

# Rule 2: Remove Recent Clean Last Change
def test_rule2_last_is_buggy():
    rule = Rule2RemoveRecentCleanLastChange()
    df = create_df({
        'class_name': ['C1', 'C1'],
        'author_date_unix_timestamp': [1000, 2000],
        'is_buggy': [False, True], # Last change is buggy
        'id': [1, 2]
    })
    result = rule.apply(df, {}, {})
    # Use default gap (2419200s ~28 days)
    # The last commit IS the batch max, so diff is 0, which is < gap. It SHOULD be dropped.
    result = rule.apply(df, {'gap_seconds': 2419200}, {})
    assert len(result) == 1 # Expecting the last clean row to be dropped
    assert result['id'].tolist() == [2]

def test_rule2_last_clean_but_old():
    rule = Rule2RemoveRecentCleanLastChange()
    df = create_df({
        'class_name': ['C1', 'C1', 'C1'],
        'author_date_unix_timestamp': [1000, 2000, 1700000000], # Last change is old
        'is_buggy': [False, False,False],
        'id': [1, 2, 3]
    })
    # Use default gap (2419200s ~28 days), assume current time is > 1700000000 + gap
    result = rule.apply(df, {'gap_seconds': 2419200}, {})
    assert len(result) == 2

def test_rule2_last_clean_and_recent():
    rule = Rule2RemoveRecentCleanLastChange()
    now = int(np.datetime64('now', 's').astype(int))
    df = create_df({
        'class_name': ['C1', 'C1'],
        'author_date_unix_timestamp': [now - 5000000, now - 1000], # Last change is recent
        'is_buggy': [False, False],
        'id': [1, 2]
    })
    result = rule.apply(df, {'gap_seconds': 2419200}, {}) # Use default gap
    assert len(result) == 1
    assert result['id'].tolist() == [1] # Keeps first row, drops recent clean one

def test_rule2_multiple_classes():
    rule = Rule2RemoveRecentCleanLastChange()
    now = int(np.datetime64('now', 's').astype(int))
    df = create_df({
        'class_name': ['C1', 'C1', 'C2', 'C2'],
        'author_date_unix_timestamp': [now - 5000, now - 1000, now - 6000, now - 2000],
        'is_buggy': [False, False, False, True], # C1 last is clean/recent, C2 last is buggy
        'id': [1, 2, 3, 4]
    })
    result = rule.apply(df, {'gap_seconds': 3000}, {})
    assert len(result) == 3
    assert sorted(result['id'].tolist()) == [1, 3, 4] # Drops row 2

def test_rule2_empty_df():
    rule = Rule2RemoveRecentCleanLastChange()
    df = create_df({'class_name': [], 'author_date_unix_timestamp': [], 'is_buggy': [], 'id': []})
    result = rule.apply(df, {}, {})
    assert result.empty

def test_rule2_missing_columns(caplog):
    rule = Rule2RemoveRecentCleanLastChange()
    df = create_df({'class_name': ['C1'], 'id': [1]})
    result = rule.apply(df, {}, {})
    assert len(result) == 1
    # assert "Rule 2 skipped" in caplog.text

# Rule 3: Remove Empty Class
def test_rule3_not_empty():
    rule = Rule3RemoveEmptyClass()
    df = create_df({'totalMethodsQty': [1, 0], 'totalFieldsQty': [0, 1], 'id': [1, 2]})
    result = rule.apply(df, {}, {})
    assert len(result) == 2

def test_rule3_is_empty():
    rule = Rule3RemoveEmptyClass()
    df = create_df({'totalMethodsQty': [1, 0, 0], 'totalFieldsQty': [1, 0, np.nan], 'id': [1, 2, 3]})
    result = rule.apply(df, {}, {})
    assert len(result) == 1
    assert result['id'].tolist() == [1]

def test_rule3_missing_columns(caplog):
    rule = Rule3RemoveEmptyClass()
    df = create_df({'totalMethodsQty': [1], 'id': [1]})
    result = rule.apply(df, {}, {})
    assert len(result) == 1
    # assert "Rule 3 skipped" in caplog.text

# Rule 4: Remove Trivial Get/Set
def test_rule4_is_trivial():
    rule = Rule4RemoveTrivialGetSet()
    df = create_df({'totalMethodsQty': [1, 1, 0], 'wmc': [1, 0.5, 5], 'rfc': [0, 1, 5], 'id': [1, 2, 3]})
    result = rule.apply(df, {}, {})
    assert len(result) == 1
    assert result['id'].tolist() == [3] # Row 1 (1,1) and Row 2 (0.5,1) removed

def test_rule4_not_trivial():
    rule = Rule4RemoveTrivialGetSet()
    df = create_df({'totalMethodsQty': [1, 1], 'wmc': [2, 1], 'rfc': [1, 2], 'id': [1, 2]})
    result = rule.apply(df, {}, {})
    assert len(result) == 2

def test_rule4_nan_values():
    rule = Rule4RemoveTrivialGetSet()
    df = create_df({'totalMethodsQty': [1, 1], 'wmc': [1, np.nan], 'rfc': [np.nan, 1], 'id': [1, 2]})
    result = rule.apply(df, {}, {})
    assert len(result) == 0 # Both treated as trivial (wmc/rfc <= 1)

# Rule 5: Remove No Added Lines
def test_rule5_lines_added():
    rule = Rule5RemoveNoAddedLines()
    df = create_df({'la': [1, 10, 5], 'id': [1, 2, 3]})
    result = rule.apply(df, {}, {})
    assert len(result) == 3

def test_rule5_no_lines_added():
    rule = Rule5RemoveNoAddedLines()
    df = create_df({'la': [1, 0, -1, np.nan], 'id': [1, 2, 3, 4]})
    result = rule.apply(df, {}, {})
    assert len(result) == 1
    assert result['id'].tolist() == [1]

# Rule 6: Remove Comment Only Change
def test_rule6_comment_only():
    rule = Rule6RemoveCommentOnlyChange()
    df = create_df({'d_loc': [0, 0, 1], 'd_wmc': [0, 0, 0], 'la': [1, 0, 1], 'id': [1, 2, 3]})
    result = rule.apply(df, {}, {})
    assert len(result) == 1 # Only row where la > 0 kept (others dropped by Rule 6 logic)
    assert result['id'].tolist() == [3]

def test_rule6_code_changed():
    rule = Rule6RemoveCommentOnlyChange()
    df = create_df({'d_loc': [0, 1, 0], 'd_wmc': [0, 0, 2], 'id': [1, 2, 3]})
    result = rule.apply(df, {}, {})
    assert len(result) == 2
    assert sorted(result['id'].tolist()) == [2, 3]

def test_rule6_no_delta_cols(caplog):
    rule = Rule6RemoveCommentOnlyChange()
    df = create_df({'la': [1], 'id': [1]})
    result = rule.apply(df, {}, {})
    assert len(result) == 1
    # assert "Rule 6 skipped" in caplog.text

# Rule 7: Remove Trivial Method Change
def test_rule7_is_trivial():
    rule = Rule7RemoveTrivialMethodChange()
    params = {'min_line_change': 10}
    df = create_df({'la': [5, 10, 5], 'ld': [4, 0, 4], 'd_totalMethodsQty': [1, 1, 0], 'id': [1, 2, 3]})
    # Row 1: (5+4)=9 < 10 AND delta=1 -> remove
    # Row 2: (10+0)=10 >= 10 -> keep
    # Row 3: (5+4)=9 < 10 AND delta=0 -> keep
    result = rule.apply(df, params, {})
    assert len(result) == 2
    assert sorted(result['id'].tolist()) == [2, 3]

def test_rule7_custom_threshold():
    rule = Rule7RemoveTrivialMethodChange()
    params = {'min_line_change': 5}
    df = create_df({'la': [2, 5], 'ld': [2, 0], 'd_totalMethodsQty': [1, 1], 'id': [1, 2]})
    # Row 1: (2+2)=4 < 5 AND delta=1 -> remove
    # Row 2: (5+0)=5 >= 5 -> keep
    result = rule.apply(df, params, {})
    assert len(result) == 1
    assert result['id'].tolist() == [2]

# Rule 8: Remove Type/Exception Files
def test_rule8_remove_type():
    rule = Rule8RemoveTypeExceptionFiles()
    df = create_df({'file': ['MyType.java', 'SomeClass.java', 'mytype.java'], 'id': [1, 2, 3]})
    result = rule.apply(df, {}, {})
    assert len(result) == 2
    assert sorted(result['id'].tolist()) == [2, 3] # MyType.java removed, mytype.java kept

def test_rule8_remove_exception():
    rule = Rule8RemoveTypeExceptionFiles()
    df = create_df({'file': ['MyException.java', 'MyEx.java', 'ExceptionBase.java'], 'id': [1, 2, 3]})
    result = rule.apply(df, {}, {})
    assert len(result) == 2
    assert sorted(result['id'].tolist()) == [2, 3] # MyException.java removed

def test_rule8_no_match():
    rule = Rule8RemoveTypeExceptionFiles()
    df = create_df({'file': ['Main.java', 'Utils.kt'], 'id': [1, 2]})
    result = rule.apply(df, {}, {})
    assert len(result) == 2

def test_rule8_invalid_filename():
    rule = Rule8RemoveTypeExceptionFiles()
    df = create_df({'file': ['noextension', np.nan, 123], 'id': [1, 2, 3]})
    result = rule.apply(df, {}, {})
    assert len(result) == 3 # Should keep rows with invalid names

# Rule 9: Remove Dead Code
def test_rule9_is_dead():
    rule = Rule9RemoveDeadCode()
    df = create_df({'cbo': [0, 0, 1], 'fanin': [0, np.nan, 0], 'id': [1, 2, 3]})
    result = rule.apply(df, {}, {})
    assert len(result) == 1
    assert result['id'].tolist() == [3]

def test_rule9_not_dead():
    rule = Rule9RemoveDeadCode()
    df = create_df({'cbo': [1, 0], 'fanin': [0, 1], 'id': [1, 2]})
    result = rule.apply(df, {}, {})
    assert len(result) == 2

# Rule 10: Remove Data Class
def test_rule10_is_data_class():
    rule = Rule10RemoveDataClass()
    df = create_df({'wmc': [1, 0, 1], 'rfc': [0.5, 1, 2], 'totalFieldsQty': [1, 5, 1], 'id': [1, 2, 3]})
    # Row 1: wmc=1, rfc=0.5, fields=1 -> remove
    # Row 2: wmc=0, rfc=1, fields=5 -> remove
    # Row 3: wmc=1, rfc=2, fields=1 -> keep (rfc > 1)
    result = rule.apply(df, {}, {})
    assert len(result) == 1
    assert result['id'].tolist() == [3]

def test_rule10_not_data_class():
    rule = Rule10RemoveDataClass()
    df = create_df({'wmc': [2, 1], 'rfc': [1, 0], 'totalFieldsQty': [1, 0], 'id': [1, 2]})
    # Row 1: wmc > 1 -> keep
    # Row 2: fields = 0 -> keep
    result = rule.apply(df, {}, {})
    assert len(result) == 2

# Rule 11: Remove No Code Change
def test_rule11_no_change():
    rule = Rule11RemoveNoCodeChange()
    df = create_df({'la': [0, 1, 0, np.nan], 'ld': [0, 0, 1, 0], 'id': [1, 2, 3, 4]})
    result = rule.apply(df, {}, {})
    assert len(result) == 2
    assert sorted(result['id'].tolist()) == [2, 3]

# Rule 12: Remove Marginal Change
def test_rule12_is_marginal_non_buggy():
    rule = Rule12RemoveMarginalChange()
    params = {'threshold': 15}
    df = create_df({'d_loc': [5, 10, 5], 'd_wmc': [5, 5, 11], 'is_buggy': [False, False, False], 'id': [1, 2, 3]})
    # Row 1: sum=10 <= 15, non-buggy -> remove
    # Row 2: sum=15 <= 15, non-buggy -> remove
    # Row 3: sum=16 > 15, non-buggy -> keep
    result = rule.apply(df, params, {})
    assert len(result) == 1
    assert result['id'].tolist() == [3]

def test_rule12_is_marginal_buggy():
    rule = Rule12RemoveMarginalChange()
    params = {'threshold': 15}
    df = create_df({'d_loc': [5], 'd_wmc': [5], 'is_buggy': [True], 'id': [1]})
    # Row 1: sum=10 <= 15, buggy -> keep
    result = rule.apply(df, params, {})
    assert len(result) == 1

def test_rule12_not_marginal():
    rule = Rule12RemoveMarginalChange()
    params = {'threshold': 15}
    df = create_df({'d_loc': [10], 'd_wmc': [10], 'is_buggy': [False], 'id': [1]})
    # Row 1: sum=20 > 15, non-buggy -> keep
    result = rule.apply(df, params, {})
    assert len(result) == 1

# Rule 13: Remove Minimal Change
def test_rule13_is_minimal_non_buggy():
    rule = Rule13RemoveMinimalChange()
    params = {'threshold': 5}
    df = create_df({'d_loc': [1, 3, 5], 'd_wmc': [1, 1, 0], 'is_buggy': [False, False, False], 'id': [1, 2, 3]})
    # Row 1: sum=2 < 5, non-buggy -> remove
    # Row 2: sum=4 < 5, non-buggy -> remove
    # Row 3: sum=5 >= 5, non-buggy -> keep
    result = rule.apply(df, params, {})
    assert len(result) == 1
    assert result['id'].tolist() == [3]

def test_rule13_is_minimal_buggy():
    rule = Rule13RemoveMinimalChange()
    params = {'threshold': 5}
    df = create_df({'d_loc': [1], 'd_wmc': [1], 'is_buggy': [True], 'id': [1]})
    # Row 1: sum=2 < 5, buggy -> keep
    result = rule.apply(df, params, {})
    assert len(result) == 1

def test_rule13_not_minimal():
    rule = Rule13RemoveMinimalChange()
    params = {'threshold': 5}
    df = create_df({'d_loc': [3], 'd_wmc': [3], 'is_buggy': [False], 'id': [1]})
    # Row 1: sum=6 >= 5, non-buggy -> keep
    result = rule.apply(df, params, {})
    assert len(result) == 1

# Rule 14: Filter Large Commits
def test_rule14_large_commit_non_buggy():
    rule = Rule14FilterLargeCommits()
    params = {'max_files_changed': 10}
    df = create_df({'changed_file_count': [5, 11, 10], 'is_buggy': [False, False, False], 'id': [1, 2, 3]})
    result = rule.apply(df, params, {})
    assert len(result) == 2
    assert sorted(result['id'].tolist()) == [1, 3] # Row 2 removed

def test_rule14_large_commit_buggy():
    rule = Rule14FilterLargeCommits()
    params = {'max_files_changed': 10}
    df = create_df({'changed_file_count': [15], 'is_buggy': [True], 'id': [1]})
    result = rule.apply(df, params, {})
    assert len(result) == 1 # Keep buggy even if large

def test_rule14_small_commit():
    rule = Rule14FilterLargeCommits()
    params = {'max_files_changed': 10}
    df = create_df({'changed_file_count': [9], 'is_buggy': [False], 'id': [1]})
    result = rule.apply(df, params, {})
    assert len(result) == 1

# Rule Cluster: Large Commits (Simplified tests mocking KMeans)

@patch('worker.dataset.services.cleaning_rules.KMeans')
def test_rule_cluster_no_large_commits(mock_kmeans):
    rule = RuleClusterLargeCommits()
    params = {'threshold': 10}
    df = create_df({'commit_hash': ['h1', 'h2'], 'changed_file_count': [5, 10], 'is_buggy': [False, False], 'id': [1, 2]})
    result = rule.apply(df, params, {})
    pd.testing.assert_frame_equal(result, df)
    mock_kmeans.assert_not_called()

@patch('worker.dataset.services.cleaning_rules.KMeans')
def test_rule_cluster_large_commit_below_avg(mock_kmeans):
    rule = RuleClusterLargeCommits()
    params = {'threshold': 5}
    # avg_count below threshold will be 1 (from row 1)
    df = create_df({
        'commit_hash': ['h_small', 'h_large'],
        'changed_file_count': [1, 6], # Large commit has 1 row, avg_count=1
        'is_buggy': [False, False],
        'x1': [10, 20], # Example feature
        'id': [1, 2]
    })
    result = rule.apply(df, params, {'feature_columns': ['x1'], 'target_column': 'is_buggy'})
    assert len(result) == 2 # Should keep both rows as large commit group size (1) <= avg_count (1)
    mock_kmeans.assert_not_called()

@patch('worker.dataset.services.cleaning_rules.KMeans')
def test_rule_cluster_performs_clustering_and_agg(mock_kmeans_cls):
    # Not so sure about this test, but it seems to be testing the clustering and aggregation logic...
    rule = RuleClusterLargeCommits()
    params = {'threshold': 7}
    # Mock KMeans instance and fit_predict
    mock_kmeans_instance = MagicMock()
    mock_kmeans_instance.fit_predict.return_value = np.array([0, 1, 0])
    mock_kmeans_cls.return_value = mock_kmeans_instance

    df = create_df({
        'commit_hash': ['h_small'] * 3 + ['h_large'] * 5,
        'changed_file_count': [8] * 3 + [10] * 5,
        'is_buggy': [False, True, False] + [True, False, True, False, True], # Target
        'x1': [10, 20, 30] + [100, 110, 120, 130, 140], # Numeric feature
        'info': ['a', 'b', 'c'] + ['d', 'e', 'f', 'g', 'h'], # Info column
        'id': [1, 2, 3, 4, 5, 6, 7, 8]
    })
    # Need to provide a config for feature columns
    config = {'feature_columns': ['x1', 'changed_file_count'], 'target_column': 'is_buggy'}

    result = rule.apply(df, params, config)

    assert len(result) == 7
    assert mock_kmeans_cls.call_count == 2
    assert mock_kmeans_instance.fit_predict.call_count == 2

    # Check aggregated values for h_large (rows 4 and 6 went to cluster 0, row 5 to cluster 1)
    h_large_rows = result[result['commit_hash'] == 'h_large'].reset_index(drop=True)
    # Cluster 0: rows 4, 6 -> buggy=mean(1,1)=1>=0.5 -> True, x1=mean(100,120)=110, info='d' (first)
    # Cluster 1: row 5 -> buggy=mean(0)=0<0.5 -> False, x1=mean(110)=110, info='e' (first)
    cluster0 = h_large_rows[h_large_rows['info'] == 'd'] # Identify cluster 0 row
    cluster1 = h_large_rows[h_large_rows['info'] == 'e'] # Identify cluster 1 row

    assert bool(cluster0['is_buggy'].iloc[0]) is True
    assert int(cluster0['x1'].iloc[0]) == 100
    assert bool(cluster1['is_buggy'].iloc[0]) is False
    assert int(cluster1['x1'].iloc[0]) == 110


@patch('worker.dataset.services.cleaning_rules.KMeans')
def test_rule_cluster_handles_clustering_error(mock_kmeans_cls, caplog):
    rule = RuleClusterLargeCommits()
    params = {'threshold': 5}
    mock_kmeans_cls.return_value.fit_predict.side_effect = ValueError("KMeans failed")

    df = create_df({
        'commit_hash': ['h_small', 'h_large', 'h_large'],
        'changed_file_count': [3, 10, 10],
        'is_buggy': [False, True, False],
        'x1': [10, 100, 110],
        'id': [1, 2, 3]
    })
    config = {'feature_columns': ['x1'], 'target_column': 'is_buggy'}
    result = rule.apply(df, params, config)

    # Should keep all original rows because clustering failed for h_large
    assert len(result) == 3
    pd.testing.assert_frame_equal(result.sort_values('id').reset_index(drop=True),
                                 df.sort_values('id').reset_index(drop=True))
    # assert "Clustering failed for commit h_large" in caplog.text

@patch('worker.dataset.services.cleaning_rules.KMeans')
def test_rule_cluster_handles_agg_error(mock_kmeans_cls, caplog):
    rule = RuleClusterLargeCommits()
    params = {'threshold': 5}
    mock_kmeans_instance = MagicMock()
    mock_kmeans_instance.fit_predict.return_value = np.array([0, 1]) # 2 clusters
    mock_kmeans_cls.return_value = mock_kmeans_instance

    df = create_df({
        'commit_hash': ['h_small', 'h_large', 'h_large'],
        'changed_file_count': [3, 10, 10],
        'is_buggy': [False, True, False],
        'x1': [10, 100, 110],
        'id': [1, 2, 3]
    })
    config = {'feature_columns': ['x1'], 'target_column': 'is_buggy'}

    # Mock pandas aggregation to fail
    with patch('pandas.core.groupby.generic.DataFrameGroupBy.agg', side_effect=TypeError("Agg failed")):
        result = rule.apply(df, params, config)

    # Should keep all original rows because aggregation failed for h_large
    assert len(result) == 3
    pd.testing.assert_frame_equal(result.sort_values('id').reset_index(drop=True),
                                 df.sort_values('id').reset_index(drop=True))
    # assert "Aggregation failed for commit h_large" in caplog.text