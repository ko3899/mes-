# Edge Gateway Runtime and Transport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the durable edge outbox as an independent process that safely delivers events through interchangeable authenticated HTTP or MQTT transports.

**Architecture:** `DeliveryPump` owns claim/send/ack/retry semantics and depends only on a transport protocol. A strict environment-backed configuration creates either an HTTP HMAC transport or an MQTT QoS1 mTLS transport. The central MES accepts gateway HMAC requests on a dedicated endpoint and continues to use the existing idempotent ingestion service.

**Tech Stack:** Python 3.8, SQLite, urllib, hmac/sha256, Flask, optional paho-mqtt 1.6+, pytest.

## Global Constraints

- Never acknowledge the edge outbox before central durable acceptance.
- One in-flight event per device; leases expire and retry safely.
- Gateway credentials are never accepted in JSON payloads or returned by APIs.
- HTTP signatures bind gateway ID, timestamp, nonce and exact request body; replay is rejected.
- MQTT production mode requires TLS CA, client certificate and private key; QoS must be 1.
- Existing AIM and admin APIs remain compatible.

---

### Task 1: Delivery Pump and Lease-Safe Failure Handling

**Files:**
- Create: `backend/edge_gateway/delivery.py`
- Modify: `backend/edge_gateway/event_store.py`
- Test: `tests/test_edge_delivery.py`

**Interfaces:** `DeliveryTransport.send(event) -> DeliveryReceipt`; `DeliveryPump.run_once() -> DeliverySummary`; `release(event_id,worker_id,error)` clears the lease and increments attempts.

- [ ] Write tests for accepted, duplicate, transport failure, wrong-worker acknowledgement and per-device ordering.
- [ ] Run `python -m pytest -q tests/test_edge_delivery.py` and verify RED import failure.
- [ ] Implement minimal delivery pump and lease-owner-aware release.
- [ ] Run delivery and edge store tests; expect all pass.
- [ ] Commit `feat: add lease-safe edge delivery pump`.

### Task 2: Gateway HMAC Authentication and HTTP Transport

**Files:**
- Create: `backend/services/gateway_auth.py`
- Create: `backend/edge_gateway/http_transport.py`
- Modify: `backend/blueprints/device_platform.py`
- Modify: `backend/utils/database.py`
- Test: `tests/test_gateway_http_transport.py`

**Interfaces:** Dedicated `POST /api/device-platform/gateway-events`; headers `X-Gateway-Id`, `X-Gateway-Time`, `X-Gateway-Nonce`, `X-Gateway-Signature`; HMAC-SHA256 over `gateway_id\ntimestamp\nnonce\nsha256(body)`.

- [ ] Write tests for valid request, invalid signature, stale timestamp, nonce replay and HTTP receipt mapping.
- [ ] Run focused test and verify RED.
- [ ] Add gateway credential/nonces tables, authentication service, endpoint and stdlib HTTP client.
- [ ] Run API, transport and migration regressions; expect all pass.
- [ ] Commit `feat: authenticate edge gateway HTTP delivery`.

### Task 3: Standalone Edge Runtime

**Files:**
- Create: `edge_gateway_service.py`
- Create: `backend/edge_gateway/config.py`
- Test: `tests/test_edge_gateway_runtime.py`
- Modify: `.gitignore`

**Interfaces:** environment variables `MES_EDGE_DB`, `MES_EDGE_GATEWAY_ID`, `MES_EDGE_TRANSPORT`, transport credentials and polling/lease settings; `--once` performs one bounded delivery cycle.

- [ ] Write tests for missing/unsafe configuration, HTTP construction, `--once`, and secret-safe diagnostics.
- [ ] Verify RED, implement config and CLI, then verify GREEN.
- [ ] Add runtime database and local secrets paths to ignore rules.
- [ ] Commit `feat: run edge delivery as a standalone service`.

### Task 4: MQTT QoS1 mTLS Transport

**Files:**
- Create: `backend/edge_gateway/mqtt_transport.py`
- Modify: `backend/edge_gateway/config.py`
- Modify: `requirements.txt`
- Test: `tests/test_mqtt_transport.py`
- Create: `docs/edge-gateway-runtime.md`

**Interfaces:** publish topic `mes/v1/{customer}/{factory}/{gateway}/events/{device}`; QoS 1; receipt succeeds only after PUBACK; TLS files are mandatory outside explicit test mode.

- [ ] Write fake-client tests for topic, payload, QoS, PUBACK timeout and mandatory TLS.
- [ ] Verify RED, implement paho adapter behind lazy import, verify GREEN.
- [ ] Run the complete Python suite and documentation configuration check.
- [ ] Document Windows/Linux service startup, certificates, firewall, HTTP fallback and recovery.
- [ ] Commit `feat: deliver edge events over mqtt tls`.
