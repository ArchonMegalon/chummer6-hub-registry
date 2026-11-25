# Draft review binding

`HubPublicationDraftService` binds each new moderation case to a server-computed
SHA-256 digest of the normalized Registry draft payload. The versioned, ordered
JSON digest includes draft ID, owner, project kind/ID, ruleset, title, summary,
description, publisher and visibility. It excludes workflow timestamps and notes.
It describes Registry's stored draft payload; it does not attest to bytes in an
external project repository or provider.

An existing preferred ID is checked against its owner. Project identity cannot
be replaced through draft creation; use a separate draft ID. An identical create
or update preserves identity, approval and publication timestamps. Content changes
use the same edit guards for both routes, clear approval and publication state,
and require a new submission and decision. Pending reviews cannot be edited.
Changed creation requests return HTTP 409 when these guards reject them.

Approval requires the latest pending case to match the current stored payload.
Publication, including a published retry, requires that latest case to be approved
and its digest to match. The comparison and publication mutation run inside the
existing `RegistryStateStore.Mutate` transaction and draft lock. Existing durable
writer leasing, commit/rollback and uncertain-outcome handling remain in force.

Publisher changes belong in the draft edit/submission before review. Publication
cannot change the reviewed publisher or widen visibility. A draft reviewed without
a publisher retains campaign-shared visibility on publication.

The new persisted `reviewedContentDigest` is optional only for loading older state.
No digest is backfilled from a mutable draft. Old pending cases cannot be approved,
and old approvals cannot authorize publication or a publication retry. Resubmit and
review a fresh case to establish evidence. Historical cases remain in the trail.
An older binary's strict snapshot reader rejects the new field; preserve a matching
pre-upgrade snapshot if rolling back the runtime. No live state was migrated here.

The focused synthetic verifier is:

```sh
dotnet run --project Chummer.Run.Registry.Verify/Chummer.Run.Registry.Verify.csproj -- --draft-review-binding
```

It is also included in the ordinary Registry verifier. Coverage includes owner and
project replacement rejection, identical approved and published retries, content
invalidation on both write routes, validated publication, missing legacy evidence,
restart persistence, failed-commit rollback and a competing replacement/publication.
The existing `--audit-registry-durability` verifier checks the shared persistence path.
