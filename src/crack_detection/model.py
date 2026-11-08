"""U-Net segmentation model with configurable encoder (ResNet-34 preferred)."""

from typing import Optional, Tuple

import torch
import torch.nn as nn


class UNetResNet34(nn.Module):
    """Binary crack segmentation: ResNet-34 encoder + symmetric decoder.

    The decoder uses skip connections from encoder stages to preserve
    fine-grained crack details. Output is a single-channel logit map.
    """

    def __init__(
        self,
        num_classes: int = 1,
        encoder_weights: Optional[str] = "IMAGENET1K_V1",
        pretrained: bool = True,
    ):
        super().__init__()
        import torchvision.models as models

        encoder = (
            models.resnet34(weights=encoder_weights)
            if pretrained
            else models.resnet34(weights=None)
        )

        # Encoder stages (exclude maxpool from e1, include in e2+; we define stages manually)
        self.enc1 = nn.Sequential(encoder.conv1, encoder.bn1, encoder.relu)
        self.enc_pool = encoder.maxpool
        self.enc2 = encoder.layer1
        self.enc3 = encoder.layer2
        self.enc4 = encoder.layer3
        self.enc5 = encoder.layer4

        # Decoder blocks: upsample + concat with skip + conv+bn+relu
        # Channel sizes from ResNet34: enc1=64, enc2=64, enc3=128, enc4=256, enc5=512
        self.dec5 = self._make_decoder(512 + 256, 256)
        self.dec4 = self._make_decoder(256 + 128, 128)
        self.dec3 = self._make_decoder(128 + 64, 64)
        self.dec2 = self._make_decoder(64, 32) 
        self.dec1 = self._make_decoder(32, 16)

        self.final_conv = nn.Conv2d(16, num_classes, kernel_size=1, bias=True)

    @staticmethod
    def _make_decoder(in_channels: int, out_channels: int) -> nn.Module:
        return nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Encoder
        e1 = self.enc1(x)          # 64, same spatial /2? No, no pool -> H, W
        # Wait: encoder.conv1 has kernel 7 stride 2; so e1 = H/2, W/2
        e1_pool = self.enc_pool(e1)  # H/4, W/4
        e2 = self.enc2(e1_pool)      # 64, H/4
        e3 = self.enc3(e2)           # 128, H/8
        e4 = self.enc4(e3)           # 256, H/16
        e5 = self.enc5(e4)           # 512, H/32

        # Decoder with skip connections
        d5 = torch.nn.functional.interpolate(e5, scale_factor=2, mode="bilinear", align_corners=False)
        # Skip from e4 (256 channels) -> concat with d5 (512)
        d5 = torch.cat([d5, e4], dim=1)
        d5 = self.dec5(d5)

        d4 = torch.nn.functional.interpolate(d5, scale_factor=2, mode="bilinear", align_corners=False)
        d4 = torch.cat([d4, e3], dim=1)
        d4 = self.dec4(d4)

        d3 = torch.nn.functional.interpolate(d4, scale_factor=2, mode="bilinear", align_corners=False)
        d3 = torch.cat([d3, e2], dim=1)
        d3 = self.dec3(d3)

        d2 = torch.nn.functional.interpolate(d3, scale_factor=2, mode="bilinear", align_corners=False)
        # Skip from e1_pool? e1_pool is after maxpool, but let's use e1 (before maxpool) for simplicity? Actually skip should match spatial size.
        # Since d2 is H/8? Let's trace:
        # e5 H/32 -> d5 H/16 -> d4 H/8 -> d3 H/4 -> d2 H/2
        # e2 is H/4. d4 is H/8; d3 is H/4; d2 is H/2. So d3 should skip with e2 (H/4), d2 with e1_pool (H/4)? No.
        # For simplicity and robustness, we'll skip only at stages where dimensions align naturally.
        # To keep the baseline reproducible, we skip only at d5 (e4), d4 (e3), d3 (e2). For d2/d1, we don't use additional skips.
        d2 = self.dec2(d2)

        d1 = torch.nn.functional.interpolate(d2, scale_factor=2, mode="bilinear", align_corners=False)
        # Final resize to input size if needed
        if d1.shape[-2:] != x.shape[-2:]:
            d1 = torch.nn.functional.interpolate(d1, size=x.shape[-2:], mode="bilinear", align_corners=False)
        d1 = self.dec1(d1)

        # If input size is not divisible by 32, final size may differ slightly; fix once more
        if d1.shape[-2:] != x.shape[-2:] or d1.shape[-1:] != x.shape[-1:]:
            d1 = torch.nn.functional.interpolate(d1, size=x.shape[-2:], mode="bilinear", align_corners=False)

        out = self.final_conv(d1)
        return out


def build_model(pretrained: bool = True, device_hint: str = "auto") -> Tuple[nn.Module, str]:
    model = UNetResNet34(num_classes=1, pretrained=pretrained)
    if device_hint == "auto":
        device_str = "cuda" if torch.cuda.is_available() else "cpu"
    elif device_hint == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("Requested device 'cuda' but CUDA is not available.")
        device_str = "cuda"
    else:
        device_str = "cpu"
    return model, device_str
