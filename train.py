"""Train an MNIST handwritten-digit classifier and register it in Domino.

Run as a Domino Job:  python train.py
"""

import os

import mlflow
import numpy as np
from mlflow.models.signature import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.datasets import fetch_openml
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier

MODEL_NAME = "mnist-digit-classifier"
TRAIN_SAMPLE_SIZE = 15000  # subsample of the 70k-row dataset, keeps Job runtime short

DATASET_DIR = os.path.join(os.environ.get("DOMINO_DATASETS_DIR", "/mnt/data"), "create-app-example")
MNIST_PATH = os.path.join(DATASET_DIR, "mnist_784.npz")


def load_mnist():
    if os.path.exists(MNIST_PATH):
        print(f"Loading cached MNIST data from {MNIST_PATH}")
        cached = np.load(MNIST_PATH, allow_pickle=True)
        return cached["X"], cached["y"]

    print("No cached copy found — fetching MNIST from OpenML")
    X, y = fetch_openml("mnist_784", version=1, return_X_y=True, as_frame=False)

    os.makedirs(DATASET_DIR, exist_ok=True)
    tmp_path = MNIST_PATH + ".tmp.npz"  # np.savez_compressed always appends .npz to the name it's given
    np.savez_compressed(tmp_path, X=X, y=y)
    os.rename(tmp_path, MNIST_PATH)  # atomic, avoids partial-file reads from concurrent jobs
    print(f"Cached MNIST data to {MNIST_PATH}")
    return X, y


def main():
    X, y = load_mnist()
    y = y.astype(int)

    rng = np.random.RandomState(42)
    sample_idx = rng.choice(len(X), size=min(TRAIN_SAMPLE_SIZE, len(X)), replace=False)
    X, y = X[sample_idx], y[sample_idx]

    X = X / 255.0
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    username = os.environ.get("DOMINO_STARTING_USERNAME", "unknown")
    mlflow.set_experiment(f"mnist-digit-classifier-{username}")
    mlflow.sklearn.autolog(log_model_signatures=True, log_input_examples=True)

    with mlflow.start_run(run_name="mlp-mnist-v1"):
        model = MLPClassifier(
            hidden_layer_sizes=(100,),
            max_iter=30,
            early_stopping=True,
            random_state=42,
        )
        model.fit(X_train, y_train)

        test_accuracy = model.score(X_test, y_test)
        mlflow.log_metric("test_accuracy", test_accuracy)
        print(f"Test accuracy: {test_accuracy:.4f}")

        signature = infer_signature(X_test, model.predict(X_test))
        mlflow.sklearn.log_model(
            model,
            "model",
            signature=signature,
            input_example=X_test[:3],
            registered_model_name=MODEL_NAME,
        )

        run_id = mlflow.active_run().info.run_id

    client = MlflowClient()
    latest_version = max(
        int(v.version) for v in client.search_model_versions(f"name='{MODEL_NAME}'")
    )
    client.set_registered_model_alias(name=MODEL_NAME, alias="champion", version=latest_version)
    print(f"Registered '{MODEL_NAME}' version {latest_version} and aliased as 'champion'")
    print(f"MLflow run id: {run_id}")


if __name__ == "__main__":
    main()
