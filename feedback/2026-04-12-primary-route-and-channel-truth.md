# Primary Route And Channel Truth

Generated: 2026-04-12T10:55:00Z
Priority: high

## Why this exists

Registry truth needs to make primary-vs-fallback desktop posture explicit enough that the desktop client, Hub, and public shelf cannot drift into ambiguity.

## Required next work

- Publish explicit channel metadata for:
  - primary head
  - fallback head
  - platform promotion state
  - update eligibility
  - rollback and revoke state
- Make registry truth answer, directly:
  - why this client is on this channel
  - why this head is primary or fallback
  - whether installer-first or portable/manual posture is recommended
- Feed the same truth into Hub and desktop surfaces so the public route and in-app route never disagree.

## Governing design sources

- `/docker/chummercomplete/chummer-design/products/chummer/PRIMARY_ROUTE_REGISTRY.yaml`
- `/docker/chummercomplete/chummer-design/products/chummer/FLAGSHIP_RELEASE_ACCEPTANCE.yaml`
- `/docker/chummercomplete/chummer-design/products/chummer/PUBLIC_RELEASE_EXPERIENCE.yaml`
