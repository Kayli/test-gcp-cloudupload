# Task: 2-Hour Architecture Planning - GCP Document Storage Service

You are asked to plan an architecture for a cloud-based Document Storage Service used by multiple internal teams, utilizing Google Cloud Platform (GCP) and assuming a local devcontainer development context.

## Context

The service must allow internal teams to:
- Upload and download documents
- Generate temporary download links
- Attach searchable metadata (tags, owner, timestamps)

## Constraints
- Files up to 500 MB
- Total scale up to 10 million files
- Multi-tenant (several teams using the same platform)
- Must run in GCP
- Moderate traffic but production reliability required
- Limited to a 2-hour exercise

## Phase 0: CI/CD setup (mandatory, ~15 minutes)

Before doing architecture work, ensure the repository is wired to GitHub with a minimal CI pipeline so changes can be validated and pushed to the remote.

- Quick steps
	- Create a remote GitHub repository (or use an existing one) and add it as `origin` in your local repo:

		```bash
		git remote add origin git@github.com:<org-or-user>/<repo>.git
		git push -u origin main
		```

	- Add a basic GitHub Actions workflow at `.github/workflows/ci.yml` to run lint/tests and (optionally) build artifacts. Example minimal workflow:

		```yaml
		name: CI
		on: [push, pull_request]
		jobs:
			build:
				runs-on: ubuntu-latest
				steps:
					- uses: actions/checkout@v4
					- name: Set up Node
						uses: actions/setup-node@v4
						with:
							node-version: '18'
					- name: Install
						run: npm ci
					- name: Lint
						run: npm run lint --if-present
					- name: Test
						run: npm test --if-present
		```

	- Add repository secrets (e.g., `GCP_SA_KEY`) through GitHub Settings > Secrets if CI needs access to GCP for integration tests or deploy steps. Prefer short-lived credentials or Workload Identity federation for production.

Timing: ~10–15 minutes to create remote, push, and add a minimal CI workflow so commits validate on GitHub.

## Phase 1: Environment setup (mandatory, ~15 minutes)

Before starting the timed planning exercise, ensure the local development environment can access GCP safely and reproducibly. Required quick steps:

- Create a workspace secrets folder: create `.secrets/` at the repo root and place your downloaded Service Account JSON there as `.secrets/gcp-sa-key.json`.
- Add `/.secrets/` to `.gitignore` to prevent accidental commits.
- Update the devcontainer to mount `.secrets/` and set `GOOGLE_APPLICATION_CREDENTIALS` (example snippet for `.devcontainer/devcontainer.json`):

	{
		"mounts": [
			"source=${localWorkspaceFolder}/.secrets,target=/workspaces/.secrets,type=bind,consistency=cached"
		],
		"remoteEnv": {
			"GOOGLE_APPLICATION_CREDENTIALS": "/workspaces/.secrets/gcp-sa-key.json"
		}
	}

- Rebuild / reopen the devcontainer so the mount and environment variable take effect.
- Verify inside the container:

	```bash
	echo "$GOOGLE_APPLICATION_CREDENTIALS"
	ls -l /workspaces/.secrets/gcp-sa-key.json
	gcloud auth activate-service-account --key-file="$GOOGLE_APPLICATION_CREDENTIALS" --quiet || true
	gcloud auth print-access-token
	```

Timing: reserve ~10–15 minutes for Phase 0 so the remainder of the 2-hour exercise focuses on architecture decisions, not tooling.

## Planning Phase Requirements

Produce a structured planning document that includes:

### 1. Clarifying assumptions
- Any missing information you would normally ask stakeholders
- Assumptions you will proceed with (e.g., local devcontainer GCP emulators vs cloud sandbox connection)

#### Missing / clarifying questions (to ask stakeholders)
- Expected read/write ratio and peak concurrent uploads/downloads?
- Retention and lifecycle requirements (how long files must be kept)?
- Compliance or region constraints (data residency, export controls)?
- Search/query needs for metadata (full-text search, faceted search, or simple tag lookups)?
- Tenant model expectations (strict isolation vs shared namespace)?
- Backup/DR RTO and RPO expectations?

