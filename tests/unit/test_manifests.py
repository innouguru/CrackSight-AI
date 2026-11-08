from pathlib import Path
import tempfile
from crack_detection.data.manifests import ManifestRecord, build_manifest


def test_manifest_sorted():
    records = [
        ManifestRecord(dataset="t", split="s", image_path=Path("b.jpg"), annotation_path=Path("b_mask.png"), scene_id="s1", view_id="v", digest="d", duplicate_group_digest="g", canonical_representative=True, mask_conversion_rule="binary", notes=[]),
        ManifestRecord(dataset="t", split="s", image_path=Path("a.jpg"), annotation_path=Path("a_mask.png"), scene_id="s1", view_id="v", digest="d", duplicate_group_digest="g", canonical_representative=True, mask_conversion_rule="binary", notes=[]),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "m.json"
        build_manifest("t", "s", records, out)
        text = out.read_text()
        assert text.index("a.jpg") < text.index("b.jpg")
