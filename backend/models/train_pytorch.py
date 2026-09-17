"""
Training script for Lead Acetate H2S indicator paper classification using PyTorch.

Trains CNN on synthetic/real indicator strip images, tracks validation accuracy,
and saves optimal checkpoint to models/h2s_cnn_model.pth.
"""

import os
import sys
import argparse
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from sklearn.metrics import classification_report, confusion_matrix

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from models.h2s_model_pytorch import get_model


# Standard ImageNet normalization for consistent feature scaling
NORMALIZE = transforms.Normalize(
    mean=[0.485, 0.456, 0.406],
    std=[0.229, 0.224, 0.225],
)

# Custom ImageFolder with explicit class order matching Config.CLASS_NAMES
class OrderedImageFolder(datasets.ImageFolder):
    def find_classes(self, directory):
        classes = Config.CLASS_NAMES
        class_to_idx = {cls_name: i for i, cls_name in enumerate(classes)}
        return classes, class_to_idx


def get_data_loaders(train_dir, val_dir, img_size=(128, 128), batch_size=16):
    train_transforms = transforms.Compose([
        transforms.Resize(img_size),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(),
        transforms.RandomRotation(10),
        transforms.ColorJitter(brightness=0.1, contrast=0.1),
        transforms.ToTensor(),
        NORMALIZE,
    ])

    val_transforms = transforms.Compose([
        transforms.Resize(img_size),
        transforms.ToTensor(),
        NORMALIZE,
    ])

    train_dataset = OrderedImageFolder(train_dir, transform=train_transforms)
    val_dataset = OrderedImageFolder(val_dir, transform=val_transforms)

    print(f"Dataset classes mapping: {train_dataset.class_to_idx}")
    print(f"Training samples: {len(train_dataset)}, Validation samples: {len(val_dataset)}")

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    return train_loader, val_loader


def train_model(train_dir, val_dir, epochs=10, batch_size=16, out_path=None):
    if out_path is None:
        out_path = Config.MODEL_PATH.replace(".h5", ".pth")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device}")

    train_loader, val_loader = get_data_loaders(train_dir, val_dir, Config.IMG_SIZE, batch_size)

    model = get_model(num_classes=len(Config.CLASS_NAMES)).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="max", factor=0.5, patience=2)

    best_val_acc = 0.0

    print("-" * 60)
    print("Starting Model Training...")
    print("-" * 60)

    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * images.size(0)
            _, preds = torch.max(outputs, 1)
            correct += torch.sum(preds == labels.data).item()
            total += labels.size(0)

        epoch_loss = running_loss / total
        epoch_acc = correct / total

        # Validation Phase
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)

                val_loss += loss.item() * images.size(0)
                _, preds = torch.max(outputs, 1)
                val_correct += torch.sum(preds == labels.data).item()
                val_total += labels.size(0)

        epoch_val_loss = val_loss / val_total
        epoch_val_acc = val_correct / val_total

        scheduler.step(epoch_val_acc)

        print(
            f"Epoch [{epoch:02d}/{epochs:02d}] "
            f"Train Loss: {epoch_loss:.4f} | Train Acc: {epoch_acc*100:.2f}% | "
            f"Val Loss: {epoch_val_loss:.4f} | Val Acc: {epoch_val_acc*100:.2f}%"
        )

        if epoch_val_acc > best_val_acc:
            best_val_acc = epoch_val_acc
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "val_acc": best_val_acc,
                "class_names": Config.CLASS_NAMES,
            }, out_path)
            print(f"  --> Saved new best checkpoint to {out_path} (Val Acc: {best_val_acc*100:.2f}%)")

    print("-" * 60)
    print(f"Training Complete! Best Validation Accuracy: {best_val_acc*100:.2f}%")
    print("-" * 60)

    # Final Evaluation & Classification Report
    checkpoint = torch.load(out_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    all_preds = []
    all_targets = []
    with torch.no_grad():
        for images, labels in val_loader:
            images = images.to(device)
            outputs = model(images)
            _, preds = torch.max(outputs, 1)
            all_preds.extend(preds.cpu().numpy())
            all_targets.extend(labels.numpy())

    print("\nClassification Report:")
    print(classification_report(all_targets, all_preds, target_names=Config.CLASS_NAMES))
    print("Confusion Matrix:")
    print(confusion_matrix(all_targets, all_preds))
    print(f"\nTrained Model Ready at: {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_dir", default=os.path.join(Config.BASE_DIR, "dataset", "train"))
    parser.add_argument("--val_dir", default=os.path.join(Config.BASE_DIR, "dataset", "val"))
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--out", default=os.path.join(Config.BASE_DIR, "models", "h2s_cnn_model.pth"))
    args = parser.parse_args()

    train_model(args.train_dir, args.val_dir, args.epochs, args.batch_size, args.out)
