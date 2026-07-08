"""Domino Model API entry point: image-of-a-digit -> predicted digit + confidence.

Publish this file via Domino's Publish -> Model APIs, with `predict` as the function
to expose. `init()` runs once when the API starts; `predict()` runs per request.
"""

import base64
import io

import mlflow
import numpy as np
from PIL import Image, ImageOps

MODEL_URI = "models:/mnist-digit-classifier@champion"

_model = None


def init():
    global _model
    _model = mlflow.sklearn.load_model(MODEL_URI)


def predict(image_base64):
    """image_base64: base64-encoded bytes of a JPG/PNG of a handwritten digit."""
    img_bytes = base64.b64decode(image_base64)
    img = Image.open(io.BytesIO(img_bytes)).convert("L")  # grayscale
    img = ImageOps.invert(img)  # MNIST: light digit on dark bg; photos are usually the opposite
    img = img.resize((28, 28))

    pixels = np.array(img, dtype=np.float32).reshape(1, -1) / 255.0
    prediction = _model.predict(pixels)[0]
    probabilities = _model.predict_proba(pixels)[0]

    return {"digit": int(prediction), "confidence": float(probabilities.max())}
