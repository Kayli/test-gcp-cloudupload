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

## Phase 0: Environment setup (mandatory, ~15 minutes)

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

### 5. High-level system decomposition
- Identify the main subsystems or services without yet designing their internals.

### 6. Risks and trade-offs
- Identify the areas where different architectural choices may significantly affect the system.

## Output expectations
- Structured outline (not a full architecture yet)
- Focus on problem framing and decision planning
- Diagrams optional but not required

## Todo (consolidated)

The actionable todo list for this 2-hour exercise. This file is the single source of truth for planning steps and progress.

```markdown
- [x] Secure API Key
	- 1. Create `.secrets/` folder in workspace root. 2. Move `<id>.json` to `.secrets/gcp-sa-key.json`. 3. Add `/.secrets/` to `.gitignore`. 4. Run `git status` to verify the key is ignored.
- [x] Configure Devcontainer Auth
	- 1. Edit `.devcontainer/devcontainer.json`. 2. Add mount: `"source=${localWorkspaceFolder}/.secrets,target=/workspaces/.secrets,type=bind"`. 3. Add `"containerEnv": {"GOOGLE_APPLICATION_CREDENTIALS": "/workspaces/.secrets/gcp-sa-key.json"}`.
- [~] Update Planning Document (in progress)
	- 1. Edit the plan and insert 'Phase 0: Environment setup'. 2. Detail the `.secrets` creation, `.gitignore` update, and devcontainer binding parameters.
- [ ] Section 1: Clarifying Assumptions
	- 1. Identify missing info (e.g., expected read/write ratio). 2. State devcontainer assumptions (using direct GCP cloud connection via injected API key instead of local emulators).
- [ ] Section 2: Key Capabilities
	- 1. Map Upload/Download to GCS. 2. Map Metadata to Firestore. 3. Map Compute to Cloud Run/Cloud Functions.
- [ ] Section 3: Non-functional Reqs
	- 1. Scalability (10M files). 2. Security (data at rest/transit encryption). 3. Reliability (GCS multi-region vs regional). 4. Operational (monitoring via Cloud Logging).
- [ ] Section 4: Storage Strategy
	- 1. Outline blob storage structure in GCS. 2. Design metadata schema in Firestore to support tagging and fast lookups.
- [ ] Section 4: Access & Signed URLs
	- 1. Detail IAM Service Account roles. 2. Explain how GCS V4 Signed URLs will handle 500MB uploads/downloads securely without compute bottlenecks.
- [ ] Section 4: Multi-tenancy
	- 1. Compare Logical (Tenant ID in Firestore and shared buckets) vs Physical (Bucket per tenant). 2. Select approach for the 2-hour scope.
- [ ] Section 5: System Decomposition
	- 1. Outline high-level APIs/Subsystems (Upload Service, Download/Auth Service, Metadata Search Service). 2. Define inputs/outputs.
- [ ] Section 6: Risks & Trade-offs
	- 1. Identify risks (Firestore index limits, Cloud Run cold starts, IAM limits). 2. Capture mitigation ideas.
- [ ] Final Review & Format
	- 1. Review the final formulated document against the 'Output expectations' in `plan.md`. 2. Ensure it is a structured outline focused on framing rather than exhaustive architecture.


Generated on: 2026-03-17
```
