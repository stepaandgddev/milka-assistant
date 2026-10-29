"""Install Milky addons (skills) from public GitHub repositories.

A skill repository is an ordinary Milky addon folder: it contains an
``addon.json`` manifest and the Python entry module named by that manifest.
The repository root may be the addon itself, or it may contain one or more
addon folders nested up to four levels deep. A GitHub URL that points to a
folder inside the repository is also supported::

    https://github.com/owner/repo
    https://github.com/owner/repo/tree/main/path/to/addon
    owner/repo

Only public repositories are supported. Addons are Python code and run with
the same permissions as Milky, so the caller must ask the user for
confirmation before installing.
"""

from __future__ import annotations

import io
import json
import os
import posixpath
import re
import shutil
import stat
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit

import requests

API_VERSION = 1
MAX_ARCHIVE_BYTES = 30 * 1024 * 1024
MAX_EXTRACTED_BYTES = 80 * 1024 * 1024
MAX_ARCHIVE_FILES = 2500
MAX_ADDON_DEPTH = 4
DOWNLOAD_TIMEOUT = 60

_ALWAYS_IGNORED = {".git", "__pycache__", ".DS_Store", "__MACOSX"}

_IGNORED_PARTS = {
    ".git",
    ".github",
    ".idea",
    ".vscode",
    ".data",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    "tests",
    "__tests__",
    "fixtures",
    "__MACOSX",
}

_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_SLUG_RE = re.compile(r"[^A-Za-z0-9_-]+")


class SkillInstallError(RuntimeError):
    """A user-facing error raised while installing a GitHub skill."""


@dataclass(frozen=True)
class GithubSource:
    owner: str
    repo: str
    branch: str = ""
    subpath: str = ""

    @property
    def label(self):
        name = f"{self.owner}/{self.repo}"
        if self.branch:
            name += f"@{self.branch}"
        if self.subpath:
            name += f"/{self.subpath}"
        return name

    @property
    def archive_url(self):
        if self.branch:
            ref = "refs/heads/" + quote(self.branch, safe="/")
        else:
            ref = "HEAD"
        return (
            f"https://codeload.github.com/{self.owner}/{self.repo}/zip/{ref}"
        )


def parse_github_url(value):
    """Parse a GitHub repository or folder URL into a :class:`GithubSource`."""
    text = str(value or "").strip()
    if not text:
        raise SkillInstallError("Enter a GitHub repository URL.")

    lowered = text.lower()
    if lowered.startswith("git@github.com:"):
        text = "https://github.com/" + text[len("git@github.com:") :]
    elif lowered.startswith("ssh://git@github.com/"):
        text = "https://github.com/" + text[len("ssh://git@github.com/") :]
    elif lowered.startswith(("github.com/", "www.github.com/")):
        text = "https://" + text
    elif "://" not in text:
        text = "https://github.com/" + text

    parts = urlsplit(text)
    if parts.scheme not in ("http", "https"):
        raise SkillInstallError("The URL must start with http:// or https://.")
    if parts.hostname not in ("github.com", "www.github.com"):
        raise SkillInstallError("Only github.com repositories are supported.")

    segments = [unquote(part) for part in parts.path.split("/") if part]
    if len(segments) < 2:
        raise SkillInstallError(
            "Use a repository URL such as https://github.com/owner/repo."
        )

    owner = segments[0]
    repo = segments[1]
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    if not _OWNER_RE.fullmatch(owner) or not _REPO_RE.fullmatch(repo):
        raise SkillInstallError("That does not look like a valid GitHub URL.")

    branch = ""
    subpath = ""
    if len(segments) > 2:
        marker = segments[2].lower()
        if marker == "tree":
            if len(segments) < 4:
                raise SkillInstallError(
                    "A /tree/ URL must include a branch name."
                )
            branch = segments[3]
            subpath = "/".join(segments[4:])
        elif marker in ("blob", "raw", "releases", "issues", "pull"):
            raise SkillInstallError(
                "Point to a repository or a folder, not to a file."
            )
        else:
            raise SkillInstallError(
                "Unsupported GitHub URL. Use the repository page or a "
                "/tree/<branch>/<folder> link."
            )

    subpath = subpath.strip("/")
    if any(part in ("..", ".") for part in subpath.split("/") if part):
        raise SkillInstallError("The folder path is not allowed.")
    return GithubSource(owner, repo, branch, subpath)


