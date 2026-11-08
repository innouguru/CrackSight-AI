from pathlib import Path
import json

def test_crackseg_duplicate_not_in_scored_set():
    excluded = Path("data/crack-seg/images/test/1979.rf.dea5db582b997afc4acb0f68d74c3b84.jpg")
    assert excluded.exists()
    manifest_path = Path("outputs/manifests/crackseg_duplicate_exclusion.json")
    data = json.loads(manifest_path.read_text())
    assert data["excluded_sample"].endswith("dea5db582b997afc4acb0f68d74c3b84.jpg")
    assert data["scored_test_count_after_exclusion"] == 111
