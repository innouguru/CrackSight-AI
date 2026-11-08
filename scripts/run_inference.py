"""Minimal command-line inference script for the crack segmentation baseline.

Usage (from the project root, with the virtual environment activated):

    python scripts/run_inference.py

This loads the trained checkpoint, runs inference on one photograph, and writes
the probability map, binary mask, and overlay to ``outputs/``.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from crack_detection.inference import CrackSegmentationPipeline, InferenceConfig


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    ckpt = project_root / "model_artifacts" / "m3_crack_seg_baseline_b1_20261026_201725" / "best_model.pth"

    if not ckpt.exists():
        raise FileNotFoundError(f"Trained checkpoint not found: {ckpt}")

    # Photograph to inspect. Swap in any real building-wall image here.
    image_path = project_root / "docs" / "dataset-audit" / "evidence" / "comp_crackseg_1604.jpg"
    if not image_path.exists():
        raise FileNotFoundError(f"Input image not found: {image_path}")

    output_dir = project_root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    config = InferenceConfig(
        checkpoint_path=ckpt,
        image_size=(256, 256),
        threshold=0.5,  # matches train_loop.py and final_test_report.json
        device="cpu",
    )
    pipe = CrackSegmentationPipeline(config)

    result = pipe.predict(image_path)

    # Save outputs at original image dimensions.
    mask_img = Path(output_dir) / f"{image_path.stem}_pred_mask.png"
    overlay_img = Path(output_dir) / f"{image_path.stem}_overlay.png"
    Image.fromarray((result.probability_map * 255).astype("uint8")).save(
        Path(output_dir) / f"{image_path.stem}_probability.png"
    )
    Image.fromarray((result.binary_mask * 255).astype("uint8")).save(mask_img)
    result.overlay.save(overlay_img)

    print(f"Input:          {image_path}")
    print(f"Original size:  {result.original_image.size}")
    print(f"Probability map: {output_dir / f'{image_path.stem}_probability.png'}")
    print(f"Binary mask:    {mask_img}")
    print(f"Overlay:        {overlay_img}")
    print(f"Crack pixels:   {int(result.binary_mask.sum())} / {result.binary_mask.size}")
    print(f"Mean probability: {float(result.probability_map.mean()):.4f}")


if __name__ == "__main__":
    main()
