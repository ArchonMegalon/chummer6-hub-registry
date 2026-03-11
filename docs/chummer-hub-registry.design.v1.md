# hub-registry design

- Mission: define the repo boundary and package plane.
- Seeded boundary:
  - `Chummer.Hub.Registry.Contracts` owns immutable DTOs and vocabulary for registry artifacts.
  - Content-specific services and storage stay in source repos until migrated.
- Current contract surface:
  - immutable artifact metadata and lifecycle state
  - publication drafts, submission, and moderation queue/decisions
  - install state, install-history records, and compatibility projections
  - runtime-bundle artifact issuance and per-head projections
- Non-goals in this slice:
  - service implementations
  - persistence adapters
  - HTTP endpoints
  - cross-repo package publication automation
  - AI gateway routing
  - Spider session routing
  - session relay orchestration
  - media rendering pipeline
