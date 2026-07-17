# What Is Still Below Gold

Launch truth observed: 2026-07-13T06:51:31Z

This document is generated from the current release channel, the authoritative whole-product flagship readiness gate, and mandatory release evidence gates. Do not edit it independently of those sources.

## Current whole-product posture

The current release is **not flagship-product-ready**. Preview support is real, but it is not a public-stable or gold-supported launch claim.

- Channel: `preview`
- Version: `run-20260712-174412`
- Rollout: `promoted_preview`
- Supportability: `preview_supported`
- Authoritative verdict: `NOT_FLAGSHIP_PRODUCT_READY`

### Launch blockers

- release channel channel is preview, not a flagship stable lane
- release channel supportability is not gold_supported
- release channel rollout is promoted_preview, not public_stable
- Windows installer visual audit source digest does not match promoted installer
- windows installer visual audit source still targets 80655fd79a096cd7714910d7b38f7741eea01f82ada96dc6a2a097951997d91a instead of promoted digest d0857d0a6e5c958f34117051669373444b785f683e701c3e0ae428abef36e8ca: /docker/chummercomplete/chummer.run-services/Chummer.Portal/downloads/visual-audit/windows-installer/WINDOWS_INSTALLER_VISUAL_AUDIT.source.json
- windows installer gold proof artifact is still missing: /docker/chummercomplete/chummer.run-services/.state/incoming_windows_installer_gold_proof/windows-installer-gold-proof-d0857d0a6e5c.zip
- flagship readiness coverage gap remains: desktop_client
- container_vulnerability_audit:not_available
- provenance:fail
- operator_proof: operator proof is missing
- proof:user_journey_tester_audit: user_journey_tester_audit is not currently passing and fresh
- release_truth:public_edge_postdeploy_gate: public_edge_postdeploy_gate is not passing for public-stable release truth

## Gold-claim boundary

Do not describe the current lane as `public_stable`, `gold_supported`, `GOLD_READY`, or launch-ready unless the registry channel, the flagship readiness gate, and the public release snapshot all agree on the same current channel and version.

Flagship parity-family evidence remains useful, but it cannot override a whole-product launch blocker or promote a preview channel.

## Authoritative sources

- Release channel: `/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json`
- Flagship readiness gate: `/docker/chummercomplete/chummer.run-services/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS_GATE.generated.json`
- Supply-chain release gate: `/docker/chummercomplete/.codex-studio/published/SUPPLY_CHAIN_RELEASE_GATE.generated.json`
- Public-edge observability gate: `/docker/chummercomplete/chummer.run-services/.codex-studio/published/PUBLIC_EDGE_OBSERVABILITY_RELEASE_GATE.generated.json`
- Release blockers projection: `/docker/chummercomplete/RELEASE_BLOCKERS.generated.json`
- Read-only snapshot audit: `/docker/chummercomplete/.codex-studio/published/PUBLIC_RELEASE_SNAPSHOT_READONLY_AUDIT.generated.json`
