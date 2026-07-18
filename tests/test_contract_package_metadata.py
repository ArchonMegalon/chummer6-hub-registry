from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable
from pathlib import Path
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROJECT_PATH = (
    ROOT
    / "Chummer.Hub.Registry.Contracts"
    / "Chummer.Hub.Registry.Contracts.csproj"
)
LICENSE_PATH = ROOT / "LICENSE"
RUNTIME_IDENTIFIER_CONDITION = (
    "'$(RuntimeIdentifiers)' == '' and '$(RuntimeIdentifier)' != ''"
)
EXPECTED_LICENSE = """# Chummer6 Hub License

Copyright (c) ArchonMegalon.
All rights reserved.

This repository is not offered under the GNU General Public License.
No license is granted to copy, redistribute, sublicense, or create derivative
works from this source without prior written permission from the copyright
holder, except where a separate third-party notice explicitly says otherwise.

Any third-party dependencies, tools, or assets referenced by this repository
retain their own licenses.
"""


def validate_contract_package_metadata(project_xml: str, license_text: str) -> None:
    project = ElementTree.fromstring(project_xml)

    runtime_identifiers = project.findall(".//RuntimeIdentifiers")
    assert len(runtime_identifiers) == 1, (
        "the contracts project must define exactly one RuntimeIdentifiers fallback"
    )
    runtime_identifier = runtime_identifiers[0]
    assert runtime_identifier.get("Condition") == RUNTIME_IDENTIFIER_CONDITION
    assert (runtime_identifier.text or "").strip() == "$(RuntimeIdentifier)"

    package_license_files = project.findall(".//PackageLicenseFile")
    assert len(package_license_files) == 1
    assert (package_license_files[0].text or "").strip() == "LICENSE"

    packed_license_files = [
        item
        for item in project.findall(".//None")
        if item.get("Include") == "../LICENSE"
    ]
    assert len(packed_license_files) == 1
    packed_license = packed_license_files[0]
    assert packed_license.get("Pack", "").lower() == "true"
    assert packed_license.get("PackagePath") == ""

    assert license_text == EXPECTED_LICENSE


def test_contract_project_has_one_runtime_fallback_and_explicit_license() -> None:
    validate_contract_package_metadata(
        PROJECT_PATH.read_text(encoding="utf-8-sig"),
        LICENSE_PATH.read_text(encoding="utf-8"),
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda project_xml: project_xml.replace(
            "</PropertyGroup>",
            (
                f'<RuntimeIdentifiers Condition="{RUNTIME_IDENTIFIER_CONDITION}">'
                "$(RuntimeIdentifier)</RuntimeIdentifiers>\n  </PropertyGroup>"
            ),
            1,
        ),
        lambda project_xml: project_xml.replace(
            "<PackageLicenseFile>LICENSE</PackageLicenseFile>", "", 1
        ),
        lambda project_xml: project_xml.replace(
            '<None Include="../LICENSE" Pack="true" PackagePath="" />',
            '<None Include="../LICENSE" Pack="false" PackagePath="" />',
            1,
        ),
    ],
    ids=["duplicate-runtime-fallback", "missing-license-metadata", "unpacked-license"],
)
def test_metadata_validator_rejects_regressions(
    mutation: Callable[[str], str],
) -> None:
    project_xml = PROJECT_PATH.read_text(encoding="utf-8-sig")
    with pytest.raises(AssertionError):
        validate_contract_package_metadata(mutation(project_xml), EXPECTED_LICENSE)


def test_metadata_validator_rejects_repository_license_drift() -> None:
    with pytest.raises(AssertionError):
        validate_contract_package_metadata(
            PROJECT_PATH.read_text(encoding="utf-8-sig"),
            EXPECTED_LICENSE.replace("All rights reserved.", "Licensed permissively."),
        )


def test_packed_contract_exposes_the_repository_license(tmp_path: Path) -> None:
    subprocess.run(
        [
            "dotnet",
            "pack",
            str(PROJECT_PATH),
            "--configuration",
            "Release",
            "--output",
            str(tmp_path),
            "--nologo",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    packages = list(tmp_path.glob("Chummer.Hub.Registry.Contracts.*.nupkg"))
    assert len(packages) == 1
    with ZipFile(packages[0]) as package:
        assert "LICENSE" in package.namelist()
        assert package.read("LICENSE").decode("utf-8") == EXPECTED_LICENSE

        nuspec_names = [name for name in package.namelist() if name.endswith(".nuspec")]
        assert len(nuspec_names) == 1
        nuspec = ElementTree.fromstring(package.read(nuspec_names[0]))
        license_metadata = next(
            element for element in nuspec.iter() if element.tag.endswith("}license")
        )
        assert license_metadata.get("type") == "file"
        assert (license_metadata.text or "").strip() == "LICENSE"
