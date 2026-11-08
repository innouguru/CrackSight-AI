from pathlib import Path
from crack_detection.data.deduplication import compute_sha256, group_duplicates


def test_sha256_for_readme():
    digest = compute_sha256(Path("data/concrete400/README.md"))
    assert len(digest) == 64


def test_exact_duplicate_groups_exist():
    train_dir = Path("data/facade-crack-dataset/train")
    jpgs = list(train_dir.glob("*.jpg"))
    subset = jpgs[:20]
    groups = group_duplicates(subset)
    duplicates = [g for g in groups if len(g.files) > 1]
    for dup in duplicates:
        assert len(dup.files) >= 2
        assert dup.digest is not None
