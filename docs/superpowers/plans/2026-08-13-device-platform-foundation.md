# Device Platform Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the first working vertical slice of the private-deployment device platform: validated standard events, a durable edge outbox, central idempotent ingestion, an authenticated API, and an AIM compatibility bridge.

**Architecture:** Protocol adapters create immutable `DeviceEvent` values and append them to a local SQLite outbox before acknowledging devices. A transport sends pending envelopes to the central MES ingestion API, which persists each `event_id` once and records per-device sequence gaps. Existing AIM code remains operational and can emit the same standard event through a compatibility bridge.

**Tech Stack:** Python 3, Flask, SQLite for the first development slice, pytest, dataclasses, JSON. PostgreSQL and MQTT replace the central development transports in later plans without changing the event contract.

## Global Constraints

- Preserve all existing AIM routes and runtime data.
- Use schema version `1.0` and UTC/RFC 3339 timestamps with timezone offsets.
- Every event has a globally unique `event_id`; ingestion is idempotent on that value.
- A device sequence is a positive integer and increases within one device identity.
- Payload must be a JSON object; unknown event types are rejected.
- Critical edge events are committed locally before they are returned to the adapter.
- No device command may bypass PLC or现场安全联锁.

---

### Task 1: Standard Event and Command Contracts

**Files:**
- Create: `backend/device_platform/__init__.py`
- Create: `backend/device_platform/contracts.py`
- Test: `tests/test_device_platform_contracts.py`

**Interfaces:**
- Produces: `DeviceEvent.from_dict(data)`, `DeviceEvent.to_dict()`, `DeviceCommand.from_dict(data)`, `ContractError`.
- `DeviceEvent` fields are `schema_version,event_id,customer_code,factory_code,gateway_code,device_code,event_type,occurred_at,received_at,sequence,correlation_id,payload,raw_reference`.

- [ ] **Step 1: Write failing contract tests**

```python
def test_event_round_trip_and_validation():
    event = DeviceEvent.from_dict(valid_event())
    assert event.to_dict()["event_id"] == "EV-001"
    with pytest.raises(ContractError):
        DeviceEvent.from_dict({**valid_event(), "sequence": 0})
```

- [ ] **Step 2: Run RED test**

Run: `python -m pytest -q tests/test_device_platform_contracts.py`
Expected: import failure because `device_platform.contracts` does not exist.

- [ ] **Step 3: Implement immutable dataclasses and exact validation**

```python
@dataclass(frozen=True)
class DeviceEvent:
    schema_version: str
    event_id: str
    customer_code: str
    factory_code: str
    gateway_code: str
    device_code: str
    event_type: str
    occurred_at: str
    received_at: str | None
    sequence: int
    correlation_id: str | None
    payload: dict
    raw_reference: str | None
```

Validation accepts only the event types listed in the approved design and parses both timestamps with `datetime.fromisoformat(value.replace('Z','+00:00'))`; timestamps without timezone information fail.

- [ ] **Step 4: Run GREEN test and existing machine protocol tests**

Run: `python -m pytest -q tests/test_device_platform_contracts.py tests/test_machine_protocol.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```text
git add backend/device_platform tests/test_device_platform_contracts.py
git commit -m "feat: define standard device event contracts"
```

### Task 2: Durable Edge Event Outbox

**Files:**
- Create: `backend/edge_gateway/__init__.py`
- Create: `backend/edge_gateway/event_store.py`
- Test: `tests/test_edge_event_store.py`

**Interfaces:**
- Consumes: `DeviceEvent` from Task 1.
- Produces: `EdgeEventStore(path)`, `append(event) -> bool`, `pending(limit=100) -> list[DeviceEvent]`, `ack(event_id) -> bool`, `fail(event_id,error) -> bool`, `stats() -> dict`.

- [ ] **Step 1: Write failing persistence and ordering tests**

```python
def test_outbox_is_durable_idempotent_and_device_ordered(tmp_path):
    store = EdgeEventStore(tmp_path / "edge.db")
    assert store.append(event("D2", 2, "E2")) is True
    assert store.append(event("D1", 1, "E1")) is True
    assert store.append(event("D1", 1, "E1")) is False
    assert [e.event_id for e in EdgeEventStore(tmp_path / "edge.db").pending()] == ["E1", "E2"]
```

- [ ] **Step 2: Run RED test**

Run: `python -m pytest -q tests/test_edge_event_store.py`
Expected: import failure because `edge_gateway.event_store` does not exist.

- [ ] **Step 3: Implement SQLite outbox**

The table uses `event_id TEXT PRIMARY KEY`, `device_code`, `sequence`, canonical JSON, `status`, attempts, error, created and acknowledged timestamps. `append` uses one transaction; `pending` orders by `device_code,sequence,id`; `ack` changes only pending rows to acknowledged.

- [ ] **Step 4: Run GREEN and restart durability tests**

Run: `python -m pytest -q tests/test_edge_event_store.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```text
git add backend/edge_gateway tests/test_edge_event_store.py
git commit -m "feat: add durable edge event outbox"
```

### Task 3: Central Idempotent Event Ingestion

**Files:**
- Create: `backend/services/device_event_ingest.py`
- Modify: `backend/utils/database.py`
- Test: `tests/test_device_event_ingest.py`

**Interfaces:**
- Consumes: `DeviceEvent`.
- Produces: `ingest_device_event(db,event) -> IngestResult` with `accepted,duplicate,gap_expected,gap_actual`.

- [ ] **Step 1: Write failing ingestion tests**

