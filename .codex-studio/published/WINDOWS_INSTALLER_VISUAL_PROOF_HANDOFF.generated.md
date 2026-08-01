# Windows Visual Proof Handoff

Generated: 2026-08-01T12:31:14Z

- Status: `ready_for_windows_host`
- Gate summary: Windows desktop exit gate failed: Windows installer visual proof is missing; capture progress and completion screenshots on a Windows host.
- Only blocker is visual proof: `True`
- Channel: `preview`
- Version: `run-20260801-031406`
- Shelf root: `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate`
- Handoff only: `True`
- Stable release unchanged: `True`
- Separate publish lane required: `True`

## Installer

- Artifact: `avalonia-win-x64-installer`
- File: `chummer-avalonia-win-x64-installer.exe`
- URL: `https://chummer.run/downloads/files/chummer-avalonia-win-x64-installer.exe`
- SHA-256: `sha256:39a1fcc3533f82a42169d4453abed67a24dd6ce08d77914224b83dfa71bbf74f`
- Payload: `chummer-avalonia-win-x64-payload.zip`
- Payload URL: `https://chummer.run/downloads/files/chummer-avalonia-win-x64-payload.zip`

### Local installer bytes found

- `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/files/chummer-avalonia-win-x64-installer.exe`

### Local payload bytes found

- `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/files/chummer-avalonia-win-x64-payload.zip`

## Startup smoke already present

- Status: `pass`
- Version: `run-20260801-031406`
- Release version: `run-20260801-031406`
- Receipt: `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json`
- Host class: `local-win-x64`
- Matches release candidate: `True`
- Matches installer file: `True`
- Matches installer digest: `True`
- Progress log: `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/startup-smoke/windows-installer-progress-avalonia-win-x64.log`
- Progress log present: `True`

## Current visual proof state

- Exists: `False`
- Status: ``
- Version: ``
- Digest: ``
- Matches release candidate: `False`
- Matches installer digest: `False`
- Stale: `False`

## Windows operator commands

- Stage root: `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate`
- Stage-local PowerShell: `powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\capture-windows-installer-visual-proof.ps1 -ReleaseChannelPath "/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/RELEASE_CHANNEL.generated.json" -OutputPath "/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/WINDOWS_INSTALLER_VISUAL_PROOF.generated.json"`
- Windows-local stage template: `powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\capture-windows-installer-visual-proof.ps1 -ReleaseChannelPath "<windows-stage>\RELEASE_CHANNEL.generated.json" -OutputPath "<windows-stage>\WINDOWS_INSTALLER_VISUAL_PROOF.generated.json"`
- Linux exit gate after copy-back: `CHUMMER_WINDOWS_RELEASE_CHANNEL_PATH="/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/RELEASE_CHANNEL.generated.json" CHUMMER_WINDOWS_LOCAL_DESKTOP_FILES_ROOT="/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/files" CHUMMER_WINDOWS_INSTALLER_VISUAL_PROOF_PATH="/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/WINDOWS_INSTALLER_VISUAL_PROOF.generated.json" bash /docker/chummercomplete/.release-work/linux-native-gate-run-20260801-031406.oiM9Cw/chummer-presentation/scripts/materialize-windows-desktop-exit-gate.sh`
- Copy-back note: If the Windows host cannot access the staged Linux path directly, copy the whole stage directory to the Windows host, run the template command against that Windows-local stage, then copy the receipt and screenshots back to these stage-relative paths before rerunning the Linux exit gate.

### Required copy-back paths

- `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/WINDOWS_INSTALLER_VISUAL_PROOF.generated.json`
- `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/windows-installer-visual-proof/windows-installer-progress.png`
- `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/windows-installer-visual-proof/windows-installer-completion.png`

## Artifact intake

