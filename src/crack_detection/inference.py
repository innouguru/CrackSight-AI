"""Reusable inference pipeline for the trained ResNet-34 U-Net crack segmentation model.

This module reconstructs the exact trained architecture and preprocessing used in
the M3 baseline (see ``configs/experiment_config.yaml`` and ``docs/m3_baseline_architecture.md``)
and exposes a small, callable API that returns:

* the original image (original dimensions, RGB),
* a probability map (sigmoid of the model logits, resized back to original dimensions),
* a binary crack mask (probability > explicit threshold), and
* a visual overlay of the mask on the original image.

Design notes
------------
* Input preprocessing matches ``crack_detection.dataset_loader.SegmentationDataset``:
  PIL ``Image.open(...).convert("RGB")``, resize to ``image_size`` (256x256) with
  bilinear resampling, scale pixels to ``[0, 1]`` (divide by 255), then
  ``HWC -> CHW`` and add a batch dimension. No ImageNet-style normalization is
  applied because training did not use it.
* The model emits a single-channel logit map resized to the model-input size.
  Probabilities are obtained with ``torch.sigmoid`` (same as the validation loop
  in ``crack_detection.train_loop``) and resized back to the *original* image
  dimensions so the returned mask/overlay align with the caller's photograph.
* The default decision threshold is ``0.5``, matching the recorded baseline
  evaluation (``final_test_report.json``: ``prediction_threshold = 0.5``) and
  the validation loop (``torch.sigmoid(logits) > 0.5``).
* Checkpoint format: a dict containing ``model_state_dict`` plus metadata
  (epoch, best_metric, seed, config, timestamp). Only ``model_state_dict`` is
  required for inference; the rest is surfaced for diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
import torch
from PIL import Image

from crack_detection.model import UNetResNet34, build_model


@dataclass(frozen=True)
class InferenceConfig:
    """Configuration for the crack segmentation inference pipeline."""

    #: Path to the trained checkpoint (``best_model.pth``).
    checkpoint_path: Path
    #: Model-input spatial size ``(height, width)`` used during training.
    image_size: Tuple[int, int] = (256, 256)
    #: Decision threshold applied to the sigmoid probability map.
    threshold: float = 0.5
    #: Device selection: "auto", "cpu", or "cuda".
    device: str = "auto"
    #: Whether to initialise the encoder with ImageNet weights before loading
    #: the checkpoint (checkpoint weights overwrite these regardless). Use
    #: ``False`` to avoid an ImageNet download when a full checkpoint is loaded.
    pretrained: bool = True

    def __post_init__(self) -> None:
        if self.device not in ("auto", "cpu", "cuda"):
            raise ValueError(
                f"Invalid device hint '{self.device}'. Expected 'auto', 'cpu', or 'cuda'."
            )
        if not (0.0 < self.threshold < 1.0):
            raise ValueError(f"threshold must be in (0, 1), got {self.threshold}.")
        h, w = self.image_size
        if h <= 0 or w <= 0:
            raise ValueError(f"image_size must be positive, got {self.image_size}.")


@dataclass(frozen=True)
class InferenceResult:
    """Output of a single-image inference call, all at original image dimensions."""

    #: Original image as a PIL RGB image at its native dimensions.
    original_image: Image.Image
    #: Sigmoid probability map, float32 in ``[0, 1]``, shape ``(H, W)`` at
    #: the original image dimensions.
    probability_map: np.ndarray
    #: Binary crack mask ``{0, 1}``, uint8, shape ``(H, W)`` at the original
    #: image dimensions.
    binary_mask: np.ndarray
    #: Visual overlay (red highlight on cracks) as a PIL RGB image at the
    #: original image dimensions.
    overlay: Image.Image


class CrackSegmentationPipeline:
    """Loads the trained checkpoint and runs inference on single images.

    The model is constructed once in ``__init__`` and kept in evaluation mode.
    Gradients are disabled for every forward pass.
    """

    def __init__(self, config: InferenceConfig) -> None:
        self.config = config
        self._device = self._resolve_device(config.device)
        self.checkpoint_meta: dict = {}
        self.model = self._load_model(config)
        self.model.eval()

    # ------------------------------------------------------------------ setup
    @staticmethod
    def _resolve_device(device_hint: str) -> torch.device:
        """Select a torch device, falling back to CPU when the hint is unsafe."""
        if device_hint == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if device_hint == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError(
                    "Requested device 'cuda' but CUDA is not available. "
                    "Use device='cpu' or device='auto'."
                )
            return torch.device("cuda")
        if device_hint == "cpu":
            return torch.device("cpu")
        raise ValueError(
            f"Invalid device hint '{device_hint}'. Expected 'auto', 'cpu', or 'cuda'."
        )

    def _load_model(self, config: InferenceConfig) -> UNetResNet34:
        """Build the architecture, load the checkpoint weights, and move to device."""
        checkpoint_path = Path(config.checkpoint_path)
        if not checkpoint_path.exists():
            raise FileNotFoundError(
                f"Checkpoint not found: {checkpoint_path.resolve()}"
            )

        # Reconstruct the exact trained architecture.
        model, _ = build_model(pretrained=config.pretrained, device_hint="cpu")

        # Load the checkpoint safely on CPU first, then move to the target device.
        try:
            checkpoint = torch.load(checkpoint_path, map_location="cpu")
        except Exception as exc:  # corrupted / truncated file
            raise RuntimeError(
                f"Failed to load checkpoint '{checkpoint_path}': {exc}"
            ) from exc

        if not isinstance(checkpoint, dict) or "model_state_dict" not in checkpoint:
            raise ValueError(
                f"Checkpoint '{checkpoint_path}' does not contain a "
                f"'model_state_dict' key. Found keys: "
                f"{list(checkpoint.keys()) if isinstance(checkpoint, dict) else type(checkpoint).__name__}"
            )

        # Surface metadata (epoch, best_metric, seed, config, timestamp) when present.
        self.checkpoint_meta = {
            key: checkpoint[key]
            for key in ("epoch", "best_metric", "seed", "config", "timestamp")
            if key in checkpoint
        }

        try:
            model.load_state_dict(checkpoint["model_state_dict"], strict=True)
        except RuntimeError as exc:
            raise RuntimeError(
                f"Checkpoint '{checkpoint_path}' is incompatible with the "
                f"UNetResNet34 architecture (shape/key mismatch): {exc}"
            ) from exc

        return model.to(self._device)

    # ------------------------------------------------------------------ preprocessing
    @staticmethod
    def _load_image(image_input: Union[str, Path, Image.Image]) -> Image.Image:
        """Open an image path or accept a PIL image, returning an RGB image.

        Raises a clear ``FileNotFoundError`` / ``ValueError`` for invalid input.
        """
        if isinstance(image_input, Image.Image):
            return image_input.convert("RGB")
        path = Path(image_input)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path.resolve()}")
        try:
            return Image.open(path).convert("RGB")
        except Exception as exc:  # unreadable / not an image
            raise ValueError(
                f"Invalid image file '{path}': could not decode as an image ({exc})"
            ) from exc

    def _preprocess(self, image: Image.Image) -> Tuple[torch.Tensor, Tuple[int, int]]:
        """Resize to model input, scale to [0,1], and return a batched CHW tensor.

        Returns the tensor and the original ``(width, height)`` for later
        resizing of outputs back to native dimensions.
        """
        original_size = image.size  # (width, height)
        resized = image.resize(
            (self.config.image_size[1], self.config.image_size[0]),
            Image.Resampling.BILINEAR,
        )
        arr = np.array(resized).astype(np.float32) / 255.0  # HWC, [0,1]
        tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)  # 1, C, H, W
        return tensor.to(self._device), original_size

    # ------------------------------------------------------------------ postprocessing
    @staticmethod
    def _resize_probability_map(
        probs: np.ndarray, target_size: Tuple[int, int]
    ) -> np.ndarray:
        """Resize a ``(H, W)`` probability map back to ``target_size = (width, height)``."""
        if probs.shape[:2] == target_size[::-1]:
            return probs
        prob_img = Image.fromarray((probs * 255.0).astype(np.uint8))
        prob_img = prob_img.resize(target_size, Image.Resampling.BILINEAR)
        return np.array(prob_img).astype(np.float32) / 255.0

    @staticmethod
    def _make_overlay(
        original: Image.Image, binary_mask: np.ndarray, alpha: float = 0.45
    ) -> Image.Image:
        """Blend a red crack highlight onto the original RGB image."""
        arr = np.array(original).astype(np.float32)
        highlight = np.zeros_like(arr)
        highlight[..., 0] = 255.0  # red channel
        mask_f = (binary_mask > 0).astype(np.float32)[..., None]
        blended = arr * (1.0 - alpha * mask_f) + highlight * (alpha * mask_f)
        return Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8))

    # ------------------------------------------------------------------ public API
    @torch.no_grad()
    def predict(self, image_input: Union[str, Path, Image.Image]) -> InferenceResult:
        """Run inference on a single image.

        Parameters
        ----------
        image_input:
            A path to an image file (str/Path) or a PIL ``Image.Image``.

        Returns
        -------
        InferenceResult
            Original image, probability map, binary mask, and overlay -- all at
            the original image dimensions.
        """
        image = self._load_image(image_input)
        original_size = image.size  # (width, height)

        input_tensor, _ = self._preprocess(image)

        model = self.model
        model.eval()
        logits = model(input_tensor)
        # Ensure logits are at model-input spatial size (defensive; the architecture
        # already resizes internally, but guard against shape drift).
        if tuple(logits.shape[-2:]) != tuple(self.config.image_size):
            logits = torch.nn.functional.interpolate(
                logits, size=self.config.image_size, mode="bilinear", align_corners=False
            )

        probs = torch.sigmoid(logits)[0, 0].detach().cpu().numpy()  # (256, 256)
        probs_orig = self._resize_probability_map(probs, original_size)
        binary_mask = (probs_orig > self.config.threshold).astype(np.uint8)
        overlay = self._make_overlay(image, binary_mask)

        return InferenceResult(
            original_image=image,
            probability_map=probs_orig.astype(np.float32),
            binary_mask=binary_mask,
            overlay=overlay,
        )


def run_inference(
    image_input: Union[str, Path, Image.Image],
    checkpoint_path: Union[str, Path],
    *,
    threshold: float = 0.5,
    image_size: Tuple[int, int] = (256, 256),
    device: str = "auto",
    pretrained: bool = True,
) -> InferenceResult:
    """Convenience one-shot inference helper.

    Builds a pipeline from the given checkpoint and runs ``predict`` on the image.
    Useful for scripts and interactive exploration; reuse ``CrackSegmentationPipeline``
    directly when inferring many images to avoid reloading the checkpoint each time.
    """
    config = InferenceConfig(
        checkpoint_path=Path(checkpoint_path),
        image_size=image_size,
        threshold=threshold,
        device=device,
        pretrained=pretrained,
    )
    pipeline = CrackSegmentationPipeline(config)
    return pipeline.predict(image_input)
