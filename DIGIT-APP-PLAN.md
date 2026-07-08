# Handwritten Digit Recognizer on Domino — reference guide

End-to-end demo: a user uploads a JPG/PNG of a handwritten digit to a Streamlit app,
the app calls a Domino Model API running a scikit-learn classifier, and the app
displays the uploaded image, the predicted digit, and the confidence.

---

## How it fits together

| File | Role |
|---|---|
| `train.py` | Trains the classifier on MNIST and registers it in the Domino Model Registry (MLflow). Run as a Domino Job. |
| `model.py` | Domino Model API: `init()` loads the registered model, `predict()` decodes an uploaded image and returns `{digit, confidence}`. Published separately as a Model API. |
| `app.py` | Streamlit app: upload UI, calls the Model API over HTTP, displays image/prediction/confidence. Published as a Domino App. |
| `app.sh` | Launch command Domino runs for the App — starts Streamlit on `0.0.0.0:8888`. |
| `requirements_app.txt` | Packages the App needs (`streamlit`, `pillow`, `requests`). |

These are three independently deployed Domino artifacts (Job, Model API, App) that get
wired together via one shared piece of state: the registered model name/alias
(`mnist-digit-classifier@champion`), and two environment variables the App uses to call
the Model API (`MODEL_API_URL`, `MODEL_API_TOKEN`).

---

## Stage 1 — Train & register the model (Job)

`train.py`:
- Fetches MNIST (`sklearn.datasets.fetch_openml`) once and caches it as
  `mnist_784.npz` in this project's Domino Dataset
  (`$DOMINO_DATASETS_DIR/create-app-example/`) — subsequent runs load the cached copy
  instead of re-fetching.
- Trains an `MLPClassifier` on a 15k-row subsample (fast enough for a small hardware
  tier; bump `TRAIN_SAMPLE_SIZE` for a small accuracy gain at the cost of runtime).
- Logs the run via `mlflow.sklearn.autolog()` + `mlflow.log_metric("test_accuracy", ...)`
  and registers the model with `mlflow.sklearn.log_model(..., registered_model_name=
  "mnist-digit-classifier")`.
- Sets the new version's alias to `champion` via
  `MlflowClient.set_registered_model_alias` — this is what `model.py` loads
  (`models:/mnist-digit-classifier@champion`). Re-running `train.py` registers a new
  version and moves the alias forward automatically.

**Run it:** as a Domino Job — `python train.py` — rather than only interactively in a
Workspace, so the run is tied to a `DOMINO_RUN_ID`.

**Verify:** check the project's Experiments/Registry UI for the new run and model
version, then in a Workspace: `mlflow.sklearn.load_model("models:/mnist-digit-classifier@champion")`
and run `predict_proba` on a few held-out samples. Confirmed locally: test accuracy
≈95.1%, and a second run correctly loaded the cached `.npz` instead of re-fetching.

---

## Stage 2 — Publish the Model API

1. In the Domino UI: **Publish → Model APIs → New Model API**.
2. Point it at `model.py`, function `predict`.
3. Make sure the Model API's environment includes `scikit-learn`, `mlflow`, `numpy`,
   `pillow` (either baked into the compute environment or via the Model API's own
   requirements file).
4. Publish, wait for status **Running**, then copy the endpoint URL and the
   auto-generated access token from the Model API page — these become `MODEL_API_URL`
   / `MODEL_API_TOKEN` for the App in Stage 3.

**Request/response contract:**
```
POST {MODEL_API_URL}
Authorization: Bearer {MODEL_API_TOKEN}
Content-Type: application/json

{"data": {"image_base64": "<base64-encoded JPG/PNG bytes>"}}
```
Response: `{"result": {"digit": 7, "confidence": 0.94}, ...}`

**Verify before wiring the app:**
- Use the Model API's built-in **Test** tab with a hand-crafted `image_base64` payload.
- Or script it: base64-encode a real image file and POST it with `requests`, checking
  both a valid image and a bad/non-image payload.
- Locally confirmed: `model.py`'s `init()`/`predict()` correctly classify synthetic
  "photo-style" digits (inverted MNIST samples simulating dark ink on light paper) with
  8/8 correct and confidences 0.84–1.00.

---

## Stage 3 — Publish the App

`app.py` is a small Streamlit app: `st.file_uploader` → `st.image` to display the
upload → POST to the Model API → `st.metric`/`st.progress` for the digit and
confidence. Errors from the Model API show a plain "Couldn't reach the prediction
service — try again" message rather than a raw traceback.

`app.sh` starts Streamlit directly (no separate pip step needed beyond what's already
there):
```bash
streamlit run app.py \
    --server.port 8888 --server.address 0.0.0.0 --server.headless true \
    --server.enableCORS false --server.enableXsrfProtection false \
    --browser.gatherUsageStats false
```
`enableCORS`/`enableXsrfProtection` are disabled specifically to avoid WebSocket errors
behind Domino's reverse proxy. Unlike the previous Dash version of this app, Streamlit
needs **no** `DOMINO_RUN_HOST_PATH`/base-path handling — Domino's proxy strips the
prefix before forwarding, and Streamlit works fine at root path.

1. In **Project Settings → Environment Variables** (or the App's own environment
   variable settings), set `MODEL_API_URL` and `MODEL_API_TOKEN` from Stage 2.
2. Confirm locally / in a Workspace first: `bash app.sh`, open the preview, upload a
   real handwritten-digit photo, confirm image + prediction + confidence render.
   Confirmed locally: the app boots cleanly and serves HTTP 200.
3. Publish via **Publish → App** (title, hardware tier, permissions, Publish).
4. Smoke-test the published URL: page loads without a stuck "Please wait..." (would
   indicate a WebSocket failure), upload a fresh image, confirm end-to-end result, check
   **View Logs** on any failure.
5. `st.session_state` is per-browser-session — re-test with two tabs uploading
   different images concurrently to confirm no cross-user state bleed.

---

## Known limitations / follow-ups

- The Model API's preprocessing (grayscale → invert → resize to 28x28) assumes a
  roughly centered, single digit on a plain background. If real-world accuracy is
  disappointing on off-center or oddly-cropped photos, the next improvement is
  MNIST-style centering: threshold the image, crop to the digit's bounding box, and
  re-center it in the 28x28 canvas before flattening.
- `TRAIN_SAMPLE_SIZE` in `train.py` trades training speed for accuracy — raise it (up
  to the full ~70k rows) if a Job's runtime budget allows.