- External artifact required: `True`
- Preferred drop root: `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate`
- Preferred receipt path: `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/WINDOWS_INSTALLER_VISUAL_PROOF.generated.json`
- Preferred screenshot directory: `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/windows-installer-visual-proof`
- Discover receipt command: `python3 ~/.codex/skills/ea-artifact-intake/scripts/artifact_intake.py discover --pattern 'WINDOWS_INSTALLER_VISUAL_PROOF.generated.json' --root "/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate" --root "/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/windows-installer-visual-proof" --root "/tmp" --root "/home/tibor/Downloads" --root "/home/tibor/pCloud Drive/EA"`
- Discover screenshot command: `python3 ~/.codex/skills/ea-artifact-intake/scripts/artifact_intake.py discover --pattern 'windows-installer-*.png' --root "/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate" --root "/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/windows-installer-visual-proof" --root "/tmp" --root "/home/tibor/Downloads" --root "/home/tibor/pCloud Drive/EA"`
- Post-copy verify command: `CHUMMER_WINDOWS_RELEASE_CHANNEL_PATH="/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/RELEASE_CHANNEL.generated.json" CHUMMER_WINDOWS_LOCAL_DESKTOP_FILES_ROOT="/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/files" CHUMMER_WINDOWS_INSTALLER_VISUAL_PROOF_PATH="/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/WINDOWS_INSTALLER_VISUAL_PROOF.generated.json" bash /docker/chummercomplete/.release-work/linux-native-gate-run-20260801-031406.oiM9Cw/chummer-presentation/scripts/materialize-windows-desktop-exit-gate.sh`
- Request summary: Capture the staged Windows installer progress and completion screenshots on a real Windows host, copy the generated receipt and screenshots back to the exact staged paths, then rerun the Linux Windows exit gate against the same stage.

### Accepted file patterns

- `WINDOWS_INSTALLER_VISUAL_PROOF.generated.json`
- `windows-installer-progress.png`
- `windows-installer-completion.png`

### Required intake paths

- `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/WINDOWS_INSTALLER_VISUAL_PROOF.generated.json`
- `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/windows-installer-visual-proof/windows-installer-progress.png`
- `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/windows-installer-visual-proof/windows-installer-completion.png`

## Release-Truth Bundle Intake

- Intake request: `/docker/chummercomplete/.release-work/linux-native-gate-run-20260801-031406.oiM9Cw/chummer.run-services/.codex-studio/published/WINDOWS_INSTALLER_VISUAL_AUDIT_INTAKE_REQUEST.generated.json`
- Intake status: `external_artifact_required`
- Promoted installer SHA-256: `13477e00b148b41b84f59ed3d5e25bb38267f530193aa80b7eb7649ed9416d74`
- Preferred zip name: `windows-installer-gold-proof-13477e00b148.zip`
- Preferred drop folder: `/docker/chummercomplete/chummer.run-services/.state/incoming_windows_installer_gold_proof`
- Preferred drop path: `/docker/chummercomplete/chummer.run-services/.state/incoming_windows_installer_gold_proof/windows-installer-gold-proof-13477e00b148.zip`
- Discover command: `python3 ~/.codex/skills/ea-artifact-intake/scripts/artifact_intake.py discover --pattern '*windows-installer-gold-proof*.zip' --root "/docker/chummercomplete/chummer.run-services/.state/incoming_windows_installer_gold_proof" --root "/tmp" --root "~/Downloads" --root "~/pCloud Drive/EA"`
- Import command: `python3 scripts/import_windows_installer_gold_proof_artifact.py /docker/chummercomplete/chummer.run-services/.state/incoming_windows_installer_gold_proof/windows-installer-gold-proof-13477e00b148.zip --intake-request /docker/chummercomplete/chummer.run-services/.codex-studio/published/WINDOWS_INSTALLER_VISUAL_AUDIT_INTAKE_REQUEST.generated.json --verify`
- Auto-import watch command: `python3 scripts/auto_import_windows_installer_gold_proof.py --intake-request /docker/chummercomplete/chummer.run-services/.codex-studio/published/WINDOWS_INSTALLER_VISUAL_AUDIT_INTAKE_REQUEST.generated.json --wait-seconds 900 --poll-seconds 10 --refresh-intake-request`
- Post-import verify command: `python3 scripts/verify_windows_installer_visual_audit.py --expected-verifier-sha256 f4eca8954d906b648ca67fc7183c0c4740533d88ab32be1328815c682daf800f --output .codex-studio/published/WINDOWS_INSTALLER_VISUAL_AUDIT.generated.json`
- Post-import verify note: The --verify import reruns the full intake-request post-import gate chain, not just the first verifier.
- Startup receipt bundle required: `False`
- Summary: Provide the native Windows gold proof bundle for the promoted installer. Native Windows startup already matches the promoted digest; the remaining gap is digest-bound visual proof for install-progress and completion.

### Windows-host bundle commands

- `${REPO_ROOT}\scripts\capture_windows_installer_gold_proof.ps1 -InstallerPath ${REPO_ROOT}\Chummer.Portal\downloads\files\chummer-avalonia-win-x64-installer.exe -DownloadsRoot ${REPO_ROOT}\Chummer.Portal\downloads -LaunchInstaller -CaptureVisualAudit -ScaledDpiScale 1.5 -VisualClippingStatus pass -VisualReadabilityStatus pass`
- `Compress-Archive -Path ${REPO_ROOT}\Chummer.Portal\downloads\visual-audit\windows-installer\* -DestinationPath windows-installer-gold-proof-13477e00b148.zip -Force`

