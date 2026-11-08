from pathlib import Path
from crack_detection.data.discovery import discover_datasets
from crack_detection.data.validation import assert_pairings

def test_facade_pairing():
    stats = assert_pairings(Path("data/facade-crack-dataset"), "facade-crack-dataset")
    assert stats["missing_pair"] == 0

def test_crackseg_counts():
    info = discover_datasets(Path("data"))
    cs = info.get("crack-seg")
    assert cs is not None
    assert cs.split_counts["train"].images == 3717