```python
first = ingest_device_event(db, event("D1", 1, "E1"))
duplicate = ingest_device_event(db, event("D1", 1, "E1"))
gap = ingest_device_event(db, event("D1", 3, "E3"))
assert first.accepted and not first.duplicate
assert duplicate.duplicate
assert (gap.gap_expected, gap.gap_actual) == (2, 3)
```

- [ ] **Step 2: Run RED test**

Run: `python -m pytest -q tests/test_device_event_ingest.py`
Expected: import failure because ingestion service does not exist.

- [ ] **Step 3: Add central tables and transactional ingestion**

Add `iot_device_event` with unique `event_id`, factory/gateway/device/event/sequence/timestamps/payload/raw reference and processing status; add `iot_device_cursor` keyed by `(factory_code,device_code)`; add `iot_device_sequence_gap` unique on device and missing range. In one `BEGIN IMMEDIATE` transaction insert the event, update cursor only when sequence advances, and record a gap when `sequence > last_sequence + 1`.

- [ ] **Step 4: Run GREEN and database migration tests**

Run: `python -m pytest -q tests/test_device_event_ingest.py tests/test_production_chain_migration.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```text
git add backend/services/device_event_ingest.py backend/utils/database.py tests/test_device_event_ingest.py
git commit -m "feat: ingest device events idempotently"
```

### Task 4: Authenticated Central Ingestion API

**Files:**
- Create: `backend/blueprints/device_platform.py`
- Modify: `backend/app.py`
- Test: `tests/test_device_platform_api.py`

**Interfaces:**
- Produces: `POST /api/device-platform/events`, `GET /api/device-platform/events`, `GET /api/device-platform/health`.
- In the development slice POST requires an authenticated MES session; gateway certificate authentication replaces this at the transport boundary in the MQTT/mTLS plan.

- [ ] **Step 1: Write failing API tests**

```python
response = client.post('/api/device-platform/events', json=valid_event())
assert response.status_code == 201
assert client.post('/api/device-platform/events', json=valid_event()).get_json()['data']['duplicate'] is True
assert create_app().test_client().post('/api/device-platform/events', json=valid_event()).status_code == 401
```

- [ ] **Step 2: Run RED test**

Run: `python -m pytest -q tests/test_device_platform_api.py`
Expected: 404 because the blueprint is not registered.

- [ ] **Step 3: Implement routes and register blueprint**

POST parses `DeviceEvent`, returns 400 for `ContractError`, 201 for a new event and 200 for a duplicate. List endpoints paginate without exposing raw credentials; health returns event totals, unprocessed totals and open sequence gaps.

- [ ] **Step 4: Run GREEN and app API regression tests**

Run: `python -m pytest -q tests/test_device_platform_api.py tests/test_machine_iot_api.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```text
git add backend/blueprints/device_platform.py backend/app.py tests/test_device_platform_api.py
git commit -m "feat: expose central device event ingestion API"
```

### Task 5: AIM Compatibility Event Bridge

**Files:**
- Create: `backend/services/aim_event_bridge.py`
- Modify: `backend/services/machine_access.py`
- Test: `tests/test_aim_event_bridge.py`

**Interfaces:**
- Consumes: existing AIM request/report rows.
- Produces: `aim_report_event(endpoint,request_row,report_row,measurements) -> DeviceEvent` and optional `event_sink(DeviceEvent)` injection in report import.

- [ ] **Step 1: Write failing AIM mapping tests**

Verify OK maps to `quality.completed` with `result=OK`, NG maps to `result=NG`, identifiers include endpoint/report IDs, and repeat mapping produces the same `event_id`.

- [ ] **Step 2: Run RED test**

Run: `python -m pytest -q tests/test_aim_event_bridge.py`
Expected: import failure because bridge does not exist.

- [ ] **Step 3: Implement deterministic mapping without changing legacy results**

Use `AIM:{endpoint_id}:REPORT:{report_id}` as event ID and report ID as sequence. Emit only after the existing AIM transaction commits; sink failures are logged and retried by the later transport plan, never used to roll back an imported report.

- [ ] **Step 4: Run GREEN and full AIM suite**

Run: `python -m pytest -q tests/test_aim_event_bridge.py tests/test_machine_access_service.py tests/test_machine_csv_flow.py tests/test_machine_csv_collector.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```text
git add backend/services/aim_event_bridge.py backend/services/machine_access.py tests/test_aim_event_bridge.py
git commit -m "feat: bridge AIM reports to standard device events"
```

### Task 6: Foundation Verification and Operator Documentation

**Files:**
- Create: `docs/device-platform-foundation.md`
- Modify: `README.md`
- Test: existing Python suite.

**Interfaces:**
- Documents local database paths, event API examples, outbox recovery, health meanings, and the explicit boundary that MQTT/mTLS and production PostgreSQL follow in later phases.

- [ ] **Step 1: Run the complete Python suite**

Run: `python -m pytest -q`
Expected: all collected tests pass.

- [ ] **Step 2: Write exact setup and recovery instructions**

Document creating an event, appending to the edge outbox, ingesting it, acknowledging only after HTTP success, inspecting gaps, and backing up the central and edge databases.

- [ ] **Step 3: Verify documentation commands in a temporary directory**

Run each Python and HTTP-independent example against a temporary SQLite file; expected output shows one pending event, one accepted event and zero pending after acknowledgement.

- [ ] **Step 4: Commit**

```text
git add docs/device-platform-foundation.md README.md
git commit -m "docs: explain device platform foundation"
```
