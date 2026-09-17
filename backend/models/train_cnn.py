"""
Train the lead-acetate H2S exposure classifier.

Expected dataset layout (see ../dataset/):

    dataset/
      train/
        no_exposure/  *.jpg
        low/          *.jpg
        medium/       *.jpg
        high/         *.jpg
      val/
        no_exposure/
        low/
        medium/
        high/

Photograph tips for a usable dataset:
  - Fixed camera position, consistent lighting (avoid mixed daylight/LED),
    ideally a small enclosed light box so shadows/reflections don't confuse
    the model.
  - Include a fixed color-reference card in frame if possible, and crop
    tightly to the paper strip before saving (or let the model see a
    consistent fixed field of view every time).
  - Capture many samples per class: different paper batches, slightly
    different exposure durations, different times of day.
  - Label by class based on known/controlled H2S concentration exposures
    (e.g. calibration gas + known exposure time), not guesswork.

Run:
    python train_cnn.py --train_dir ../dataset/train --val_dir ../dataset/val
"""

import argparse
import os
import sys

import tensorflow as tf

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from models.cnn_model import build_cnn


def load_datasets(train_dir, val_dir, img_size, batch_size=16):
    train_ds = tf.keras.utils.image_dataset_from_directory(
        train_dir,
        image_size=img_size,
        batch_size=batch_size,
        label_mode="int",
        class_names=Config.CLASS_NAMES,
        shuffle=True,
        seed=42,
    )
    val_ds = tf.keras.utils.image_dataset_from_directory(
        val_dir,
        image_size=img_size,
        batch_size=batch_size,
        label_mode="int",
        class_names=Config.CLASS_NAMES,
        shuffle=False,
    )
    autotune = tf.data.AUTOTUNE
    train_ds = train_ds.cache().prefetch(autotune)
    val_ds = val_ds.cache().prefetch(autotune)
    return train_ds, val_ds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_dir", default="../dataset/train")
    parser.add_argument("--val_dir", default="../dataset/val")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--out", default=Config.MODEL_PATH)
    args = parser.parse_args()

    train_ds, val_ds = load_datasets(
        args.train_dir, args.val_dir, Config.IMG_SIZE, args.batch_size
    )

    model = build_cnn(
        input_shape=Config.IMG_SIZE + (3,), num_classes=len(Config.CLASS_NAMES)
    )
    model.summary()

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=6, restore_best_weights=True
        ),
        tf.keras.callbacks.ModelCheckpoint(
            args.out, monitor="val_accuracy", save_best_only=True
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=3
        ),
    ]

    model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.epochs,
        callbacks=callbacks,
    )

    model.save(args.out)
    print(f"Model saved to {args.out}")


if __name__ == "__main__":
    main()
