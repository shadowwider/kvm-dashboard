# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Real-time monitoring dashboard for Shanghai Airport G&D KVM devices (ControlCenter-Compact / ControlCenter-IP). Dual-channel monitoring via active SNMP polling + passive trap reception, with WebSocket-pushed real-time updates to the frontend.

## Development Commands

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev        # http://localhost:3000, proxies /api → localhost:8000
npm run build
npm run lint
```

### Docker (production)
```bash
docker-compose build && docker-compose up -d
```

### End-to-end simulation (3 devices × 20 endpoints)
```bash
# Terminal 1
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
# Terminal 2
cd backend && python run_simulators_large.py
# Terminal 3
cd frontend && npm run dev -- --force
# Login: admin / admin123 → http://localhost:3000
```

## Architecture

```
SNMP Devices
    ↓ poll every 60s (APScheduler, 20-device semaphore)
pysnmp SnmpEngine Pool (async, pooled engines)
    ↓
SQLite (dev) / PostgreSQL + TimescaleDB (prod)
    ↓
FastAPI (single worker) + WebSocket Hub
    ↓
Nginx reverse proxy
    ↓
React 19 + Zustand frontend
```

**DB selection**: controlled by `DB_MODE` env var. SQLite uses `aiosqlite`, Postgres uses `asyncpg`.

**Single-worker constraint**: Dockerfile runs `--workers 1` intentionally — APScheduler lives in-process; multiple workers cause duplicate polling cycles. Do not increase worker count.

## Key Backend Modules

| Path | Role |
|------|------|
| `app/main.py` | Lifespan: DB init, seed data, scheduler registration, trap receiver startup |
| `app/snmp/poller.py` | Core poll loop — SnmpEngine pool, semaphore, early exit on offline device |
| `app/snmp/parser.py` | SNMP value parsing, alert threshold evaluation, 10-min dedup window |
| `app/snmp/oid_map.py` | G&D CCDC OID definitions (`1.3.6.1.4.1.32828.*`) and DB seed data |
| `app/snmp/trap_receiver.py` | UDP 162 listener |
| `app/websocket/hub.py` | `ws_manager` — broadcast and per-topic subscription |
| `app/api/topology.py` | Generates hierarchical device→cpu/con→port tree |
| `app/models/` | 8 SQLAlchemy 2.0 async models |

## Key Frontend Components

| Path | Role |
|------|------|
| `pages/Dashboard.jsx` | Main screen: KPIs, device cards, matrix/topology toggle, alerts, charts |
| `pages/Admin.jsx` | 5-tab admin panel: Devices, Endpoints, OIDs, Alerts, Users |
| `components/TopoView.jsx` | **Pure SVG** topology — no React Flow/D3. Hand-written for animation control |
| `components/BottomCharts.jsx` | **Pure SVG** charts — no ECharts. Temperature line, fan gauge, online-rate bar |
| `components/MatrixView.jsx` | Endpoint grid — click opens `EndpointDetail` panel |
| `hooks/useSystemWebSocket.js` | WebSocket client, handles `device_update` / `new_alerts` / `trap_received` |
| `store/mainStore.js` | Zustand: stats, devices, endpoints, alerts, topology, aliases, oidConfigs |
| `store/authStore.js` | Zustand persist: JWT token + user role |
| `utils/api.js` | axios instance with JWT header injection and 401→logout redirect |
| `i18n/index.js` | CN/EN strings — no hardcoded UI text allowed |

Several legacy components exist (`DeviceMatrix`, `EndpointGrid`, `MetricChart`, `TopologyView`, `EndpointNode`, `HealthRate`, `StatsBar`) — they are unused and can be ignored.

## Critical Pitfalls (from `/docs/HANDOVER.md`)

1. **pysnmp ObjectIdentity**: must receive a tuple `(1,3,6,1,...)`, not a string. Simulator return values must be coerced to `pMod.ObjectIdentifier()`.

2. **SQLite vs PostgreSQL time arithmetic**: SQLite rejects `INTERVAL '24 hours'`; use Python `datetime` objects with `timezone.utc` instead. Frontend date-fns requires an `isValid()` guard before formatting.

3. **Polling deadlock**: offline devices with long WALK operations block the 60s cycle. The early-exit on `sysObjectID` timeout is load-bearing — do not remove it.

## Alert Deduplication

Alerts are suppressed within a 10-minute window per `(device_id, oid_name)` pair. This is intentional to prevent alert storms from flapping devices.

## OID Configuration

All monitored metrics are stored in the `oid_registry` table with per-OID toggles: `poll_enabled`, `archive_enabled`, `alert_enabled`, `display_enabled`. Seed data is in `app/snmp/oid_map.py`. Do not hardcode OID behavior — use the registry.

## Reference Docs

- `docs/HANDOVER.md` — production pitfalls and design decisions
- `tasks/api_docs.md` — full API contract with request/response examples
- `tasks/lessons.md` — learned lessons on concurrency, DB compat, MIB trust
- `docs/metrics_reference.md` — metric definitions and calculation formulas