def download_github_archive(source, timeout=DOWNLOAD_TIMEOUT):
    """Download the zip archive of a public GitHub repository."""
    headers = {
        "User-Agent": "Milky addon installer",
        "Accept": "application/zip",
    }
    try:
        with requests.get(
            source.archive_url,
            headers=headers,
            timeout=timeout,
            stream=True,
        ) as response:
            if response.status_code == 404:
                raise SkillInstallError(
                    f"Repository or branch not found: {source.label}. "
                    "Only public repositories are supported."
                )
            if response.status_code != 200:
                raise SkillInstallError(
                    f"GitHub returned HTTP {response.status_code} for "
                    f"{source.label}."
                )
            length = response.headers.get("Content-Length")
            if length:
                try:
                    if int(length) > MAX_ARCHIVE_BYTES:
                        raise SkillInstallError(
                            "The repository archive is too large."
                        )
                except ValueError:
                    pass

            data = bytearray()
            for chunk in response.iter_content(65536):
                if not chunk:
                    continue
                data.extend(chunk)
                if len(data) > MAX_ARCHIVE_BYTES:
                    raise SkillInstallError(
                        "The repository archive is too large."
                    )
            return bytes(data)
    except SkillInstallError:
        raise
    except requests.RequestException as error:
        raise SkillInstallError(
            f"Could not download {source.label}: {error}"
        ) from error


def install_skill_from_github(url, destination=None, timeout=DOWNLOAD_TIMEOUT):
    """Download and install every addon found in a public GitHub repository."""
    source = parse_github_url(url)
    archive = download_github_archive(source, timeout=timeout)
    result = install_from_archive(
        archive,
        destination=destination,
        subpath=source.subpath,
    )
    result["source"] = source.label
    return result


def install_from_archive(archive_bytes, destination=None, subpath=""):
    """Install addons from a GitHub-style zip archive without using network."""
    if not archive_bytes:
        raise SkillInstallError("The downloaded archive is empty.")
    if not zipfile.is_zipfile(io.BytesIO(archive_bytes)):
        raise SkillInstallError(
            "GitHub did not return a zip archive. Check the repository URL."
        )

    destination = Path(destination or _default_addons_dir())
    destination.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="milky-skill-") as temporary:
        root = Path(temporary)
        _safe_extract(archive_bytes, root)
        archive_root = _archive_root(root)

        base = archive_root
        subpath = str(subpath or "").strip("/")
        if subpath:
            base = (archive_root / subpath).resolve()
            if not _is_within(base, archive_root):
                raise SkillInstallError(
                    "The folder path leaves the repository."
                )
            if not base.is_dir():
                raise SkillInstallError(
                    f"The folder /{subpath} was not found in the repository."
                )

        folders = _discover_addon_dirs(base, archive_root, bool(subpath))
        if not folders:
            raise SkillInstallError(
                "No addon.json was found. A skill repository needs an "
                "addon.json manifest and its Python entry file."
            )

        prepared = []
        seen = set()
        for folder in folders:
            manifest = _validate_addon(folder)
            key = manifest["id"].lower()
            if key in seen:
                raise SkillInstallError(
                    f"The repository contains two addons with id "
                    f"{manifest['id']!r}."
                )
            seen.add(key)
            prepared.append((folder, manifest))

        installed = []
        for folder, manifest in prepared:
            target = destination / manifest["id"]
            _install_folder(folder, target)
            installed.append(
                {
                    "id": manifest["id"],
                    "name": manifest["name"],
                    "version": manifest["version"],
                    "description": manifest["description"],
                    "path": str(target),
                }
            )
        return {"installed": installed}


def _default_addons_dir():
    from addon_manager import addons_directory

    return addons_directory()


def _slug(value, fallback="addon"):
    text = _SLUG_RE.sub("_", str(value or "")).strip("_")
    return (text or fallback)[:64]