#### Assumptions to proceed with in this 2-hour exercise
- Use GCS for object storage (supports >500MB and scales to millions of objects).
- Use Firestore (native mode) for metadata to keep the prototype serverless and simple.
- Use logical multi-tenancy (tenant_id in metadata + shared buckets) for speed of delivery; note trade-offs.
- Use Cloud Run for APIs; generate GCS V4 signed URLs for client uploads/downloads to avoid proxying large files.
- Development will use the provided devcontainer with an injected service account (no local emulators) to save time.
 - For the prototype: use the existing project admin service account / credentials you already have to simplify setup. Harden to least-privilege roles and rotate keys before production.

### 2. Key system capabilities
- Core functional components the system must support mapped to GCP components (e.g., Cloud Storage, Firestore/Cloud SQL, Cloud Run)

#### Mapping capabilities to GCP
- **Upload / Download (blobs):** Google Cloud Storage (GCS)
	- Use signed V4 URLs for direct client uploads/downloads to avoid routing large files through the API layer.
	- Use resumable uploads for reliability with large files (up to 500 MB). Object key pattern: `tenant/{tenantId}/files/{uuid}`.
	- Use bucket-level lifecycle rules for retention/archival (Nearline/Coldline) and object versioning if needed.

- **Metadata (tags, owner, timestamps):** Firestore (Native mode)
	- One metadata document per file with fields: `id`, `tenantId`, `ownerId`, `tags[]`, `createdAt`, `updatedAt`, `gcsPath`, `size`, `contentType`, `status`, `retentionPolicy`.
	- Indexes: `tenantId` + `tags`, `ownerId` + `createdAt` for common queries. Firestore chosen for serverless scaling and fast development; Cloud SQL is an alternative for relational queries.

- **API / Compute:** Cloud Run (serverless containers)
	- Lightweight REST endpoints to: (a) create signed upload/download URLs, (b) record/update metadata, (c) proxy metadata search.
	- Autoscaling and per-request billing suit the prototype and moderate traffic profile.

- **Access control & authentication:**

	- Use a service account for server components to perform all GCP operations (note: for the prototype we will use existing admin creds).
	- Authentication (AuthN): require Google SSO (ID tokens) for all client requests (validate `iss`, `aud`, `exp`, signature).
	- Authorization (AuthZ): deferred for the prototype — the service will NOT enforce application-level tenant authorization checks. All administrative or cross-tenant operations will be performed manually from the terminal using the existing service account credentials.
	- Temporary mitigations and cautions:
	  - Tighten service account scope where possible (restrict to the project/bucket) and rotate keys before production.
	  - Use very short-lived signed URLs (e.g., 5–15 minutes) and limit operations to expected object prefixes (`tenant/{tenantId}/...`).
	  - Audit: enable Cloud Audit Logs and monitor signed-url issuance and metadata writes closely; consider alerts for unusual activity.
	  - Plan a clear follow-up to implement server-side authZ before moving to production (document expected checks and where they will be applied).


	#### Client authentication: Google SSO (recommended)
	- Use Google as the single OIDC provider: clients authenticate via Google Sign-In / OAuth2 and present an ID token (JWT) to the API.
	- Validate ID tokens by checking `iss`, `aud`, `exp`, and signature. Prefer using API Gateway / Cloud Endpoints to validate tokens at the edge and reject unauthenticated requests early.
	- Restrict sign-in to allowed Google Workspace domains by checking the `hd` claim when required.
	- Map Google identity to application users: extract `sub` (stable Google user id) and `email`, and resolve to a `users` record in Firestore containing `userId`, `tenantId`, `role`, and `disabled`.
	- Minimal server-side authZ: verify every sensitive request by (1) validating the token, (2) loading the `users` record, (3) checking `disabled` flag and tenant membership/role, then (4) issuing signed URLs or mutating metadata.
	- Audit all signed-url issuance and metadata writes via Cloud Logging / Audit Logs for traceability and later revocation if needed.

- **Search / Querying:**
	- Basic tag/owner/time queries via Firestore indexes.
	- If advanced full-text search or complex faceting is required, consider Cloud Search or an Elastic instance.

