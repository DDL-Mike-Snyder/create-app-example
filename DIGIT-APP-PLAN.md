# Handwritten Digit Recognizer on Domino — reference guide

End-to-end demo: a user uploads a JPG/PNG of a handwritten digit to a Streamlit app,
which predicts the digit and confidence using a scikit-learn classifier registered in
the Domino Model Registry. The app displays the uploaded image, the predicted digit,
and the confidence.

## Current status

| Piece | Status |
|---|---|
| Training + registration (`train.py`, run as a Job) | **Done.** Model registered as `mnist-digit-classifier`, alias `champion` points to the latest version (~95% test accuracy). |
| Model API (`model.py`) | **Written and correct, but not deployed.** This Domino deployment's Model API build service (buildkit) is currently stuck ("Leasing buildkit worker" never completes) — confirmed platform-level, reproduced on two separate build attempts, unrelated to this project's code. Needs whoever administers this Domino deployment to look at the build service. |
| App (`app.py`) | **Working**, using a temporary architecture change: it loads the registered model **in-process** via `mlflow.sklearn.load_model(...)` instead of calling a Model API over HTTP, since Apps launch from an already-built environment image and don't need buildkit. Not yet published. |

**To switch back to a real Model API once buildkit is fixed:** publish `model.py`
(unchanged, already correct — see Stage 2), then revert `app.py` to call it over HTTP
instead of loading the model in-process (the original HTTP-calling version is in git
history prior to the in-process-inference commit).

---

## How it fits together

| File | Role |
|---|---|
| `train.py` | Trains the classifier on MNIST and registers it in the Domino Model Registry (MLflow). Run as a Domino Job. |
| `model.py` | Domino Model API function: `predict()` decodes an uploaded image and returns `{digit, confidence}`. Ready to publish once the build service is back; not currently deployed. |
| `app.py` | Streamlit app: upload UI, loads the registered model directly and predicts in-process, displays image/prediction/confidence. |
| `app.sh` | Launch command Domino runs for the App — starts Streamlit on `0.0.0.0:8888`. |
| `requirements_app.txt` | Packages the App needs: `streamlit`, `pillow`, `mlflow`, `scikit-learn`, `numpy`. |

The shared piece of state linking training to serving is the registered model
name/alias: `models:/mnist-digit-classifier@champion`.

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
  `MlflowClient.set_registered_model_alias` — this is what both `model.py` and `app.py`
  load (`models:/mnist-digit-classifier@champion`). Re-running `train.py` registers a
  new version and moves the alias forward automatically.

**Run it:** as a Domino Job (`domino.job_start(command="train.py", ...)` via the
`dominodatalab` SDK, or the UI) rather than only interactively in a Workspace, so the
run is tied to a `DOMINO_RUN_ID`. Pin `environment_id`/`hardware_tier_id` explicitly to
a known-good combo (this project uses the default "Domino Standard Environment" on
`small-k8s`) — leaving them unset falls back to whatever this project's execution
defaults happen to be, which may point at a different, unverified environment/tier.

**Verified:** ran end-to-end as Job #11 — cached-dataset load confirmed (no re-fetch on
second run), test accuracy 95.13%, registered version 3, aliased `champion`.

---

## Stage 2 — Publish the Model API (blocked on platform build service)

1. In the Domino UI: **Publish → Model APIs → New Model API**.
2. Point it at `model.py`, function `predict`.
3. Make sure the Model API's environment includes `scikit-learn`, `mlflow`, `numpy`,
   `pillow`.
4. Publish, wait for status **Running**, then copy the endpoint URL and the
   auto-generated access token from the Model API page.

**Important — `init()` is not a real lifecycle hook.** Domino's classic Model API
harness only calls the configured function (`predict`) per request; it does **not**
call any separate startup/init function. `model.py` loads the model lazily on first
`predict()` call and caches it in a module-level global — do not rely on a separate
`init()` being called automatically (an earlier version of this file did, and every
request failed with `'NoneType' object has no attribute 'predict'` until fixed).

**Request/response contract (confirmed from a live test before the build outage):**
```
POST {url}                                    # e.g. https://<domino-host>/models/{model_id}/latest/model
auth: (access_token, access_token)            # HTTP basic auth, token as both user and password
Content-Type: application/json

{"data": {"image_base64": "<base64-encoded JPG/PNG bytes>"}}
```
Response is the `predict()` return value directly at the top level — **not** wrapped
in a `{"result": ...}` envelope: `{"digit": 7, "confidence": 0.94}`.

**Known platform issue:** publishing a new Model API version (`model_version_publish`)
got stuck at "Leasing buildkit worker" in the build logs on two separate attempts
(versions 2 and 3), even after canceling and retrying. This is a build-service-level
problem in this Domino deployment, not specific to this project's code — flag it to
whoever administers this Domino instance if it recurs.

**Verify before wiring the app** (once the build service is healthy):
- Use the Model API's built-in **Test** tab with a hand-crafted `image_base64` payload.
- Script it: base64-encode a real image file and POST it with `requests`, checking both
  a valid image and a bad/non-image payload.

---

## Stage 3 — The App (currently in-process, no Model API dependency)

`app.py` loads the registered model directly (`mlflow.sklearn.load_model`, cached via
`st.cache_resource`) and runs the same grayscale → invert → resize(28x28) → normalize
→ `predict`/`predict_proba` pipeline that `model.py` would run in a Model API. This
avoids the buildkit outage entirely, since Apps launch from an already-built
environment image and only run `pip install` + `streamlit run` at startup — no new
container build required.

`app.sh`:
```bash
streamlit run app.py \
    --server.port 8888 --server.address 0.0.0.0 --server.headless true \
    --server.enableCORS false --server.enableXsrfProtection false \
    --browser.gatherUsageStats false
```
`enableCORS`/`enableXsrfProtection` are disabled specifically to avoid WebSocket errors
behind Domino's reverse proxy. Streamlit needs **no** `DOMINO_RUN_HOST_PATH`/base-path
handling — Domino's proxy strips the prefix before forwarding.

**Verified locally:** boots cleanly (HTTP 200), and the full image→prediction pipeline
was validated against the live registered model on real (simulated-photo) inputs:
4/5 correct with confidences 0.65–1.0 on a random sample (the one miss, 8 predicted as
9, is a plausible model confusion, not a pipeline bug).

**To publish:**
1. Publish via **Publish → App** (title, hardware tier, permissions, Publish).
2. Smoke-test the published URL: page loads without a stuck "Please wait..." (would
   indicate a WebSocket failure), upload a fresh image, confirm end-to-end result, check
   **View Logs** on any failure.
3. `st.session_state` and `st.cache_resource` are process-wide/per-session, not
   cross-request-mutable — re-test with two tabs uploading different images
   concurrently to confirm no cross-user state bleed.

---

## Known limitations / follow-ups

- The preprocessing (grayscale → invert → resize to 28x28) assumes a roughly centered,
  single digit on a plain background. If real-world accuracy is disappointing on
  off-center or oddly-cropped photos, the next improvement is MNIST-style centering:
  threshold the image, crop to the digit's bounding box, and re-center it in the 28x28
  canvas before flattening.
- `TRAIN_SAMPLE_SIZE` in `train.py` trades training speed for accuracy — raise it (up
  to the full ~70k rows) if a Job's runtime budget allows.
- Once the Model API build service is fixed, consider moving back to the Model
  API + HTTP call architecture (`model.py` is ready) to decouple inference scaling
  from the App's own process, and to get Domino's built-in Model API monitoring
  (Grafana dashboards, request logging) for free.
