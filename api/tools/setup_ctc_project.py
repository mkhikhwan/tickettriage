#!/usr/bin/env python3
"""
Create, import, train, and deploy the TicketTriage Custom Text Classification
project via the Azure AI Language REST API.

Training data: data/ctc/out/labels.json — a curated set of 399 example
tickets across all 6 categories (a mix of clean/formal and messy/informal
phrasing). The matching .txt documents are already uploaded directly to the
team's Language resource's storage container (tickettriage-training-data);
this script only needs labels.json locally to drive the import step.

Usage (from the api/ folder, with local.settings.json filled in):
    python tools/setup_ctc_project.py

This is a one-shot setup script, not something to run repeatedly against a
shared team resource -- the Free tier only allows one hour of training time
per month. This has already been run once for the live deployment
(TicketTriageClassifier / production, ~0.90 microF1). Only re-run if the
training data genuinely changes, and only after uploading matching .txt
files to the storage container first.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

import requests

HERE = pathlib.Path(__file__).resolve().parent
API_ROOT = HERE.parent
SETTINGS_FILE = API_ROOT / "local.settings.json"
LABELS_FILE = API_ROOT.parent / "data" / "ctc" / "out" / "labels.json"

PROJECT_NAME = "TicketTriageClassifier"
DEPLOYMENT_NAME = "production"
MODEL_LABEL = "v1"
STORAGE_CONTAINER_NAME = "tickettriage-training-data"
API_VERSION = "2023-04-01"


def _load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        sys.exit(
            f"Missing {SETTINGS_FILE}. Copy local.settings.json.sample to "
            f"local.settings.json and fill in LANGUAGE_ENDPOINT / LANGUAGE_KEY first."
        )
    raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    values = raw.get("Values", {})
    endpoint = values.get("LANGUAGE_ENDPOINT", "").rstrip("/")
    key = values.get("LANGUAGE_KEY", "")
    if not endpoint or not key or "<" in endpoint or "<" in key:
        sys.exit(
            "LANGUAGE_ENDPOINT / LANGUAGE_KEY are missing or still placeholders "
            "in local.settings.json. Fill them in with the team's Language "
            "resource details before running this script."
        )
    return {"endpoint": endpoint, "key": key}


SETTINGS = _load_settings()
HEADERS = {
    "Ocp-Apim-Subscription-Key": SETTINGS["key"],
    "Content-Type": "application/json",
}


def _url(path: str) -> str:
    return f"{SETTINGS['endpoint']}/language/authoring/analyze-text/{path}"


def _poll(operation_url: str, label: str, timeout_seconds: int = 300) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        resp = requests.get(operation_url, headers=HEADERS)
        resp.raise_for_status()
        payload = resp.json()
        status = payload.get("status", "").lower()
        print(f"  [{label}] status: {status}")
        if status == "succeeded":
            return payload
        if status in {"failed", "cancelled", "partiallycompleted"}:
            raise RuntimeError(f"{label} ended with status '{status}': {json.dumps(payload, indent=2)}")
        time.sleep(5)
    raise TimeoutError(f"{label} did not finish within {timeout_seconds} seconds.")


def delete_project() -> None:
    print("Step 0/4: Deleting any existing project (clean slate)...")
    resp = requests.delete(_url(f"projects/{PROJECT_NAME}"), headers=HEADERS, params={"api-version": API_VERSION})
    if resp.status_code == 404:
        print("  No existing project found, nothing to delete.\n")
        return
    if not resp.ok:
        print(f"  Error {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    operation_url = resp.headers.get("operation-location")
    if operation_url:
        _poll(operation_url, "Delete", timeout_seconds=120)
    print("  Old project deleted.\n")
    time.sleep(5)


def create_project() -> None:
    print("Step 1/4: Creating project...")
    body = {
        "projectName": PROJECT_NAME,
        "language": "en",
        "projectKind": "CustomSingleLabelClassification",
        "multilingual": False,
        "description": "Ticket category classifier for TicketTriage capstone",
        "storageInputContainerName": STORAGE_CONTAINER_NAME,
    }
    patch_headers = dict(HEADERS)
    patch_headers["Content-Type"] = "application/merge-patch+json"
    resp = requests.patch(
        _url(f"projects/{PROJECT_NAME}"),
        headers=patch_headers,
        params={"api-version": API_VERSION},
        data=json.dumps(body),
    )
    if not resp.ok:
        print(f"  Error {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    print("  Project created.\n")


def import_data() -> None:
    print("Step 2/4: Importing labeled data...")
    if not LABELS_FILE.exists():
        sys.exit(f"Missing {LABELS_FILE}. Run data/ctc/generate_corpus.py first.")
    labels_payload = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    labels_payload["metadata"]["storageInputContainerName"] = STORAGE_CONTAINER_NAME

    resp = requests.post(
        _url(f"projects/{PROJECT_NAME}/:import"),
        headers=HEADERS,
        params={"api-version": API_VERSION},
        json=labels_payload,
    )
    resp.raise_for_status()
    operation_url = resp.headers["operation-location"]
    _poll(operation_url, "Import")
    print("  Import complete.\n")


def train_model() -> None:
    print("Step 3/4: Training model (this can take up to 30-40 minutes)...")
    body = {
        "modelLabel": MODEL_LABEL,
        "trainingConfigVersion": "latest",
        "evaluationOptions": {"kind": "percentage", "trainingSplitPercentage": 80, "testingSplitPercentage": 20},
    }
    resp = requests.post(
        _url(f"projects/{PROJECT_NAME}/:train"),
        headers=HEADERS,
        params={"api-version": API_VERSION},
        json=body,
    )
    resp.raise_for_status()
    operation_url = resp.headers["operation-location"]
    _poll(operation_url, "Training", timeout_seconds=2700)
    print("  Training complete.\n")


def deploy_model() -> None:
    print("Step 4/4: Deploying model...")
    body = {"trainedModelLabel": MODEL_LABEL}
    resp = requests.put(
        _url(f"projects/{PROJECT_NAME}/deployments/{DEPLOYMENT_NAME}"),
        headers=HEADERS,
        params={"api-version": API_VERSION},
        json=body,
    )
    resp.raise_for_status()
    operation_url = resp.headers["operation-location"]
    _poll(operation_url, "Deployment", timeout_seconds=300)
    print("  Deployment complete.\n")


def fetch_evaluation_summary() -> None:
    print("Fetching model evaluation summary...")
    resp = requests.get(
        _url(f"projects/{PROJECT_NAME}/models/{MODEL_LABEL}/evaluation/summary-result"),
        headers=HEADERS,
        params={"api-version": API_VERSION},
    )
    if not resp.ok:
        print(f"  Could not fetch evaluation: {resp.status_code} {resp.text}")
        return
    print(json.dumps(resp.json(), indent=2))


if __name__ == "__main__":
    overall_start = time.time()
    timings: dict[str, float] = {}

    def _timed(label: str, func) -> None:
        start = time.time()
        func()
        elapsed = time.time() - start
        timings[label] = elapsed
        print(f"  >>> {label} took {elapsed/60:.1f} min ({elapsed:.0f}s)\n")

    _timed("delete_project", delete_project)
    _timed("create_project", create_project)
    _timed("import_data", import_data)
    _timed("train_model", train_model)
    _timed("deploy_model", deploy_model)
    fetch_evaluation_summary()

    total = time.time() - overall_start
    print("=" * 60)
    print("TIMING SUMMARY")
    for label, elapsed in timings.items():
        print(f"  {label:<20} {elapsed/60:.1f} min")
    print(f"  {'TOTAL':<20} {total/60:.1f} min")
    print("=" * 60)
    print("Done. Set these in api/local.settings.json (and the team's")
    print("Function App application settings, via Ikhwan / Key Vault):")
    print(f"  LANGUAGE_CTC_PROJECT    = {PROJECT_NAME}")
    print(f"  LANGUAGE_CTC_DEPLOYMENT = {DEPLOYMENT_NAME}")
    print("=" * 60)