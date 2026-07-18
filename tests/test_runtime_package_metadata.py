from __future__ import annotations

import hashlib
import re
import subprocess
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PROJECT = ROOT / "Chummer.Run.Registry" / "Chummer.Run.Registry.csproj"
CONTRACTS_PROJECT = (
    ROOT / "Chummer.Hub.Registry.Contracts" / "Chummer.Hub.Registry.Contracts.csproj"
)
LICENSE_PATH = ROOT / "LICENSE"
PACKAGE_VERSION = "0.0.0-packageplane.20260718.1"
REPOSITORY_URL = "https://github.com/ArchonMegalon/chummer6-hub-registry.git"
RUNTIME_EXACT_PACKAGE_FILES = {
    "_rels/.rels",
    "Chummer.Run.Registry.nuspec",
    "lib/net10.0/Chummer.Run.Registry.dll",
    "lib/net10.0/Chummer.Run.Registry.xml",
    "PACKAGE_README.md",
    "LICENSE",
    "[Content_Types].xml",
}
CORE_PROPERTIES_PATTERN = re.compile(
    r"^package/services/metadata/core-properties/[0-9a-f]{32}\.psmdcp$"
)


def _local_name(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _metadata(nuspec: ElementTree.Element, name: str) -> ElementTree.Element:
    matches = [element for element in nuspec.iter() if _local_name(element) == name]
    assert len(matches) == 1, f"expected one {name} element"
    return matches[0]


def validate_runtime_project(project_xml: str) -> None:
    project = ElementTree.fromstring(project_xml)
    properties = {
        element.tag: (element.text or "").strip()
        for group in project.findall("./PropertyGroup")
        for element in group
    }
    assert properties["IsPackable"] == "true"
    assert properties["PackageId"] == "Chummer.Run.Registry"
    assert properties["PackageVersion"] == PACKAGE_VERSION
    assert properties["PackageLicenseFile"] == "LICENSE"
    assert properties["PackageReadmeFile"] == "PACKAGE_README.md"
    assert properties["RepositoryType"] == "git"
    assert properties["RepositoryUrl"] == REPOSITORY_URL
    assert properties["PublishRepositoryUrl"] == "true"

    packed = {
        item.get("Include"): item
        for item in project.findall(".//None")
        if item.get("Pack", "").lower() == "true"
    }
    assert packed["../LICENSE"].get("PackagePath") == ""
    assert packed["PACKAGE_README.md"].get("PackagePath") == "\\"


def validate_runtime_package_inventory(names: list[str]) -> None:
    observed = set(names)
    assert "lib/net10.0/Chummer.Run.Registry.dll" in observed
    assert "Chummer.Run.Registry.nuspec" in observed
    assert "PACKAGE_README.md" in observed
    assert "LICENSE" in observed
    unexpected = {
        name
        for name in observed
        if name not in RUNTIME_EXACT_PACKAGE_FILES
        and CORE_PROPERTIES_PATTERN.fullmatch(name) is None
    }
    assert not unexpected, f"unexpected Registry runtime package files: {sorted(unexpected)}"


def test_runtime_project_is_explicitly_versioned_and_licensed() -> None:
    validate_runtime_project(RUNTIME_PROJECT.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "old,new",
    [
        ("<IsPackable>true</IsPackable>", "<IsPackable>false</IsPackable>"),
        ("<PackageLicenseFile>LICENSE</PackageLicenseFile>", ""),
        (f"<RepositoryUrl>{REPOSITORY_URL}</RepositoryUrl>", ""),
        ('<None Include="../LICENSE" Pack="true" PackagePath="" />',
         '<None Include="../LICENSE" Pack="false" PackagePath="" />'),
    ],
)
def test_runtime_metadata_validator_rejects_regressions(old: str, new: str) -> None:
    project_xml = RUNTIME_PROJECT.read_text(encoding="utf-8")
    with pytest.raises((AssertionError, KeyError)):
        validate_runtime_project(project_xml.replace(old, new, 1))


def test_runtime_package_contains_license_readme_dependency_and_provenance(
    tmp_path: Path,
) -> None:
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    output = tmp_path / "feed"
    output.mkdir()
    common = [
        "--configuration", "Release",
        "--output", str(output),
        "--nologo",
        f"-p:PackageVersion={PACKAGE_VERSION}",
        f"-p:Version={PACKAGE_VERSION}",
        f"-p:RepositoryCommit={source_commit}",
        f"-p:RepositoryUrl={REPOSITORY_URL}",
        "-p:PublishRepositoryUrl=true",
        "-p:ContinuousIntegrationBuild=true",
    ]
    for project in (CONTRACTS_PROJECT, RUNTIME_PROJECT):
        subprocess.run(
            ["dotnet", "pack", str(project), *common],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    packages = list(output.glob(f"Chummer.Run.Registry.{PACKAGE_VERSION}.nupkg"))
    assert len(packages) == 1
    package_path = packages[0]
    assert hashlib.sha256(package_path.read_bytes()).hexdigest()

    with ZipFile(package_path) as package:
        names = package.namelist()
        validate_runtime_package_inventory(names)
        assert "LICENSE" in names
        assert "PACKAGE_README.md" in names
        assert package.read("LICENSE") == LICENSE_PATH.read_bytes()
        nuspec_name = next(name for name in names if name.endswith(".nuspec"))
        nuspec = ElementTree.fromstring(package.read(nuspec_name))
        assert (_metadata(nuspec, "id").text or "").strip() == "Chummer.Run.Registry"
        assert (_metadata(nuspec, "version").text or "").strip() == PACKAGE_VERSION
        license_metadata = _metadata(nuspec, "license")
        assert license_metadata.get("type") == "file"
        assert (license_metadata.text or "").strip() == "LICENSE"
        repository = _metadata(nuspec, "repository")
        assert repository.get("type") == "git"
        assert repository.get("url") == REPOSITORY_URL
        assert repository.get("commit") == source_commit
        dependencies = [
            element
            for element in nuspec.iter()
            if _local_name(element) == "dependency"
        ]
        assert any(
            dependency.get("id") == "Chummer.Hub.Registry.Contracts"
            and PACKAGE_VERSION in (dependency.get("version") or "")
            for dependency in dependencies
        )


@pytest.mark.parametrize(
    "forbidden_name",
    [
        "content/appsettings.json",
        "contentFiles/any/net10.0/appsettings.Development.json",
        "lib/net10.0/Chummer.Run.Registry.runtimeconfig.json",
        "lib/net10.0/metadata-valid-malicious.dll",
    ],
)
def test_runtime_package_inventory_rejects_host_or_unlisted_content(
    forbidden_name: str,
) -> None:
    baseline = [
        "_rels/.rels",
        "Chummer.Run.Registry.nuspec",
        "lib/net10.0/Chummer.Run.Registry.dll",
        "PACKAGE_README.md",
        "LICENSE",
        "[Content_Types].xml",
        "package/services/metadata/core-properties/0123456789abcdef0123456789abcdef.psmdcp",
    ]
    with pytest.raises(AssertionError, match="unexpected Registry runtime package files"):
        validate_runtime_package_inventory([*baseline, forbidden_name])
