# Primary-route and fallback-route registry truth

Date: 2026-04-11
Audience: `chummer6-hub-registry`
Status: injected fleet feedback

## Summary

Registry truth needs to support the flagship desktop promise more directly.
The client and the release shelf should be able to answer which route is primary, which route is fallback, and whether the current route is actually flagship-grade.

## Required changes

* Publish explicit release metadata for:
  * primary desktop head
  * fallback desktop head
  * platform promotion state
  * parity posture
  * rollback/revoke posture
* Ensure registry truth can answer:
  * which head is recommended for this platform
  * whether that head is flagship or fallback
  * whether parity is gold, preview, or bounded
  * why this install is on this channel and route
* Remove hand-wavy route messaging from downstream shelves by making the registry answer authoritative.
