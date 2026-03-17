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

### 2. Key system capabilities
- Core functional components the system must support mapped to GCP components (e.g., Cloud Storage, Firestore/Cloud SQL, Cloud Run)

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
