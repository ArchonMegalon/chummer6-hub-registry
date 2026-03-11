# Hub registry implementation scope

## Mission

`chummer6-hub-registry` owns immutable artifact catalog, publication workflow, moderation state, installs, reviews, compatibility, and runtime-bundle head metadata.

## Owns

* immutable artifact metadata
* publication draft and publish/archive state
* moderation state and review trails
* install state and install history
* compatibility projections
* runtime-bundle head metadata
* registry contract canon

## Must not own

* AI gateway routing
* Spider/session relay
* media rendering
* play/client implementation
* canonical rules math

## Current focus

* extract registry contracts and catalog lifecycle out of `chummer6-hub`
* grow from contract seed to real registry domain service
* become the authoritative home for reusable published artifacts, installs, reviews, and compatibility

## Milestone spine

* H0 contract canon
* H1 artifact domain
* H2 publication drafts
* H3 install/compatibility engine
* H4 search/discovery/reviews
* H5 style/template publication
* H6 federation/org channels
* H7 hardening
* H8 finished registry

## Worker rule

If the problem is about published artifacts, installs, compatibility, reviews, or moderation state, it belongs here.
If it is about relay, play shells, or rendering, it does not.


## External integration note

`chummer6-hub-registry` may reference reusable external-facing help, preview, template, and style artifacts only when they have been promoted into registry truth.

It must not:

* run provider adapters
* own approval bridges
* own docs/help vendor execution
* own render execution

