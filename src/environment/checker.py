"""Compare the active Python environment with the compiled requirements."""

from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Callable

from packaging.requirements import Requirement


PACKAGE_INDEXES = {
    "Default": None,
    "PyPI": "https://pypi.org/simple",
    "Tsinghua": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "Aliyun": "https://mirrors.aliyun.com/pypi/simple/",
    "USTC": "https://pypi.mirrors.ustc.edu.cn/simple/",
    "Huawei Cloud": "https://repo.huaweicloud.com/repository/pypi/simple/",
    "Tencent Cloud": "https://mirrors.cloud.tencent.com/pypi/simple/",
}


@dataclass(frozen=True)
class RequirementIssue:
    requirement: Requirement
    installed_version: str | None

    @property
    def is_missing(self) -> bool:
        return self.installed_version is None


@dataclass(frozen=True)
class EnvironmentReport:
    issues: tuple[RequirementIssue, ...]

    @property
    def is_healthy(self) -> bool:
        return not self.issues

    @property
    def missing(self) -> tuple[RequirementIssue, ...]:
        return tuple(issue for issue in self.issues if issue.is_missing)

    @property
    def outdated(self) -> tuple[RequirementIssue, ...]:
        return tuple(issue for issue in self.issues if not issue.is_missing)

    @property
    def requirements_to_install(self) -> tuple[str, ...]:
        return tuple(str(issue.requirement) for issue in self.issues)


class PythonEnvironmentChecker:
    def __init__(
        self,
        requirements_path: Path,
        version_getter: Callable[[str], str] = metadata.version,
    ):
        self.requirements_path = requirements_path
        self.version_getter = version_getter

    def check(self) -> EnvironmentReport:
        issues = []
        for requirement in load_requirements(self.requirements_path):
            try:
                installed_version = self.version_getter(requirement.name)
            except metadata.PackageNotFoundError:
                installed_version = None

            if installed_version is None or (
                requirement.specifier
                and not requirement.specifier.contains(
                    installed_version, prereleases=True
                )
            ):
                issues.append(RequirementIssue(requirement, installed_version))
        return EnvironmentReport(tuple(issues))


def load_requirements(path: Path) -> list[Requirement]:
    """Load active PEP 508 entries from the project's compiled lock file."""
    requirements = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        requirement_text = line.split(" #", 1)[0].strip()
        try:
            requirement = Requirement(requirement_text)
        except ValueError as exc:
            raise ValueError(
                f"Invalid requirement on line {line_number}: {line}"
            ) from exc
        if requirement.marker is None or requirement.marker.evaluate():
            requirements.append(requirement)
    return requirements
