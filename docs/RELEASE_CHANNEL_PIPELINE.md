# Release channel pipeline

Purpose: define the registry-owned truth for desktop release channels, installer/update metadata, and the compatibility projection that Hub serves at `/downloads/releases.json`.

## Canonical ownership

* `chummer6-core` emits runtime-bundle facts and fingerprints.
* `chummer6-ui` emits desktop bundles and installer-ready artifacts.
* `fleet` orchestrates the release wave and asks registry tooling to materialize release truth.
* `chummer6-hub-registry` owns the promoted release-channel record, installer/update metadata, compatibility state, and runtime-bundle references.
* `chummer6-hub` consumes the registry projection and renders the public downloads/install surface.

## Canonical artifacts

Registry-owned generated artifacts:

* `.codex-studio/published/RELEASE_CHANNEL.generated.json`
* compatibility projection `releases.json` when a legacy `/downloads/releases.json` surface still needs it

`RELEASE_CHANNEL.generated.json` is the canonical projection. `releases.json` is a compatibility export for existing Hub/download consumers.

## Shape

Minimum canonical payload:

```json
{
  "schemaVersion": 1,
  "product": "chummer6",
  "channelId": "preview",
  "version": "2026.03.23-preview.1",
  "publishedAt": "2026-03-23T18:00:00Z",
  "status": "published",
  "artifactSource": "ui_desktop_bundle",
  "artifacts": [
    {
      "artifactId": "avalonia-win-x64-installer",
      "head": "avalonia",
      "platform": "windows",
      "arch": "x64",
      "kind": "installer",
      "fileName": "chummer-avalonia-win-x64-installer.exe",
      "downloadUrl": "/downloads/files/chummer-avalonia-win-x64-installer.exe",
      "sha256": "…",
      "sizeBytes": 123456789,
      "embeddedRuntimeBundleHeadId": "runtime-head-preview-sr5"
    }
  ],
  "runtimeBundleHeads": [
    {
      "headId": "runtime-head-preview-sr5",
      "headKind": "session",
      "rulesetId": "sr5",
      "sourceBundleVersion": "2026.03.23-core.1",
      "projectionFingerprint": "sha256:…"
    }
  ]
}
```

## Operational rule

Hub, guide generators, and any public download UX must consume the registry-owned release-channel artifact or its explicit compatibility projection.

They must not mint their own release truth by scanning files and inventing a new manifest shape locally.
