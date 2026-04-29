# ADR-008: GitHub Webhook Deployment with HMAC Verification

**Status:** Accepted  
**Date:** 2026-04-28  
**Related:** PROJECT_OPS_PROTOCOL.md

---

## Context

TimeWoven requires a reliable and automated deployment mechanism.

The system architecture defines:

* GitHub as the single source of truth for code,
* a production server responsible for execution,
* a deployment script (`update_timewoven.sh`) that updates the application.

Previously, deployment was triggered manually or via insecure mechanisms:

* query-based secrets (`?secret=...`),
* internal admin endpoints (`/admin/deploy`),
* lack of standardized verification for incoming requests.

This created security risks and inconsistency in deployment flow.

---

## Problem

The existing deployment approach was not production-safe:

* secrets exposed via query parameters,
* multiple deployment entry points,
* lack of strict request validation,
* risk of unauthorized deployment execution.

Without a unified and secure mechanism:

* deployment could be triggered externally,
* system integrity could be compromised,
* architecture would become inconsistent.

---

## Decision

Adopt GitHub Webhook as the only deployment trigger, secured via HMAC verification.

### 1. Deployment trigger

Deployment is triggered exclusively via:

POST /deploy

---

### 2. Security model

All incoming requests must include:

X-Hub-Signature-256

Verification is performed using:

* HMAC SHA256
* shared secret (`GITHUB_WEBHOOK_SECRET`)

---

### 3. Fail-fast validation

The system enforces strict validation:

* missing signature → reject (403)
* invalid signature → reject (403)
* missing secret → error (500)

No side effects are allowed before validation completes.

---

### 4. Single deployment entry point

The system enforces:

* exactly one public endpoint (`/deploy`)
* removal of alternative paths (`/admin/deploy`)
* no fallback mechanisms

---

### 5. Deployment execution

After successful validation:

* the deploy script is executed asynchronously:

/root/scripts/deploy/update_timewoven.sh

---

## Consequences

### Positive

* secure deployment flow
* no secret exposure
* single, consistent entry point
* alignment with GitHub-native workflow
* elimination of legacy endpoints

---

### Negative

* dependency on correct GitHub webhook configuration
* deployment unavailable if signature validation fails
* requires environment variable (`GITHUB_WEBHOOK_SECRET`)

---

## Scope

This ADR defines:

* deployment trigger mechanism
* security model for deployment
* endpoint structure for deploy

This ADR does NOT include:

* deployment script internals
* CI/CD pipelines (GitHub Actions)
* infrastructure provisioning
* rollback strategy

---

## Implementation Path

### Phase 1 — Endpoint normalization

* introduce `/deploy` endpoint
* remove duplicate or insecure endpoints

### Phase 2 — Security enforcement

* implement HMAC verification
* enforce fail-fast validation

### Phase 3 — Cleanup

* remove `/admin/deploy`
* remove query-based secrets

---

## Notes

This ADR establishes a strict and secure deployment contract:

> deployment is allowed only via authenticated GitHub webhook requests.

This ensures that:

* GitHub remains the single source of truth,
* the server acts only as an execution environment,
* deployment cannot be triggered manually or externally.

