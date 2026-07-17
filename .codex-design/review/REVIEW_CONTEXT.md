
# Review guidelines
- Flag mutable artifact version updates as P1.
- Flag media or AI orchestration logic inside hub-registry as P1.
- Flag missing retention or compatibility coverage as P1.
- Flag registry contract changes that leave publication or moderation ownership ambiguous as P1.
- Flag relay, Spider, or session-approval logic moving into hub-registry as P1.
- For governed spatial artifacts, require Registry-owned publication leases, renewal, revocation, public refs, cache-withdrawal posture, and public-ref tombstones to consume only immutable provider-redacted media-factory manifests.
- Reject provider selection/execution, provider jobs, quota mutation, private execution receipts, campaign/private-audience truth, or PropertyQuarry lifecycle action inside hub-registry.
- Reject publication, renewal, or `ready` projection from compose-only success, prose, provider names, environment variables, historical handoffs, or missing/stale/revoked/wrong-family/wrong-environment capability evidence.
- Require publication expiry or takedown to revoke serving, purge caches on the numeric SLA, preserve only TTL-bound provider-redacted history, and defer PropertyQuarry authority to its recorded external owners without acting for them.