### Windows-host prep notes

- Copy the repository checkout or at least Chummer.Portal/downloads/files, Chummer.Portal/downloads/RELEASE_CHANNEL.generated.json, and scripts to the Windows host.
- Do not mark screenshots pass until a human has inspected clipping/readability.
- The published startup-smoke receipt already matches the promoted installer digest, so you may either zip only the visual-audit/windows-installer folder or copy it extracted to the preferred extracted visual-proof directory.

## Required screenshots

- `progress`: `windows-installer-progress.png` -> `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/windows-installer-visual-proof/windows-installer-progress.png`
- `completion`: `windows-installer-completion.png` -> `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/windows-installer-visual-proof/windows-installer-completion.png`

## Gate reasons

- Windows installer visual proof is missing; capture progress and completion screenshots on a Windows host.

## Blockers

- none

## Next actions

- If you are clearing the live release-truth blocker, run the promoted-digest Windows capture command `${REPO_ROOT}\scripts\capture_windows_installer_gold_proof.ps1 -InstallerPath ${REPO_ROOT}\Chummer.Portal\downloads\files\chummer-avalonia-win-x64-installer.exe -DownloadsRoot ${REPO_ROOT}\Chummer.Portal\downloads -LaunchInstaller -CaptureVisualAudit -ScaledDpiScale 1.5 -VisualClippingStatus pass -VisualReadabilityStatus pass`.
- Package the promoted-digest Windows gold proof bundle as `windows-installer-gold-proof-13477e00b148.zip` with `Compress-Archive -Path ${REPO_ROOT}\Chummer.Portal\downloads\visual-audit\windows-installer\* -DestinationPath windows-installer-gold-proof-13477e00b148.zip -Force`.
- Drop the digest-bound bundle at `/docker/chummercomplete/chummer.run-services/.state/incoming_windows_installer_gold_proof/windows-installer-gold-proof-13477e00b148.zip` and import it with `python3 scripts/import_windows_installer_gold_proof_artifact.py /docker/chummercomplete/chummer.run-services/.state/incoming_windows_installer_gold_proof/windows-installer-gold-proof-13477e00b148.zip --intake-request /docker/chummercomplete/chummer.run-services/.codex-studio/published/WINDOWS_INSTALLER_VISUAL_AUDIT_INTAKE_REQUEST.generated.json --verify`. Or watch for it with `python3 scripts/auto_import_windows_installer_gold_proof.py --intake-request /docker/chummercomplete/chummer.run-services/.codex-studio/published/WINDOWS_INSTALLER_VISUAL_AUDIT_INTAKE_REQUEST.generated.json --wait-seconds 900 --poll-seconds 10 --refresh-intake-request`.
- On a real Windows host, open the repo checkout that contains the capture script and run `powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\capture-windows-installer-visual-proof.ps1 -ReleaseChannelPath "/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/RELEASE_CHANNEL.generated.json" -OutputPath "/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/WINDOWS_INSTALLER_VISUAL_PROOF.generated.json"`.
- If the Windows host cannot access the staged Linux path directly, copy the whole stage directory to the Windows host, run `powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\capture-windows-installer-visual-proof.ps1 -ReleaseChannelPath "<windows-stage>\RELEASE_CHANNEL.generated.json" -OutputPath "<windows-stage>\WINDOWS_INSTALLER_VISUAL_PROOF.generated.json"`, then copy the generated receipt and screenshots back.
- Confirm `windows-installer-progress.png` and `windows-installer-completion.png` are written under `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/windows-installer-visual-proof`.
- Confirm `WINDOWS_INSTALLER_VISUAL_PROOF.generated.json` is written under `/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate`.
- Rerun the Windows exit gate against the same shelf: `CHUMMER_WINDOWS_RELEASE_CHANNEL_PATH="/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/RELEASE_CHANNEL.generated.json" CHUMMER_WINDOWS_LOCAL_DESKTOP_FILES_ROOT="/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/files" CHUMMER_WINDOWS_INSTALLER_VISUAL_PROOF_PATH="/docker/chummercomplete/.release-work/provenance-corrective-stage6-run-20260801-031406.j6X69q/candidate/WINDOWS_INSTALLER_VISUAL_PROOF.generated.json" bash /docker/chummercomplete/.release-work/linux-native-gate-run-20260801-031406.oiM9Cw/chummer-presentation/scripts/materialize-windows-desktop-exit-gate.sh`.
- This packet is handoff-only for the staged nightly bytes. It does not publish the live downloads shelf or change the stable channel.
