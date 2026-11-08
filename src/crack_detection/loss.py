"""Loss functions for binary crack segmentation."""

import torch
import torch.nn as nn


class BinaryCrossEntropyDiceLoss(nn.Module):
    """Combined binary cross-entropy + Dice loss.

    The Dice term uses smooth=1.0 to stay stable with small crack regions.
    """

    def __init__(self, dice_weight: float = 0.5):
        super().__init__()
        self.dice_weight = dice_weight
        self.bce = nn.BCEWithLogitsLoss()

    def dice_loss(self, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        probs = torch.sigmoid(logits)
        intersection = torch.sum(probs * target, dim=[2, 3])
        union = torch.sum(probs, dim=[2, 3]) + torch.sum(target, dim=[2, 3])
        dice = (2.0 * intersection + 1.0) / (union + 1.0)
        return 1.0 - dice.mean()
        

    def forward(self, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        bce = self.bce(logits, target)
        dice = self.dice_loss(logits, target)
        return bce + self.dice_weight * dice
