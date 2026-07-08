"""Streamlit app: upload a handwritten digit image, get a prediction + confidence.

Calls a Domino Model API (see model.py) for inference. Requires MODEL_API_URL and
MODEL_API_TOKEN to be set as project/app environment variables.
"""

import base64
import os

import requests
import streamlit as st

st.set_page_config(page_title="Digit Recognizer", page_icon="🔢")
st.title("Handwritten Digit Recognizer")
st.write("Upload a JPG or PNG of a handwritten digit to get a prediction.")

uploaded_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image_bytes = uploaded_file.getvalue()
    st.image(image_bytes, caption="Uploaded image", width=200)

    model_api_url = os.environ.get("MODEL_API_URL")
    model_api_token = os.environ.get("MODEL_API_TOKEN")

    if not model_api_url or not model_api_token:
        st.error("MODEL_API_URL and MODEL_API_TOKEN must be set as environment variables.")
    else:
        with st.spinner("Predicting..."):
            try:
                response = requests.post(
                    model_api_url,
                    json={"data": {"image_base64": base64.b64encode(image_bytes).decode("utf-8")}},
                    headers={"Authorization": f"Bearer {model_api_token}"},
                    timeout=30,
                )
                response.raise_for_status()
                result = response.json()["result"]

                st.metric("Predicted digit", result["digit"])
                st.progress(result["confidence"])
                st.write(f"Confidence: {result['confidence']:.1%}")
            except Exception:
                st.error("Couldn't reach the prediction service — try again.")