- **Observability & ops:**
	- Cloud Logging for request logs, Cloud Monitoring for SLOs/alerts, and Cloud Trace/Error Reporting for diagnostics.

- **Backup & lifecycle:**
	- Configure GCS lifecycle to move older objects to Nearline/Coldline and optionally keep metadata snapshots in Firestore exports.

- **Developer environment:** devcontainer with injected `GOOGLE_APPLICATION_CREDENTIALS` for quick verification against real GCP resources (preferred for the 2-hour exercise).

### 3. Non-functional requirements
- Scalability
- Security
- Reliability
- Operational concerns

### 4. Major architectural decisions to resolve
- Storage strategy
- Metadata storage
- Access control model
- Handling temporary download links (e.g., GCS Signed URLs)
- Multi-tenancy isolation

#### 4a. Storage strategy (GCS + metadata schema)

Summary: Use Google Cloud Storage (GCS) for file blobs and Firestore for metadata. Keep object keys predictable and tenant-scoped so operational controls, lifecycle rules and signed-URL scoping are simple.

- Bucket & object layout
	- Prototype: one project-level bucket (e.g., `gs://<project>-docstore`). Use separate buckets per environment (dev/prod). Defer per-tenant buckets unless regulatory isolation is required.
	- Object key pattern: `tenant/{tenantId}/files/{yyyy}/{mm}/{uuid}` — date prefixes avoid single hot prefixes and make lifecycle selection easier.

- Uploads & verification
	- Clients use GCS V4 signed URLs (resumable uploads for large files). Signed URLs avoid proxying data through the API layer.
	- After upload, record/verify object checksum (MD5 or CRC32c) and contentType in Firestore metadata; optionally compare object metadata to recorded checksum.

- Lifecycle & versioning
	- Use lifecycle rules to transition objects (e.g., Nearline after 30d, Coldline after 180d) and to delete after tenant retention period.
	- Enable object versioning only if accidental-delete protection is required — versions increase storage cost and complexity.

- Metadata schema (Firestore - single collection `files`)
	- Document ID: file UUID
	- Fields: `id`, `tenantId`, `ownerEmail` (or `ownerId`), `gcsPath`, `size`, `contentType`, `checksum`, `tags` (array), `status` (uploaded/processing/archived/deleted), `createdAt`, `updatedAt`, `retentionExpiresAt`
	- Indexes: `tenantId` + `createdAt` (listings), `tenantId` + `tags` (tenant-scoped tag queries), `ownerEmail` + `createdAt`.

- Query patterns & scaling
	- Always scope queries by `tenantId`. Use cursor-based pagination for lists. Avoid broad cross-tenant scans in the prototype.
	- Limit indexed arrays (tags) cardinality; prefer an allowed tag set or tag-count limits per file to avoid index explosion.

- Deletion & garbage collection
	- Two-step deletion: mark metadata `status=deleted` -> delete GCS object (or rely on lifecycle) -> remove metadata after retention/confirmation.
	- Consider a background worker (Cloud Run job / Cloud Tasks) to reconcile metadata and objects periodically.

- Operational notes & cost
	- Monitor object counts and egress; signed-URL uploads shift network bandwidth to clients and reduce server costs.
	- Use lifecycle tiers to reduce long-term storage cost; track Firestore document growth (index costs) for very large scales.

#### 4b. Access & Signed URLs (IAM, signed-V4, resumable uploads)

Summary: Use narrowly-scoped service accounts for server-side operations and issue short-lived Signed V4 URLs for client uploads/downloads. Favor resumable uploads for files near the 500 MB limit to avoid proxying large payloads through Cloud Run.

- IAM & service account scoping
	- Create a dedicated service account for the DocStore backend (e.g., `docstore-sa@<project>.iam.gserviceaccount.com`).
	- For the prototype, grant `roles/storage.objectAdmin` on the target bucket(s) scoped via bucket-level IAM bindings. For production, create distinct custom roles (signing vs metadata) and narrow permissions to least-privilege.
	- Apply IAM Conditions where supported to restrict access to object prefixes like `projects/_/buckets/<bucket>/objects/tenant/${request.auth.claims.tenantId}/*`.

