"""
CNN architecture for classifying the color-change stage of lead acetate
(Pb(CH3COO)2) H2S detection paper.

Lead acetate paper reacts with hydrogen sulfide gas to form black lead
sulfide (PbS):
    Pb(CH3COO)2 + H2S -> PbS (black) + 2 CH3COOH
The degree of darkening/discoloration correlates with H2S concentration x
exposure time, so a color/texture classifier on a photo of the paper strip
gives a proxy for exposure severity.
"""

from tensorflow.keras import layers, models


def build_cnn(input_shape=(128, 128, 3), num_classes=4):
    """A compact CNN suited to a small, domain-specific image dataset
    (color-patch classification, not general object recognition)."""

    model = models.Sequential(
        [
            layers.Input(shape=input_shape),
            # Rescale pixel values into [0, 1]
            layers.Rescaling(1.0 / 255),
            # Light augmentation helps a lot when the dataset is small
            layers.RandomFlip("horizontal"),
            layers.RandomRotation(0.05),
            layers.RandomBrightness(0.1),
            layers.RandomContrast(0.1),
            layers.Conv2D(16, 3, padding="same", activation="relu"),
            layers.BatchNormalization(),
            layers.MaxPooling2D(),
            layers.Conv2D(32, 3, padding="same", activation="relu"),
            layers.BatchNormalization(),
            layers.MaxPooling2D(),
            layers.Conv2D(64, 3, padding="same", activation="relu"),
            layers.BatchNormalization(),
            layers.MaxPooling2D(),
            layers.Conv2D(128, 3, padding="same", activation="relu"),
            layers.BatchNormalization(),
            layers.MaxPooling2D(),
            layers.GlobalAveragePooling2D(),
            layers.Dense(64, activation="relu"),
            layers.Dropout(0.3),
            layers.Dense(num_classes, activation="softmax"),
        ],
        name="h2s_lead_acetate_cnn",
    )

    model.compile(
        optimizer="adam",
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model
