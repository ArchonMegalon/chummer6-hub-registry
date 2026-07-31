# Desktop Downloads Staging

This directory is a compatibility staging area for the desktop download bundle.
Registry-owned release truth should be materialized here as `RELEASE_CHANNEL.generated.json` plus the compatibility `releases.json` when Hub needs a file-backed `/downloads` surface.

Expected contents:

- `RELEASE_CHANNEL.generated.json`
- `releases.json`
- `files/`
- desktop artifacts under `files/` (for example `chummer-avalonia-win-x64-installer.exe`, `chummer-avalonia-win-x64.exe`, and `chummer-blazor-desktop-linux-x64.tar.gz`)

Hub prefers `RELEASE_CHANNEL.generated.json` as the canonical registry-backed projection, serves `/downloads/releases.json` as the compatibility manifest, and resolves `/downloads/files/<artifact>` from the same root.

Published portal builds do not ship the checked-in `Chummer.Portal/downloads`
snapshot. This mounted directory is the deploy-time projection target for
registry-owned desktop release truth.

Populate this directory from the `desktop-download-bundle` produced by the
self-hosted release path, or use:

```bash
bash scripts/runbook.sh downloads-sync
```

For a compatibility repair after the run-services layout-v1 shelf is active,
do not use this directory's manifests as the source and do not run the legacy
release materializer. From `chummer.run-services`, first audit and then apply the
generation-bound mirror transaction:

```bash
python3 scripts/sync_active_release_compatibility_mirror.py
python3 scripts/sync_active_release_compatibility_mirror.py \
  --apply \
  --receipt /tmp/chummer-hub-release-compatibility-mirror-sync.json
```

The sync resolves and validates `current.json`, copies only the active immutable
generation's managed release entries, preserves unrelated registry receipts, rolls
back the managed entries on a pre-commit failure, and refuses targets carrying
layout-v1 or server-writer authority metadata.

If `CHUMMER_PORTAL_DOWNLOADS_DEPLOY_DIR` is configured, the local release
path can publish this bundle automatically.
