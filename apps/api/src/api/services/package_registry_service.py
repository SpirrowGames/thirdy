"""Package registry service — checks npm/PyPI for version updates and GitHub for advisories."""

import logging
import re
from dataclasses import dataclass, field

import httpx

from api.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PackageVersionInfo:
    name: str
    ecosystem: str  # npm / pypi
    current_version: str | None = None
    latest_version: str | None = None
    is_outdated: bool = False
    update_type: str | None = None  # major / minor / patch
    latest_release_date: str | None = None
    registry_url: str | None = None


@dataclass
class SecurityAdvisory:
    package: str
    ecosystem: str
    ghsa_id: str
    cve_id: str | None = None
    severity: str = "unknown"  # low / medium / high / critical
    summary: str = ""
    url: str = ""


@dataclass
class RegistryReport:
    outdated: list[PackageVersionInfo] = field(default_factory=list)
    advisories: list[SecurityAdvisory] = field(default_factory=list)


def _parse_semver(version: str) -> tuple[int, int, int] | None:
    """Parse a semver string, stripping prefix operators."""
    cleaned = re.sub(r'^[~^>=<! ]+', '', version.strip())
    m = re.match(r'(\d+)\.(\d+)\.(\d+)', cleaned)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.match(r'(\d+)\.(\d+)', cleaned)
    if m:
        return int(m.group(1)), int(m.group(2)), 0
    return None


def _compare_versions(current: str, latest: str) -> str | None:
    """Return 'major', 'minor', 'patch', or None if same/unparseable."""
    cur = _parse_semver(current)
    lat = _parse_semver(latest)
    if not cur or not lat:
        return None
    if lat <= cur:
        return None
    if lat[0] > cur[0]:
        return "major"
    if lat[1] > cur[1]:
        return "minor"
    if lat[2] > cur[2]:
        return "patch"
    return None


class PackageRegistryService:
    def __init__(self, http: httpx.AsyncClient):
        self._http = http

    async def check_npm_package(self, name: str, current_version: str | None = None) -> PackageVersionInfo:
        """Check latest version of an npm package."""
        info = PackageVersionInfo(name=name, ecosystem="npm", current_version=current_version)
        try:
            resp = await self._http.get(
                f"https://registry.npmjs.org/{name}/latest",
                timeout=10,
            )
            if resp.status_code != 200:
                return info
            data = resp.json()
            info.latest_version = data.get("version")
            info.registry_url = f"https://www.npmjs.com/package/{name}"
            if current_version and info.latest_version:
                update = _compare_versions(current_version, info.latest_version)
                if update:
                    info.is_outdated = True
                    info.update_type = update
        except Exception as e:
            logger.warning("npm registry check failed for %s: %s", name, e)
        return info

    async def check_pypi_package(self, name: str, current_version: str | None = None) -> PackageVersionInfo:
        """Check latest version of a PyPI package."""
        info = PackageVersionInfo(name=name, ecosystem="pypi", current_version=current_version)
        try:
            resp = await self._http.get(
                f"https://pypi.org/pypi/{name}/json",
                timeout=10,
            )
            if resp.status_code != 200:
                return info
            data = resp.json()
            info.latest_version = data.get("info", {}).get("version")
            info.registry_url = f"https://pypi.org/project/{name}/"
            if current_version and info.latest_version:
                update = _compare_versions(current_version, info.latest_version)
                if update:
                    info.is_outdated = True
                    info.update_type = update
        except Exception as e:
            logger.warning("PyPI check failed for %s: %s", name, e)
        return info

    async def check_github_advisories(
        self,
        packages: list[tuple[str, str]],  # [(name, ecosystem), ...]
    ) -> list[SecurityAdvisory]:
        """Check GitHub Advisory Database for known vulnerabilities."""
        if not settings.github_token:
            return []

        advisories: list[SecurityAdvisory] = []
        ecosystem_map = {"npm": "npm", "pypi": "pip"}

        for name, ecosystem in packages:
            gh_eco = ecosystem_map.get(ecosystem)
            if not gh_eco:
                continue
            try:
                resp = await self._http.get(
                    "https://api.github.com/advisories",
                    params={
                        "ecosystem": gh_eco,
                        "affects": name,
                        "per_page": 5,
                    },
                    headers={
                        "Authorization": f"Bearer {settings.github_token}",
                        "Accept": "application/vnd.github+json",
                    },
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue
                for adv in resp.json():
                    advisories.append(SecurityAdvisory(
                        package=name,
                        ecosystem=ecosystem,
                        ghsa_id=adv.get("ghsa_id", ""),
                        cve_id=adv.get("cve_id"),
                        severity=adv.get("severity", "unknown"),
                        summary=adv.get("summary", ""),
                        url=adv.get("html_url", ""),
                    ))
            except Exception as e:
                logger.warning("GitHub Advisory check failed for %s: %s", name, e)

        return advisories

    async def check_packages(
        self,
        npm_deps: dict[str, str] | None = None,
        pypi_deps: dict[str, str] | None = None,
    ) -> RegistryReport:
        """Check all packages for updates and advisories."""
        report = RegistryReport()
        advisory_targets: list[tuple[str, str]] = []

        if npm_deps:
            for name, version in npm_deps.items():
                info = await self.check_npm_package(name, version)
                if info.is_outdated:
                    report.outdated.append(info)
                advisory_targets.append((name, "npm"))

        if pypi_deps:
            for name, version in pypi_deps.items():
                info = await self.check_pypi_package(name, version)
                if info.is_outdated:
                    report.outdated.append(info)
                advisory_targets.append((name, "pypi"))

        if advisory_targets:
            report.advisories = await self.check_github_advisories(advisory_targets)

        return report
