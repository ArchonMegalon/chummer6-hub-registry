# Release Build Handoff

Generated: 2026-07-08T15:59:34Z

- Stage dir: `/docker/chummercomplete/chummer-presentation/Chummer.Portal/downloads`
- Channel: `public_stable`
- Version: `run-20260704-170602`
- Artifact count: `2`
- Handoff only: `True`
- Handoff scope: `staged_nightly`
- Stage proof complete: `False`
- Stable release unchanged: `True`
- Separate publish lane required: `True`

## Artifacts

- `avalonia-linux-x64-installer` -> `chummer-avalonia-linux-x64-installer.deb` (linux / linux-x64)
- `avalonia-win-x64-installer` -> `chummer-avalonia-win-x64-installer.exe` (windows / win-x64)

## Startup Smoke

- `avalonia:linux:linux-x64`: `pass`
- `avalonia:macos:osx-arm64`: `pass`
- `avalonia:windows:win-x64`: `pass`

## Windows Exit Gate Refresh

- Status: `passed`
- JSON: `/docker/chummercomplete/chummer-presentation/Chummer.Portal/downloads/UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json`
- Script: `/docker/chummercomplete/chummer6-ui/scripts/materialize-windows-desktop-exit-gate.sh`
- Blocking mode: `none`
- Summary: Windows desktop exit gate passed.

## Windows Visual Proof Handoff

- Status: `needs_review`
- JSON: `/docker/chummercomplete/chummer-presentation/Chummer.Portal/downloads/WINDOWS_INSTALLER_VISUAL_PROOF_HANDOFF.generated.json`
- Markdown: `/docker/chummercomplete/chummer-presentation/Chummer.Portal/downloads/WINDOWS_INSTALLER_VISUAL_PROOF_HANDOFF.generated.md`
- Visual proof receipt target: `/docker/chummercomplete/chummer-presentation/Chummer.Portal/downloads/WINDOWS_INSTALLER_VISUAL_PROOF.generated.json`
- Summary: Windows desktop exit gate passed.
- Artifact intake required: `True`
- Preferred drop root: `/docker/chummercomplete/chummer-presentation/Chummer.Portal/downloads`
- Preferred receipt path: `/docker/chummercomplete/chummer-presentation/Chummer.Portal/downloads/WINDOWS_INSTALLER_VISUAL_PROOF.generated.json`
- Preferred screenshot dir: `/docker/chummercomplete/chummer-presentation/Chummer.Portal/downloads/windows-installer-visual-proof`
- Post-copy verify command: `CHUMMER_WINDOWS_RELEASE_CHANNEL_PATH="/docker/chummercomplete/chummer-presentation/Chummer.Portal/downloads/RELEASE_CHANNEL.generated.json" CHUMMER_WINDOWS_LOCAL_DESKTOP_FILES_ROOT="/docker/chummercomplete/chummer-presentation/Chummer.Portal/downloads/files" CHUMMER_WINDOWS_INSTALLER_VISUAL_PROOF_PATH="/docker/chummercomplete/chummer-presentation/Chummer.Portal/downloads/WINDOWS_INSTALLER_VISUAL_PROOF.generated.json" bash /docker/chummercomplete/chummer6-ui/scripts/materialize-windows-desktop-exit-gate.sh`

## Remaining Blockers

- Windows visual-proof handoff is not ready; inspect the staged handoff packet before asking a Windows operator to continue.

## Next Actions

- Inspect the Windows visual-proof handoff packet and fix the staged shelf mismatch before the nightly handoff continues: /docker/chummercomplete/chummer-presentation/Chummer.Portal/downloads/WINDOWS_INSTALLER_VISUAL_PROOF_HANDOFF.generated.json
- Keep the live downloads shelf and stable channel unchanged while this staged nightly handoff is still incomplete.