- Signed V4 URL issuance
	- Server (Cloud Run) validates the caller's Google SSO ID token, checks tenant context, then issues a Signed V4 URL with appropriate method (`PUT`/`POST`/`GET`) and headers.
	- TTLs: keep download URLs short (5–15 minutes). For uploads, allow slightly longer (up to 30 minutes) to accommodate resumable flows and retries.
	- Use service-account signing or Cloud KMS SignBlob to avoid embedding long-lived keys in container images.

- Resumable uploads for large files
	- Initiate a resumable upload session via a signed URL; the client receives a resumable session URI from GCS and uploads chunks directly to GCS.
	- This prevents Cloud Run from handling large request bodies and mitigates timeout/memory limits.

- Validation and finalization
	- After upload completion, client notifies metadata API (or use Pub/Sub notifications) so the service can verify object existence, size and checksum, update Firestore metadata and set `status=uploaded`.
	- Optionally use Cloud Storage notifications (Pub/Sub) to trigger asynchronous reconciliation and checksum verification jobs.

- Security mitigations and operational controls
	- Rate-limit signed-URL issuance per user; instrument logs/metrics for issuance and failed attempts.
	- Because signed URLs cannot be revoked directly, enforce short TTLs and use object-level ACL/IAM or object deletion to mitigate abuse if needed.
	- Monitor egress, failed uploads, and anomalous signed-URL patterns via Cloud Monitoring alerts.

- Large-file and client guidance
	- Recommend client libraries and chunk sizes for resumable uploads; document recommended retry strategies and TTL expectations.

#### 4c. Multi-tenancy (logical vs physical)

Summary: For the 2-hour prototype choose logical multi-tenancy (tenant ID in metadata with shared buckets). This minimizes setup complexity and eases cross-tenant operational tasks while noting production trade-offs.

- Logical multi-tenancy (recommended for prototype)
	- Approach: single shared bucket per environment + Firestore `tenantId` field on metadata documents.
	- Pros: simpler provisioning, lower operational overhead, easier to query across tenants for admin tasks, cheaper to manage at scale in Firestore.
	- Cons: requires strict application-level scoping to avoid accidental access, more complex tenant-level quotas and per-tenant billing, potential noisy-neighbor concerns.
	- Mitigations: enforce upload prefixes (`tenant/{tenantId}/...`), issue signed URLs scoped to tenant prefixes, use IAM Conditions where available, implement rate-limits and per-tenant quotas.

- Physical multi-tenancy (bucket-per-tenant)
	- Approach: provision a separate bucket per tenant or tenant groups.
	- Pros: strong isolation (separation of data at storage level), easier per-tenant billing and lifecycle policies, simpler to meet strict compliance/regulatory requirements.
	- Cons: operational overhead (many buckets), higher IAM management complexity, potential project/bucket limits at very large tenant counts.

- Recommendation for 2-hour exercise
	- Use logical multi-tenancy for speed: shared bucket + `tenantId` in Firestore, plus prefix-scoped signed URLs and monitoring.
	- Document the migration plan to move to physical isolation if required later: automated bucket provisioning, tenant-export/import utilities, and updated IAM automation.

### 5. High-level system decomposition

Summary: Break the system into small, focused subsystems (serverless where possible) to keep the prototype simple and testable.

- **Upload Service (Cloud Run)**
	- Responsibilities: authenticate requester (ID token), authorize upload intent (prototype: minimal checks), create Signed V4 URL (resumable if needed), create initial metadata record (`status=uploading`), and return the signed URL to client.
	- Endpoints:
		- `POST /uploads` -> request signed upload URL (body: `tenantId`, `filename`, `contentType`, `size`, `tags`)
		- `POST /uploads/:id/complete` -> confirm upload finished (client supplies checksum or object path)
	- Inputs/Outputs: receives upload metadata; outputs signed URL and upload id.

- **Download / Auth Service (Cloud Run or API Gateway + Cloud Run)**
	- Responsibilities: validate client ID token, lookup metadata, optionally check tenant membership, generate short-lived Signed V4 download URLs, and enforce download limits.
	- Endpoint: `GET /files/:id/download` -> returns Signed V4 GET URL.

