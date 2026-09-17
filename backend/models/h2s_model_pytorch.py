"""
PyTorch Convolutional Neural Network for Lead Acetate H2S Indicator Paper Classification.

Architecture:
- 4 Convolutional Blocks with Batch Normalization & LeakyReLU
- Spatial Pooling (MaxPool2d)
- Adaptive Average Pooling
- Fully Connected classification head with Dropout regularization
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class H2SLeadAcetateCNN(nn.Module):
    def __init__(self, num_classes=4):
        super(H2SLeadAcetateCNN, self).__init__()

        # Conv Block 1: 128x128 -> 64x64
        self.conv1 = nn.Conv2d(3, 16, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(16)

        # Conv Block 2: 64x64 -> 32x32
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(32)

        # Conv Block 3: 32x32 -> 16x16
        self.conv3 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm2d(64)

        # Conv Block 4: 16x16 -> 8x8
        self.conv4 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        self.bn4 = nn.BatchNorm2d(128)

        self.pool = nn.MaxPool2d(2, 2)
        self.global_pool = nn.AdaptiveAvgPool2d((1, 1))

        # Classification Head
        self.fc1 = nn.Linear(128, 64)
        self.dropout = nn.Dropout(0.3)
        self.fc2 = nn.Linear(64, num_classes)

    def forward(self, x):
        x = self.pool(F.leaky_relu(self.bn1(self.conv1(x)), 0.1))
        x = self.pool(F.leaky_relu(self.bn2(self.conv2(x)), 0.1))
        x = self.pool(F.leaky_relu(self.bn3(self.conv3(x)), 0.1))
        x = self.pool(F.leaky_relu(self.bn4(self.conv4(x)), 0.1))

        x = self.global_pool(x)
        x = torch.flatten(x, 1)

        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        logits = self.fc2(x)
        return logits


def get_model(num_classes=4):
    return H2SLeadAcetateCNN(num_classes=num_classes)
