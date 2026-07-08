"""Streamlit app: upload a handwritten digit image, get a prediction + confidence.

Loads the registered MLflow model directly in-process rather than calling a separate
Model API. Domino's Model API build service (buildkit) is currently down in this
deployment, which blocks building any new Model API container; Apps don't need a
buildkit build (they launch from an already-built environment image), so this sidesteps
the outage. See DIGIT-APP-PLAN.md for how to switch back to a real Model API once the
platform issue is resolved -- model.py already has the equivalent predict() logic.
"""

import io

import mlflow
import numpy as np
import streamlit as st
from PIL import Image, ImageOps

MODEL_URI = "models:/mnist-digit-classifier@champion"


@st.cache_resource
def load_model():
    return mlflow.sklearn.load_model(MODEL_URI)


st.set_page_config(page_title="Digit Recognizer", page_icon="🔢")
st.title("Handwritten Digit Recognizer")
st.write("Upload a JPG or PNG of a handwritten digit to get a prediction.")

uploaded_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image_bytes = uploaded_file.getvalue()
    st.image(image_bytes, caption="Uploaded image", width=200)

    with st.spinner("Predicting..."):
        try:
            model = load_model()

            img = Image.open(io.BytesIO(image_bytes)).convert("L")  # grayscale
            img = ImageOps.invert(img)  # MNIST: light digit on dark bg; photos are usually the opposite
            img = img.resize((28, 28))

            pixels = np.array(img, dtype=np.float32).reshape(1, -1) / 255.0
            prediction = int(model.predict(pixels)[0])
            confidence = float(model.predict_proba(pixels)[0].max())

            st.metric("Predicted digit", prediction)
            st.progress(confidence)
            st.write(f"Confidence: {confidence:.1%}")
        except Exception:
            st.error("Couldn't generate a prediction — try again.")
