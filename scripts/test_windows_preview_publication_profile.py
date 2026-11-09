"""Policy-only tests with tiny synthetic bytes; no native release receipts are produced."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_materialize_public_release_channel import MODULE as M, VERIFY_MODULE as V


def make_candidate(tmp_path):
    root = tmp_path / 'candidate'
    files = root / 'files'
    smoke = root / 'startup-smoke'
    files.mkdir(parents=True)
    smoke.mkdir()
    name = 'chummer-avalonia-win-x64-installer.exe'
    data = b'synthetic-policy-test-only'
    (files / name).write_bytes(data)
    now = M.utc_now().isoformat().replace('+00:00', 'Z')
    receipt = {
        'status': 'pass', 'executionEnvironment': M.WINDOWS_NATIVE_EXECUTION_ENVIRONMENT,
        'verificationScope': M.WINDOWS_NATIVE_VERIFICATION_SCOPE,
        'nativeHostEvidence': {'contractName': M.WINDOWS_NATIVE_HOST_EVIDENCE_CONTRACT,
            'status': 'verified', 'isNativeWindows': True, 'hostPlatform': 'windows',
            'hostKernel': 'synthetic-Windows-kernel', 'runner': 'synthetic-native-test',
            'evidenceSource': 'synthetic-policy-unit-test'}, 'headId': 'avalonia', 'platform': 'windows',
        'rid': 'win-x64', 'arch': 'x64', 'hostClass': 'local-win-x64',
        'operatingSystem': 'Windows 11', 'readyCheckpoint': 'pre_ui_event_loop',
        'artifactId': 'avalonia-win-x64-installer', 'artifactFileName': name,
        'artifactRelativePath': f'files/{name}',
        'artifactDigest': 'sha256:' + hashlib.sha256(data).hexdigest(),
        'channel': 'preview', 'channelId': 'preview',
        'version': 'synthetic-policy-test', 'releaseVersion': 'synthetic-policy-test',
        'completedAtUtc': now, 'installerMode': 'bundled',
    }
    receipt_path = smoke / 'startup-smoke-avalonia-win-x64.receipt.json'
    receipt_path.write_text(json.dumps(receipt))
    proof = {'status': 'review_required', 'generatedAt': now,
             'baseUrl': 'https://chummer.run', 'journeysPassed': [],
             'proofRoutes': list(V.WINDOWS_PREVIEW_ROUTES)}
    proof_path = tmp_path / 'synthetic-proof.json'
    proof_path.write_text(json.dumps(proof))
    args = M.parse_args([
        '--publication-profile', V.WINDOWS_PREVIEW_PROFILE,
        '--registry-commit', '0' * 40, '--downloads-dir', str(files),
        '--startup-smoke-dir', str(smoke), '--proof', str(proof_path),
        '--channel', 'preview', '--version', 'synthetic-policy-test',
        '--published-at', now, '--output', str(root / 'RELEASE_CHANNEL.generated.json'),
        '--compat-output', str(root / 'releases.json'),
    ])
    return args, root, receipt_path


def write_candidate(args):
    canonical = M.canonical_payload(args)
    compat = M.compatibility_payload(canonical)
    compat['publicTrustMetrics'] = M.expected_public_trust_metrics(compat)
    compat['registryBoundaryCoverage'] = M.expected_registry_boundary_coverage(compat)
    M.write_json(args.output, canonical)
    M.write_json(args.compat_output, compat)
    return canonical, compat


def test_default_policy_stays_broad():
    assert M.materialization_required_platforms([], 'windows') == ['linux', 'windows']
    with pytest.raises(ValueError, match='missing required baseline'):
        M.normalize_release_proof_payload({'status': 'review_required', 'journeysPassed': []}, source='test')
    with pytest.raises(ValueError, match='requires explicit'):
        M.materialization_required_platforms([], 'linux,windows', platform_scope='windows_only', channel='preview')


def test_windows_preview_round_trip_and_real_verifier_cli(tmp_path):
    args, root, _ = make_candidate(tmp_path)
    canonical, compat = write_candidate(args)
    for payload in (canonical, compat):
        assert payload['desktopTupleCoverage']['complete'] is True
        assert payload['desktopTupleCoverage']['requiredDesktopPlatforms'] == ['windows']
        assert payload['publicationScope']['linux'] == 'outside_profile'
        assert payload['publicationScope']['hubJourneys'] == 'outside_profile'
        assert payload['releaseProof']['journeysPassed'] == []
        assert payload['releaseProof']['uiLocalizationReleaseGate'] is None
        assert payload['supportabilityState'] == 'review_required'
        V.verify_release_truth(payload, 'synthetic test')
        V.verify_artifacts(payload, 'synthetic test', require_complete_desktop_coverage=True)
        V.verify_local_download_files(payload, root, 'synthetic test')
    result = subprocess.run([sys.executable, str(Path(V.__file__)), '--publication-profile',
                             V.WINDOWS_PREVIEW_PROFILE, '--require-complete-desktop-coverage', str(root)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('mutation', ['missing_bytes', 'changed_bytes', 'same_size_wrong_bytes', 'missing_smoke', 'wrong_digest',
                                      'wrong_host', 'wrong_checkpoint', 'wrong_version', 'skipped', 'private_path', 'secret_file'])
def test_windows_preview_rejects_missing_mismatched_or_private_inputs(tmp_path, mutation):
    args, root, receipt_path = make_candidate(tmp_path)
    payload, _ = write_candidate(args)
    receipt = json.loads(receipt_path.read_text())
    binary = args.downloads_dir / 'chummer-avalonia-win-x64-installer.exe'
    if mutation == 'missing_bytes': binary.unlink()
    elif mutation == 'changed_bytes': binary.write_bytes(b'different-size')
    elif mutation == 'same_size_wrong_bytes': binary.write_bytes(b'x' * binary.stat().st_size)
    elif mutation == 'missing_smoke': receipt_path.unlink()
    elif mutation == 'secret_file': (root / 'files' / 'private-key.pem').write_text('test-only')
    else:
        key, value = {'wrong_digest': ('artifactDigest', 'sha256:' + 'f' * 64),
                      'wrong_host': ('hostClass', 'linux-x64'),
                      'wrong_checkpoint': ('readyCheckpoint', 'launched'),
                      'wrong_version': ('version', 'different-release'),
                      'skipped': ('status', 'skipped'),
                      'private_path': ('artifactPath', '/docker/private/installer.exe')}[mutation]
        receipt[key] = value
        receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(SystemExit):
        V.verify_local_download_files(payload, root, 'synthetic test')


@pytest.mark.parametrize('key,value', [('channel', 'stable'), ('supportabilityState', 'preview_supported'),
                                     ('publicationProfile', 'unknown'), ('message', 'All passed')])
def test_profile_cannot_widen_or_hide_disclosure(tmp_path, key, value):
    args, _, _ = make_candidate(tmp_path)
    payload, _ = write_candidate(args)
    payload[key] = value
    with pytest.raises(SystemExit): V.verify_release_truth(payload, 'synthetic test')


def test_materializer_requires_evidence_and_explicit_profile(tmp_path):
    args, root, receipt = make_candidate(tmp_path)
    payload, _ = write_candidate(args)
    args.manifest = args.output
    args.publication_profile = ''
    with pytest.raises(ValueError, match='explicit matching'): M.canonical_payload(args)
    args.publication_profile = V.WINDOWS_PREVIEW_PROFILE
    args.skip_startup_smoke_filter = True
    with pytest.raises(ValueError, match='without skip'): M.canonical_payload(args)
    args.skip_startup_smoke_filter = False
    receipt.unlink()
    with pytest.raises(ValueError, match='startup evidence'): M.canonical_payload(args)


def test_profile_preserves_access_and_rejects_revocation(tmp_path):
    args, _, _ = make_candidate(tmp_path)
    payload, _ = write_candidate(args)
    payload['artifacts'][0]['installAccessClass'] = 'account_required'
    M.write_json(args.output, payload)
    args.manifest = args.output
    projected = M.canonical_payload(args)
    assert projected['artifacts'][0]['installAccessClass'] == 'account_required'
    payload['artifacts'][0]['revoked'] = True
    M.write_json(args.output, payload)
    with pytest.raises(SystemExit, match='revoked'): M.canonical_payload(args)


def test_skip_environment_cannot_relax_profile_verifier(tmp_path):
    args, root, _ = make_candidate(tmp_path)
    write_candidate(args)
    result = subprocess.run([sys.executable, str(Path(V.__file__)), str(root)],
                            env={**os.environ, 'CHUMMER_VERIFY_SKIP_STARTUP_SMOKE_FILTER': 'true'},
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'does not permit skipped' in result.stderr


def test_profile_cannot_demote_stable_input_into_an_implicit_preview(tmp_path):
    args, _, _ = make_candidate(tmp_path)
    args.channel = 'stable'
    with pytest.raises(ValueError, match='explicit preview channel'):
        M.canonical_payload(args)


@pytest.mark.parametrize('mutation', ['missing_pair', 'mixed_profile', 'changed_access', 'changed_proof', 'unknown_profile'])
def test_exact_manifest_pair_is_required_even_for_file_target(tmp_path, mutation):
    args, root, _ = make_candidate(tmp_path)
    payload, compat = write_candidate(args)
    if mutation == 'missing_pair':
        args.compat_output.unlink()
    else:
        if mutation == 'mixed_profile': compat.pop('publicationProfile')
        elif mutation == 'unknown_profile': compat['publicationProfile'] = 'future_preview'
        elif mutation == 'changed_access': compat['downloads'][0]['installAccessClass'] = 'account_required'
        elif mutation == 'changed_proof': compat['releaseProof']['generatedAt'] = '2026-01-01T00:00:00Z'
        M.write_json(args.compat_output, compat)
    with pytest.raises(SystemExit):
        V.verify_local_download_files(payload, root, 'synthetic file target')


@pytest.mark.parametrize('field', ['projectionProfile', 'releaseProfile', 'projectionStage',
                                   'codeDeployCurrentShelfAuthority', 'codeDeploymentAuthority',
                                   'releaseUploadAuthority', 'channelPromotionAuthority'])
def test_profile_rejects_other_authority_modes(tmp_path, field):
    args, _, _ = make_candidate(tmp_path)
    payload, _ = write_candidate(args)
    payload[field] = 'synthetic-other-mode'
    with pytest.raises(SystemExit, match='mix publication modes'):
        V.verify_artifacts(payload, 'synthetic mixed modes')
    M.write_json(args.output, payload)
    args.manifest = args.output
    with pytest.raises(SystemExit, match='mix publication modes'):
        M.canonical_payload(args)


@pytest.mark.parametrize('mutation', ['wine', 'missing_native', 'stale', 'missing_time', 'wrong_os', 'alias_localization'])
def test_native_evidence_and_no_fake_broad_proof(tmp_path, mutation):
    args, root, receipt_path = make_candidate(tmp_path)
    payload, _ = write_candidate(args)
    receipt = json.loads(receipt_path.read_text())
    if mutation == 'wine': receipt['executionEnvironment'] = M.WINDOWS_WINE_COMPATIBILITY_EXECUTION_ENVIRONMENT
    elif mutation == 'missing_native': receipt.pop('nativeHostEvidence')
    elif mutation == 'stale': receipt['completedAtUtc'] = '2000-01-01T00:00:00Z'
    elif mutation == 'missing_time': receipt.pop('completedAtUtc')
    elif mutation == 'wrong_os': receipt['operatingSystem'] = 'Linux'
    elif mutation == 'alias_localization':
        payload['releaseProof']['ui_localization_release_gate'] = {'status': 'pass'}
        with pytest.raises(SystemExit): V.verify_release_truth(payload, 'synthetic proof')
        return
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(SystemExit):
        V.verify_local_startup_smoke_receipts(payload, root, 'synthetic evidence')


def test_profile_cannot_skip_receipts_at_direct_local_entry_point(tmp_path):
    args, root, _ = make_candidate(tmp_path)
    payload, _ = write_candidate(args)
    for key in ('skip_startup_smoke_filter', 'allow_skipped_startup_smoke'):
        with pytest.raises(SystemExit, match='does not permit skipped'):
            V.verify_local_startup_smoke_receipts(payload, root, 'synthetic bypass', **{key: True})
    payload['desktopTupleCoverage']['complete'] = False
    with pytest.raises(SystemExit): V.verify_artifacts(payload, 'synthetic incomplete')


@pytest.mark.parametrize('url', ['https:/downloads/files/chummer-avalonia-win-x64-installer.exe',
    '//chummer.run/downloads/files/chummer-avalonia-win-x64-installer.exe',
    'https://untrusted.example/downloads/files/chummer-avalonia-win-x64-installer.exe',
    '/downloads/files/chummer-avalonia-win-x64-payload.zip',
    '/downloads/g/another/files/chummer-avalonia-win-x64-installer.exe'])
def test_profile_rejects_noncanonical_or_wrong_artifact_urls(tmp_path, url):
    args, _, _ = make_candidate(tmp_path)
    payload, _ = write_candidate(args)
    payload['artifacts'][0]['downloadUrl'] = url
    with pytest.raises(SystemExit): V.verify_windows_preview_profile(payload, 'synthetic URL')


def test_profile_public_root_cannot_be_a_symlink(tmp_path):
    args, root, _ = make_candidate(tmp_path)
    payload, _ = write_candidate(args)
    alias = tmp_path / 'public-root-alias'
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(SystemExit, match='symlink'):
        V.verify_windows_preview_public_files(payload, alias, 'synthetic alias')


@pytest.mark.parametrize('field,value', [
    ('apiKey', 'synthetic-not-a-credential'),
    ('Authorization', 'Bearer synthetic-not-a-credential'),
    ('Cookie', 'session=synthetic-not-a-credential'),
    ('artifactPath', '/var/lib/private-build/candidate.exe'),
    ('aPi_KeY', 'synthetic-not-a-credential'),
    ('AUTHORIZATION', 'Bearer synthetic-not-a-credential'),
    ('set-cookie', 'session=synthetic-not-a-credential'),
    ('nativeHostEvidence', {'API-Key': 'synthetic-not-a-credential'}),
    ('nativeHostEvidence', {'headers': [{'cOoKiE': 'synthetic-not-a-credential'}]}),
    ('nativeHostEvidence', {'runner': '/srv/private-build/runner'}),
    ('nativeHostEvidence', {'runner': {'Authorization': 'synthetic-not-a-credential'}}),
    ('artifactPath', r'\\server\private-build\candidate.exe'),
    ('artifact_path', '/opt/private-build/candidate.exe'),
    ('debugContext', 'unreviewed-extension'),
])
def test_public_receipt_metadata_rejected_at_direct_and_cli_boundaries(tmp_path, field, value):
    args, root, receipt_path = make_candidate(tmp_path)
    payload, _ = write_candidate(args)
    receipt = json.loads(receipt_path.read_text())
    if field == 'nativeHostEvidence':
        receipt[field].update(value)
    else:
        receipt[field] = value
    receipt_path.write_text(json.dumps(receipt))
    original = receipt_path.read_bytes()
    for verify in (V.verify_local_startup_smoke_receipts, V.verify_local_download_files):
        with pytest.raises(SystemExit, match='Windows preview metadata'):
            verify(payload, root, 'synthetic private metadata')
    result = subprocess.run([sys.executable, str(Path(V.__file__)), '--publication-profile',
                             V.WINDOWS_PREVIEW_PROFILE, str(root)], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Windows preview metadata' in result.stderr
    assert 'synthetic-not-a-credential' not in result.stderr
    assert receipt_path.read_bytes() == original  # Reject; never silently redact or rewrite.


@pytest.mark.parametrize('metadata', [
    {'nested': [{'ＡＰＩ＿ＫＥＹ': 'synthetic'}]},
    {'nested': [{'proxy-Authorization': 'synthetic'}]},
    {'nested': [{'Set_Cookie': 'synthetic'}]},
    {'nested': [{'refresh.token': 'synthetic'}]},
    {'nested': [{'artifactPath': '/etc/private-build/candidate.exe'}]},
    {'nested': [{'artifactPath': '/Volumes/private-build/candidate.exe'}]},
    {'nested': [{'artifactPath': 'path:/var/lib/private-build/candidate.exe'}]},
    {'nested': [{'artifactPath': '%2Fvar%2Flib%2Fprivate-build%2Fcandidate.exe'}]},
    {'nested': [{'artifactPath': 'FILE:///var/lib/private-build/candidate.exe'}]},
    {'nested': [{'artifactPath': r'C:\private-build\candidate.exe'}]},
    {'nested': [{'artifactPath': '~/private-build/candidate.exe'}]},
    {'nested': [{'artifactPath': '/downloads/../private-build/candidate.exe'}]},
    {'nested': [{'url': 'https://synthetic-user:synthetic-password@chummer.run/downloads'}]},
    {'nested': [{'url': 'https://chummer.run/downloads?apiKey=synthetic'}]},
])
def test_public_metadata_filter_rejects_nested_fields_and_private_path_forms(metadata):
    with pytest.raises(SystemExit, match='Windows preview metadata'):
        V.verify_windows_preview_public_metadata(metadata, 'synthetic metadata')


@pytest.mark.parametrize('value', [
    '/downloads', '/downloads/files/chummer-avalonia-win-x64-installer.exe',
    '/downloads/g/synthetic-generation/files/chummer-avalonia-win-x64-payload.zip.json',
    '/downloads/install/avalonia-win-x64-installer/metadata',
    'https://chummer.run/downloads/g/synthetic-generation/files/chummer-avalonia-win-x64-installer.exe',
    'https://chummer.run', 'files/chummer-avalonia-win-x64-installer.exe',
    'startup-smoke/startup-smoke-avalonia-win-x64.receipt.json',
    'Independent startup verification for windows/win-x64.',
])
def test_public_metadata_filter_preserves_public_routes_and_relative_references(value):
    V.verify_windows_preview_public_metadata({'reference': value}, 'synthetic public metadata')


@pytest.mark.parametrize('snake_aliases', [False, True])
def test_public_bootstrap_receipt_and_sidecar_preserve_supported_fields(tmp_path, snake_aliases):
    args, root, receipt_path = make_candidate(tmp_path)
    payload_name = 'chummer-avalonia-win-x64-payload.zip'
    payload_bytes = b'synthetic-payload-policy-test-only'
    digest = hashlib.sha256(payload_bytes).hexdigest()
    receipt = json.loads(receipt_path.read_text())
    receipt.pop('installerMode')
    fields = [
        ('artifactInstallMode', 'artifact_install_mode', 'nsis_bootstrap_installer'),
        ('bootstrapPayloadAcquisitionMode', 'bootstrap_payload_acquisition_mode', 'download'),
        ('bootstrapPayloadFileName', 'bootstrap_payload_file_name', payload_name),
        ('bootstrapPayloadSha256', 'bootstrap_payload_sha256', digest),
        ('bootstrapPayloadSizeBytes', 'bootstrap_payload_size_bytes', len(payload_bytes)),
    ]
    receipt.update({snake if snake_aliases else camel: value for camel, snake, value in fields})
    receipt['artifactPath'] = receipt['artifactRelativePath']
    receipt['startedAtUtc'] = receipt['recordedAtUtc'] = receipt['completedAtUtc']
    receipt_path.write_text(json.dumps(receipt))
    payload, _ = write_candidate(args)
    assert payload['artifacts'][0]['installerMode'] == 'bootstrap'
    (args.downloads_dir / payload_name).write_bytes(payload_bytes)
    sidecar = {'contractName': 'chummer6-ui.windows_bootstrap_payload', 'fileName': payload_name,
               'downloadUrl': f'/downloads/files/{payload_name}', 'sha256': digest,
               'sizeBytes': len(payload_bytes), 'installerFileName': receipt['artifactFileName'],
               'releaseVersion': receipt['releaseVersion'], 'payloadAcquisitionMode': 'download'}
    sidecar_path = args.downloads_dir / (payload_name + '.json')
    sidecar_path.write_text(json.dumps(sidecar))
    result = subprocess.run([sys.executable, str(Path(V.__file__)), '--publication-profile',
                             V.WINDOWS_PREVIEW_PROFILE, str(root)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    for extra in ({'apiKey': 'synthetic'}, {'Authorization': 'synthetic'}, {'Cookie': 'synthetic'},
                  {'artifactPath': '/var/lib/private-build/payload.zip'}, {'debugContext': {}},
                  {'sizeBytes': {'Cookie': 'synthetic'}}):
        sidecar_path.write_text(json.dumps({**sidecar, **extra}))
        with pytest.raises(SystemExit, match='Windows preview metadata'):
            V.verify_local_download_files(payload, root, 'synthetic sidecar')
