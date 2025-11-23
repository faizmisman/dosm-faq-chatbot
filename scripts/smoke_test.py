#!/usr/bin/env python3
"""Kubernetes smoke test for DOSM FAQ Chatbot API.

Steps:
1. Fetch API key from a Kubernetes secret (base64 decode).
2. Port-forward service locally (svc/<service>:80 -> localhost:8000).
3. Hit /health endpoint and validate status.
4. Issue /predict request with a sample query.
5. Print results and exit non-zero if failures encountered.

Requires: kubectl in PATH, access to cluster context, Python >=3.10.

Usage:
  python scripts/smoke_test.py \
    --namespace dosm-dev \
    --service faq-chatbot-dosm-insights \
    --secret app-secrets \
    --api-key-key API_KEY

When DATABASE_URL is not configured, /health 'db' check may be 'unconfigured'.
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error
from contextlib import contextmanager

PORT_LOCAL = 8000

@contextmanager
def port_forward(namespace: str, service: str):
    # Use service port 80 -> localhost:8000
    cmd = [
        "kubectl", "port-forward", f"svc/{service}", f"{PORT_LOCAL}:80", "-n", namespace
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        # Wait until port-forward establishes or errors
        ready = False
        start = time.time()
        while time.time() - start < 15:
            line = proc.stdout.readline().decode("utf-8", errors="ignore")
            if line:
                if "Forwarding from" in line:
                    ready = True
                    break
                if "error" in line.lower():
                    break
            if proc.poll() is not None:
                break
        if not ready:
            raise RuntimeError("port-forward failed to become ready in time")
        yield
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def fetch_api_key(namespace: str, secret: str, key: str) -> str | None:
    cmd = [
        "kubectl", "get", "secret", secret, "-n", namespace,
        "-o", f"jsonpath={{.data.{key}}}"
    ]
    try:
        raw = subprocess.check_output(cmd).decode().strip()
        if not raw:
            return None
        return base64.b64decode(raw).decode()
    except subprocess.CalledProcessError:
        return None


def http_get(path: str, headers: dict[str, str] | None = None):
    url = f"http://127.0.0.1:{PORT_LOCAL}{path}"
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return -1, str(e)


def http_post(path: str, payload: dict, headers: dict[str, str] | None = None):
    url = f"http://127.0.0.1:{PORT_LOCAL}{path}"
    body = json.dumps(payload).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return -1, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--namespace", required=True)
    ap.add_argument("--service", required=True)
    ap.add_argument("--secret", required=True)
    ap.add_argument("--api-key-key", default="API_KEY")
    ap.add_argument("--query", default="What is the system?")
    args = ap.parse_args()

    api_key = fetch_api_key(args.namespace, args.secret, args.api_key_key)
    if api_key:
        print("[info] Retrieved API key (length=%d)" % len(api_key))
    else:
        print("[warn] API key not found; predict will likely be unauthorized.")

    failures = []
    with port_forward(args.namespace, args.service):
        # Health
        status, body = http_get("/health")
        print(f"[health] status={status} body={body}")
        if status != 200:
            failures.append("health-non-200")
        else:
            try:
                hjson = json.loads(body)
                if hjson.get("status") not in ("ok", "degraded"):
                    failures.append("health-bad-status")
            except json.JSONDecodeError:
                failures.append("health-invalid-json")
        # Predict
        headers = {"X-API-Key": api_key} if api_key else {}
        status, body = http_post("/predict", {"query": args.query}, headers)
        print(f"[predict] status={status} body={body}")
        if status != 200:
            failures.append("predict-non-200")
        else:
            try:
                pjson = json.loads(body)
                if "prediction" not in pjson:
                    failures.append("predict-missing-payload")
            except json.JSONDecodeError:
                failures.append("predict-invalid-json")

    if failures:
        print("[result] FAIL ->", ",".join(failures))
        return 1
    print("[result] PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
