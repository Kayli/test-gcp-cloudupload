# TODO List - Document Storage Planning

- [x] Secure API Key
  - 1. Create `.secrets/` folder in workspace root. 2. Move `<id>.json` to `.secrets/gcp-sa-key.json`. 3. Add `/.secrets/` to `.gitignore`. 4. Run `git status` to verify the key is ignored.
- [x] Configure Devcontainer Auth
  - 1. Edit `.devcontainer/devcontainer.json`. 2. Add mount: `"source=${localWorkspaceFolder}/.secrets,target=/workspaces/.secrets,type=bind"`. 3. Add `"containerEnv": {"GOOGLE_APPLICATION_CREDENTIALS": "/workspaces/.secrets/gcp-sa-key.json"}`.
- [~] Update Planning Document (in progress)
  - 1. Edit `untitled:plan-gcpDocumentStorage.prompt.md`. 2. Insert 'Phase 0: Environment setup'. 3. Detail the `.secrets` creation, `.gitignore` update, and devcontainer binding parameters so candidates complete this before architecture planning.
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