- **Metadata & Search Service (Cloud Run + Firestore)**
	- Responsibilities: CRUD metadata documents in Firestore, provide paginated search by `tenantId`/`tags`/`owner`, and manage indexes.
	- Endpoint examples: `GET /files?tenantId=...&cursor=...`, `GET /files/:id`, `PATCH /files/:id`.

- **Reconciliation Worker (Cloud Run job / Cloud Tasks triggered by Pub/Sub)**
	- Responsibilities: reconcile Pub/Sub notifications or periodically scan Firestore to ensure GCS objects and metadata match (checksums, sizes), set `status` appropriately, and retry failed validations.

- **Admin / Orchestration (CLI scripts + small admin UI)**
	- Responsibilities: tenant onboarding, lifecycle policy changes, bulk exports/imports, and running maintenance tasks. For prototype, prefer CLI scripts using the injected service account.

- **Infrastructure & Integrations**
	- Storage: GCS buckets (storage of blobs)
	- Notifications: Cloud Storage -> Pub/Sub -> Reconciliation Worker
	- Observability: Cloud Logging, Monitoring, Error Reporting.

Deployment notes: use Cloud Run revisions for safe rollout, and Cloud Build / GitHub Actions for CI; keep container images small and stateless.

### 6. Risks and trade-offs

Summary: Document key risks introduced by the prototype choices, their impact, and short-term mitigations plus longer-term remediation paths.

- Firestore indexing and query limits
	- Risk: Large numbers of tags or high-cardinality indexed fields can cause index explosion and increased costs or quota issues.
	- Impact: slower writes, higher storage/index costs, potential quota exhaustion.
	- Mitigation: limit indexed array cardinality, use a controlled tag vocabulary, add composite indexes only where required, and monitor index growth; consider moving heavy search to a dedicated search service if needed.

- Authentication & Authorization gaps (prototype decision)
	- Risk: Deferring application-level AuthZ means potential accidental cross-tenant access if signed URLs or metadata are mis-scoped.
	- Impact: data exposure, compliance violations.
	- Mitigation: enforce tenant-scoped prefixes in signed URLs, keep very short TTLs, restrict service account permissions, enable Cloud Audit Logs and alerting; prioritize implementing server-side AuthZ before production.

- Cold starts and request latency (Cloud Run)
	- Risk: Cloud Run cold starts can increase latency for bursty workloads.
	- Impact: poor user experience on first requests, potential SLA issues.
	- Mitigation: tune concurrency and min-instances for critical endpoints, keep containers slim to reduce cold start time, and consider using Cloud Run with minimum instances for predictable traffic.

- IAM and quota management at scale
	- Risk: Bucket-per-tenant approach (if chosen later) increases IAM complexity and may hit resource limits for very large tenant counts.
	- Impact: operational overhead, provisioning delays.
	- Mitigation: prefer logical multi-tenancy initially; if moving to buckets-per-tenant, automate provisioning and monitor project/bucket quotas.

- Large-file upload reliability and cost
	- Risk: Failed large uploads increase storage ingress/egress and operational retries.
	- Impact: wasted bandwidth/cost, inconsistent metadata/object state.
	- Mitigation: use resumable uploads, require client retries with exponential backoff, verify checksums server-side, and use Pub/Sub notifications for async reconciliation.

- Data residency, compliance, and encryption key management
	- Risk: Regulatory or compliance requirements (CMEK, specific region storage) add complexity.
	- Impact: additional engineering and operational burden, potential costs.
	- Mitigation: identify compliance needs early; for prototype, document required controls and defer CMEK/VPC-SC work to a hardened production sprint.

- Cost surprises (egress, Firestore index growth)
	- Risk: signed-URL usage shifts bandwidth to clients but egress and storage lifecycle choices can still produce surprises.
	- Impact: unexpectedly high monthly bills.
	- Mitigation: set budgets/alerts in Cloud Billing, instrument cost-sensitive metrics, and review sample workloads for cost estimates.

Decision notes: mark high-risk items as follow-up action items (AuthZ implementation, index strategy review, production-grade IAM scoping) before promoting to production.

## Output expectations
- Structured outline (not a full architecture yet)
- Focus on problem framing and decision planning
- Diagrams optional but not required