def _is_within(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def _safe_extract(archive_bytes, destination):
    total = 0
    files = 0
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for info in archive.infolist():
            files += 1
            if files > MAX_ARCHIVE_FILES:
                raise SkillInstallError(
                    "The repository archive contains too many files."
                )
            name = str(info.filename or "").replace("\\", "/")
            if not name:
                continue
            pure = PurePosixPath(name)
            if pure.is_absolute() or any(part == ".." for part in pure.parts):
                raise SkillInstallError(
                    "The repository archive contains an unsafe path."
                )
            if os.name == "nt" and any(":" in part for part in pure.parts):
                raise SkillInstallError(
                    "The repository archive contains an unsafe path."
                )

            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                continue

            normalized = posixpath.normpath(name)
            if normalized in ("", "."):
                continue
            if normalized.startswith("../") or normalized.startswith("/"):
                raise SkillInstallError(
                    "The repository archive contains an unsafe path."
                )
            target = (destination / normalized).resolve()
            if not _is_within(target, destination):
                raise SkillInstallError(
                    "The repository archive contains an unsafe path."
                )

            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            total += int(info.file_size or 0)
            if total > MAX_EXTRACTED_BYTES:
                raise SkillInstallError(
                    "The repository archive is too large when unpacked."
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, open(target, "wb") as output:
                shutil.copyfileobj(source, output)


def _archive_root(root):
    entries = [path for path in root.iterdir()]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return root


def _discover_addon_dirs(base, archive_root, has_subpath):
    if not has_subpath and (archive_root / "addon.json").is_file():
        return [archive_root]

    candidates = []
    for manifest in base.rglob("addon.json"):
        try:
            relative = manifest.parent.relative_to(archive_root)
        except ValueError:
            continue
        if len(relative.parts) > MAX_ADDON_DEPTH:
            continue
        if any(part in _IGNORED_PARTS for part in relative.parts):
            continue
        if not manifest.is_file():
            continue
        candidates.append(manifest.parent)

    candidates.sort(key=lambda path: (len(path.parts), str(path).lower()))
    selected = []
    for folder in candidates:
        if any(_is_within(folder, parent) for parent in selected):
            continue
        selected.append(folder)
    return selected


def _validate_addon(folder):
    manifest_path = folder / "addon.json"
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise SkillInstallError(
            f"Cannot read {folder.name}/addon.json: {error}"
        ) from error
    if not isinstance(data, dict):
        raise SkillInstallError(
            f"{folder.name}/addon.json must contain an object."
        )

    addon_id = _slug(data.get("id") or folder.name)
    entry = str(data.get("entry") or "addon.py").strip() or "addon.py"
    entry_path = (folder / entry).resolve()
    if not _is_within(entry_path, folder):
        raise SkillInstallError(
            f"The entry file of {addon_id!r} must stay inside its folder."
        )
    if not entry_path.is_file():
        raise SkillInstallError(
            f"{addon_id!r} is missing its entry file: {entry}"
        )

    try:
        api = int(data.get("api", 1))
    except (TypeError, ValueError):
        api = 1
    if api > API_VERSION:
        raise SkillInstallError(
            f"{addon_id!r} requires addon API {api}; Milky supports "
            f"{API_VERSION}."
        )

    name = " ".join(str(data.get("name") or addon_id).split()) or addon_id
    version = str(data.get("version") or "").strip()[:30]
    description = " ".join(str(data.get("description") or "").split())[:300]

    icon = str(data.get("icon") or "").strip()
    if icon:
        icon_path = (folder / icon).resolve()
        if not _is_within(icon_path, folder) or not icon_path.is_file():
            raise SkillInstallError(
                f"The icon of {addon_id!r} must be a file inside its "
                f"folder: {icon}"
            )

    return {
        "id": addon_id,
        "name": name,
        "version": version,
        "description": description,
    }


def _install_folder(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f".install-{target.name}-{uuid.uuid4().hex[:8]}"
    backup = target.parent / f".backup-{target.name}-{uuid.uuid4().hex[:8]}"
    source = Path(source)

    def ignore(directory, names):
        return _copy_ignore(source, directory, names)

    try:
        shutil.copytree(source, staging, ignore=ignore)
        if target.exists():
            target.rename(backup)
        try:
            staging.rename(target)
        except Exception:
            if backup.exists() and not target.exists():
                backup.rename(target)
            raise
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def _copy_ignore(source, directory, names):
    directory = Path(directory)
    assets_root = source / "assets"
    try:
        directory.resolve().relative_to(assets_root.resolve())
        in_assets = True
    except ValueError:
        in_assets = False

    ignored = set()
    for name in names:
        if name in _ALWAYS_IGNORED or name.endswith((".pyc", ".pyo")):
            ignored.add(name)
        elif not in_assets and name in _IGNORED_PARTS:
            ignored.add(name)
    return ignored


__all__ = [
    "GithubSource",
    "SkillInstallError",
    "download_github_archive",
    "install_from_archive",
    "install_skill_from_github",
    "parse_github_url",
]
