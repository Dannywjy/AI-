#!/usr/bin/env python3
"""Install pinned, project-local skills through Codex's official installer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import subprocess
import sys
import tempfile


RECORD = ".codex-media-source.json"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class InstallError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InstallError(message)


def read_lock(root: Path) -> list[dict]:
    lock_path = root / "media-skills.lock.json"
    require(not lock_path.is_symlink(), "Lock file must not be a symbolic link")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    require(isinstance(lock, dict) and lock.get("schema_version") == 1,
            "Expected lock schema_version 1")
    sources = lock.get("sources")
    require(isinstance(sources, list) and bool(sources), "Lock requires sources")
    names, ids = set(), set()
    for source in sources:
        require(isinstance(source, dict), "Invalid source entry")
        source_id, repo, ref = (source.get(key) for key in ("id", "repo", "ref"))
        require(isinstance(source_id, str) and bool(SLUG.fullmatch(source_id))
                and source_id not in ids, "Invalid or duplicate source id")
        ids.add(source_id)
        require(isinstance(repo, str) and bool(re.fullmatch(
            r"[A-Za-z0-9_-][A-Za-z0-9_.-]*/[A-Za-z0-9_-][A-Za-z0-9_.-]*", repo)),
            f"Invalid owner/repo for {source_id}")
        require(isinstance(ref, str) and bool(re.fullmatch(r"[0-9a-fA-F]{40}", ref)),
                f"Source {source_id} must use a full 40-character commit SHA")
        skills = source.get("skills")
        require(isinstance(skills, list) and bool(skills), f"No skills in {source_id}")
        for skill in skills:
            require(isinstance(skill, dict), "Invalid skill entry")
            path, name = skill.get("path"), skill.get("name")
            require(isinstance(path, str) and bool(path) and "\\" not in path
                    and not PurePosixPath(path).is_absolute()
                    and (path == "." or all(part not in ("", ".", "..")
                                            for part in path.split("/")))
                    and not path.startswith("-"), f"Unsafe skill path: {path!r}")
            require(isinstance(name, str) and bool(SLUG.fullmatch(name))
                    and name not in names, f"Invalid or duplicate skill name: {name!r}")
            names.add(name)
    return sources


def project_paths(root: Path) -> tuple[Path, Path]:
    require(not root.is_symlink() and root.is_dir(), "Project root must be a real directory")
    root = root.resolve()
    for path in (root / ".agents", root / ".agents" / "skills"):
        require(not path.is_symlink(), f"Symbolic-link destination refused: {path}")
        require(not path.exists() or path.is_dir(), f"Expected directory: {path}")
    return root, root / ".agents" / "skills"


def scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1].strip()
    return value.split(" #", 1)[0].strip()


def validate_frontmatter(directory: Path, name: str) -> None:
    skill_file = directory / "SKILL.md"
    require(skill_file.is_file() and not skill_file.is_symlink(), f"Missing SKILL.md: {name}")
    lines = skill_file.read_text(encoding="utf-8").splitlines()
    require(bool(lines) and lines[0].strip() == "---", f"Missing frontmatter: {name}")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    require(end is not None, f"Unclosed frontmatter: {name}")
    fields = {}
    for index, line in enumerate(lines[1:end], 1):
        match = re.match(r"^(name|description):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        require(key not in fields, f"Duplicate {key} in {name}")
        if re.fullmatch(r"[|>][+-]?", value.strip()):
            continuation = []
            for following in lines[index + 1:end]:
                if following and not following[0].isspace():
                    break
                continuation.append(following.strip())
            value = " ".join(continuation)
        fields[key] = scalar(value)
    require(fields.get("name") == name, f"Frontmatter name must match {name}")
    require(bool(fields.get("description")) and not fields["description"].startswith("#"),
            f"Missing frontmatter description: {name}")


def tree_sha256(directory: Path) -> str:
    require(directory.is_dir() and not directory.is_symlink(), f"Invalid skill directory: {directory}")
    digest = hashlib.sha256()
    for entry in sorted(directory.rglob("*")):
        relative = entry.relative_to(directory).as_posix()
        mode = entry.lstat().st_mode
        require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), f"Unsupported file or symlink: {entry}")
        if relative == RECORD:
            continue
        digest.update((relative + ("/" if entry.is_dir() else "") + "\0").encode())
        if entry.is_file():
            content_hash = hashlib.sha256()
            with entry.open("rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    content_hash.update(chunk)
            digest.update(content_hash.digest())
        digest.update(b"\0")
    return digest.hexdigest()


def identity(source: dict, skill: dict) -> dict:
    return {"schema_version": 1, "source_id": source["id"], "repo": source["repo"],
            "ref": source["ref"], "path": skill["path"], "name": skill["name"]}


def verify(directory: Path, source: dict, skill: dict) -> None:
    expected = identity(source, skill)
    require(directory.is_dir() and not directory.is_symlink(), f"Missing or unsafe skill: {directory}")
    record_file = directory / RECORD
    require(record_file.is_file() and not record_file.is_symlink(),
            f"Existing skill has no trusted installation record: {skill['name']}")
    record = json.loads(record_file.read_text(encoding="utf-8"))
    require(isinstance(record, dict) and all(record.get(k) == v for k, v in expected.items()),
            f"Installed source/version differs: {skill['name']}; refusing to overwrite")
    validate_frontmatter(directory, skill["name"])
    require(record.get("tree_sha256") == tree_sha256(directory),
            f"Installed skill was modified: {skill['name']}; refusing to overwrite")


def commands(installer: Path, source: dict, skills: list[dict], stage: Path) -> list[list[str]]:
    base = [sys.executable, str(installer), "--repo", source["repo"], "--ref", source["ref"]]
    suffix = ["--dest", str(stage), "--method", "download"]
    if all(skill["path"] != "." and PurePosixPath(skill["path"]).name == skill["name"]
           for skill in skills):
        return [base + ["--path", *(skill["path"] for skill in skills)] + suffix]
    return [base + ["--path", skill["path"], "--name", skill["name"]] + suffix
            for skill in skills]


def run(args: argparse.Namespace) -> None:
    root, destination = project_paths(args.project_root.absolute())
    sources = read_lock(root)
    pending = {}
    for source in sources:
        pending[source["id"]] = []
        for skill in source["skills"]:
            target = destination / skill["name"]
            if os.path.lexists(target):
                verify(target, source, skill)
                print(f"Verified {skill['name']}")
            else:
                require(not args.check, f"Missing installed skill: {skill['name']}")
                pending[source["id"]].append(skill)
    if args.check:
        print("All locked skills and installation records verified (offline).")
        return
    if args.dry_run:
        for source in sources:
            skills = pending[source["id"]]
            if skills:
                stage = destination.parent / ".media-skills-dry-run" / source["id"]
                for command in commands(args.installer, source, skills, stage):
                    print(shlex.join(command))
        return
    if not any(pending.values()):
        return
    require(args.installer.is_file(), f"Official installer helper not found: {args.installer}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".media-skills-", dir=destination.parent) as temporary:
        staged = []
        for source in sources:
            skills = pending[source["id"]]
            if not skills:
                continue
            stage = Path(temporary) / source["id"]
            stage.mkdir()
            for command in commands(args.installer, source, skills, stage):
                subprocess.run(command, check=True)
            for skill in skills:
                target = stage / skill["name"]
                fingerprint = tree_sha256(target)
                validate_frontmatter(target, skill["name"])
                record = identity(source, skill) | {"tree_sha256": fingerprint}
                require(not os.path.lexists(target / RECORD), "Upstream uses reserved record filename")
                (target / RECORD).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                                             encoding="utf-8")
                staged.append((target, skill["name"]))
        # All sources must download and validate before any skill is promoted.
        project_paths(root)
        destination.mkdir(exist_ok=True)
        for _, name in staged:
            require(not os.path.lexists(destination / name), f"Destination already exists: {name}")
        moved = []
        try:
            for target, name in staged:
                target.rename(destination / name)
                moved.append((target, name))
        except OSError:
            for target, name in reversed(moved):
                (destination / name).rename(target)
            raise
        print(f"Installed {len(moved)} locked skills into {destination}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).absolute().parents[1])
    helper = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills/.system/skill-installer/scripts/install-skill-from-github.py"
    parser.add_argument("--installer", type=Path, default=helper,
                        help="Path to the official Codex installer helper")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print commands without writing or downloading")
    mode.add_argument("--check", action="store_true", help="Verify installed skills offline")
    args = parser.parse_args(argv)
    try:
        run(args)
        return 0
    except (InstallError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
