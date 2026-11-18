"""Publication refuses changed source/bytes and safely resumes only its own draft."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile

import pytest

SPEC = importlib.util.spec_from_file_location("publishing_release", Path(__file__).parents[1] / "scripts/release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def make_candidate(tmp_path):
    root = tmp_path / "repo"; root.mkdir()
    files = {
        "pyproject.toml": '[project]\nname="amplifier-publishing"\nversion="0.1.2"\nrequires-python=">=3.13"\nlicense="MIT"\ndependencies=[]\n[project.optional-dependencies]\ntest=["pytest>=8"]\n',
        "src/amplifier_publishing/__init__.py": 'value = "selected"\n',
        "src/amplifier_publishing/store.py": 'value = "store"\n',
        "README.md": "Publishing\n", "LICENSE": "MIT\n", ".gitignore": "__pycache__/\n", "AGENTS.md": "Keep owners explicit\n",
        "uv.lock": "version = 1\n", "QUALIFICATION.json": "{}\n",
        "scripts/qualify-installed.sh": "#!/bin/sh\n", "contracts/publishing.v1.md": "Contract\n",
        "docs/VISION.md": "Vision\n", "src/amplifier_publishing/README.md": "API\n",
        "PROVENANCE.json": "{}\n", "CODE_OF_CONDUCT.md": "Conduct\n",
        "SECURITY.md": "Security\n", "SUPPORT.md": "Support\n",
        "tests/test_publishing_store.py": "def test_fixture(): assert True\n",
    }
    for name, text in {**files, ".github/workflows/package.yml": "name: fixture\n", "scripts/release.py": "# automation\n"}.items():
        path = root / name; path.parent.mkdir(exist_ok=True, parents=True); path.write_text(text)
    def git(*args):
        return release.run("git", *args, cwd=root).decode().strip()
    git("init", "-q"); git("add", ".")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "selected")
    revision = git("rev-parse", "HEAD"); git("update-ref", "refs/remotes/origin/main", revision)
    selected = release.selection(root, revision)
    dist = tmp_path / "dist"; dist.mkdir()
    wheel, sdist = release.artifact_names(selected)
    with zipfile.ZipFile(dist / wheel, "w") as archive:
        for name in ("amplifier_publishing/__init__.py", "amplifier_publishing/store.py", "amplifier_publishing/README.md"):
            archive.writestr(name, files["src/" + name])
        info = "amplifier_publishing-0.1.2.dist-info/"
        archive.writestr(info + "METADATA", "Name: amplifier-publishing\nVersion: 0.1.2\nRequires-Python: >=3.13\nLicense-Expression: MIT\nProvides-Extra: test\nRequires-Dist: pytest>=8; extra == \"test\"\n")
        archive.writestr(info + "licenses/LICENSE", files["LICENSE"])
    with tarfile.open(dist / sdist, "w:gz") as archive:
        for name, text in files.items():
            raw = text.encode(); info = tarfile.TarInfo("amplifier_publishing-0.1.2/" + name); info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
    release.seal(root, revision, dist)
    return root, revision, dist, git


@pytest.fixture
def candidate(tmp_path):
    return make_candidate(tmp_path)


def test_root_receipt_binds_full_tree_and_exact_package_inputs(candidate):
    root, revision, dist, git = candidate
    value = release.verify(root, revision, dist)
    assert value["component"] == "publishing" and value["subdirectory"] == "."
    assert value["repository"] == "microsoft/amplifier-publishing"
    assert value["revision"] == revision and value["tree"] == git("rev-parse", "HEAD^{tree}")
    assert set(value["sourceFiles"]) == {
        "pyproject.toml", "README.md", "LICENSE", ".gitignore", "AGENTS.md", "uv.lock",
        "QUALIFICATION.json", "scripts/qualify-installed.sh", "contracts/publishing.v1.md",
        "docs/VISION.md", "src/amplifier_publishing/README.md", "PROVENANCE.json",
        "CODE_OF_CONDUCT.md", "SECURITY.md", "SUPPORT.md",
        "src/amplifier_publishing/__init__.py", "src/amplifier_publishing/store.py",
        "tests/test_publishing_store.py",
    }
    assert set(value["artifacts"]) == set(release.artifact_names(value))


@pytest.mark.parametrize("fault", ["wheel-flat", "wheel-src-prefix", "wheel-missing-runtime", "source-flat"])
def test_package_files_require_exact_installed_namespace(candidate, fault):
    root, revision, dist, _ = candidate
    if fault.startswith("wheel"):
        path = next(dist.glob("*.whl"))
        with zipfile.ZipFile(path) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        raw = files.pop("amplifier_publishing/store.py")
        if fault == "wheel-flat":
            files["store.py"] = raw
        elif fault == "wheel-src-prefix":
            files["src/amplifier_publishing/store.py"] = raw
        with zipfile.ZipFile(path, "w") as archive:
            for name, raw in files.items(): archive.writestr(name, raw)
        message = "second package" if fault in {"wheel-flat", "wheel-src-prefix"} else "runtime differs"
    else:
        path = next(dist.glob("*.tar.gz"))
        with tarfile.open(path) as archive:
            files = [(member, archive.extractfile(member).read()) for member in archive.getmembers()]
        with tarfile.open(path, "w:gz") as archive:
            for member, raw in files:
                if member.name.endswith("/src/amplifier_publishing/store.py"):
                    member.name = member.name.replace("/src/amplifier_publishing/store.py", "/store.py")
                archive.addfile(member, io.BytesIO(raw))
        message = "unselected runtime code"
    with pytest.raises(ValueError, match=message):
        release.verify(root, revision, dist)


def test_unmerged_candidate_can_qualify_but_never_publish(candidate, monkeypatch):
    root, revision, dist, git = candidate
    with pytest.raises(ValueError, match="full merged"):
        release.selection(root, "main")
    (root / "new.txt").write_text("unmerged")
    git("add", "."); git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "unmerged")
    unmerged = git("rev-parse", "HEAD")
    assert release.selection(root, unmerged, qualification=True)["revision"] == unmerged
    monkeypatch.setattr(release, "api", lambda *a, **k: pytest.fail("No network before merged-source verification"))
    with pytest.raises(subprocess.CalledProcessError):
        release.publish(root, unmerged, dist)


@pytest.mark.parametrize("fault", ["wheel-payload", "source-payload", "receipt", "checksums", "unexpected-asset"])
def test_changed_local_bytes_cannot_reach_publication(candidate, monkeypatch, fault):
    root, revision, dist, _ = candidate
    if fault == "wheel-payload":
        wheel = next(dist.glob("*.whl"))
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("amplifier_publishing/__init__.py", "value='other'")
    elif fault == "source-payload":
        next(dist.glob("*.tar.gz")).write_bytes(b"not a source archive")
    elif fault == "receipt":
        value = json.loads((dist / release.RECEIPT).read_text()); value["revision"] = "f" * 40
        (dist / release.RECEIPT).write_text(json.dumps(value))
    elif fault == "checksums":
        (dist / "SHA256SUMS").write_text("wrong")
    else:
        (dist / "other.whl").write_bytes(b"unselected")
    monkeypatch.setattr(release, "api", lambda *a, **k: pytest.fail("Invalid local bytes reached GitHub"))
    with pytest.raises((ValueError, KeyError, tarfile.TarError)):
        release.publish(root, revision, dist)


class Remote:
    def __init__(self, candidate, *, exists=True, draft=False):
        self.root, self.revision, self.dist, _ = candidate
        self.tag = json.loads(next(self.dist.glob("*-source.json")).read_text())["tag"]
        self.ref = {"object": {"type": "commit", "sha": self.revision}} if exists else None
        self.release = {"id": 10, "tag_name": self.tag, "draft": draft, "prerelease": False, "assets": []} if exists else None
        self.bytes = {}; self.mutations = []; self.swap_on_upload = False
        self.hide_draft_by_tag = False
        self.reads = []
        if exists:
            for path in sorted(self.dist.iterdir()): self.add(path)

    def add(self, path):
        identity = len(self.bytes) + 1; self.bytes[identity] = path.read_bytes()
        self.release["assets"].append({"name": path.name, "id": identity})

    def api(self, path, *args, missing=False):
        if "-X" not in args:
            self.reads.append(path)
            if path.startswith("git/ref/"):
                value = self.ref
            elif path == "releases/latest":
                pytest.fail("Standalone publication must not query an application latest release")
            elif path.startswith("releases/tags/"):
                value = None if self.hide_draft_by_tag and self.release and self.release["draft"] else self.release
            elif path.startswith("releases?per_page=100&page="):
                value = [self.release] if self.release and path.endswith("page=1") else []
            elif path == "releases/10":
                value = self.release
            else:
                pytest.fail("Unexpected read: " + path)
            if value is None and not missing:
                raise RuntimeError("GitHub operation failed (HTTP 404)")
            return copy.deepcopy(value)
        self.mutations.append((path, args))
        fields = dict(value.split("=", 1) for value in args if "=" in value)
        if path == "git/refs": self.ref = {"object": {"type": "commit", "sha": fields["sha"]}}
        elif path == "releases":
            assert fields["make_latest"] == "false" and fields["draft"] == "true"
            self.release = {"id": 10, "tag_name": self.tag, "draft": True, "prerelease": False, "assets": []}
        elif path == "releases/10":
            assert fields == {"draft": "false", "make_latest": "false"}
            self.release["draft"] = False
        else: pytest.fail("Unexpected mutation")
        return copy.deepcopy(self.ref if path == "git/refs" else self.release)

    def run(self, *args, **kwargs):
        if args[:2] == ("gh", "api"):
            return self.bytes[int(args[2].rsplit("/", 1)[1])]
        assert args[:3] == ("gh", "release", "upload") and "--clobber" not in args
        self.mutations.append(("upload", args))
        for value in args[4:args.index("--repo")]: self.add(Path(value))
        if self.swap_on_upload: self.ref["object"]["sha"] = "f" * 40
        return b""

    def install(self, monkeypatch):
        original = release.run
        monkeypatch.setattr(release, "api", self.api)
        monkeypatch.setattr(release, "run", lambda *a, **k: self.run(*a, **k) if a[0] == "gh" else original(*a, **k))


def test_completed_retry_is_read_only(candidate, monkeypatch):
    remote = Remote(candidate); remote.install(monkeypatch)
    assert release.publish(*candidate[:3])["status"] == "already-published-exact-bytes"
    assert remote.mutations == []


@pytest.mark.parametrize("fault", ["wrong-tag", "missing-tag", "changed-asset", "missing-asset", "extra-asset", "prerelease"])
def test_existing_publication_conflicts_never_mutate(candidate, monkeypatch, fault):
    remote = Remote(candidate)
    if fault == "wrong-tag": remote.ref["object"]["sha"] = "f" * 40
    elif fault == "missing-tag": remote.ref = None
    elif fault == "changed-asset": remote.bytes[1] = b"changed"
    elif fault == "missing-asset": remote.release["assets"].pop()
    elif fault == "extra-asset": remote.release["assets"].append({"name": "other", "id": 99})
    else: remote.release["prerelease"] = True
    remote.install(monkeypatch)
    with pytest.raises(ValueError): release.publish(*candidate[:3])
    assert remote.mutations == []


@pytest.mark.parametrize("new", [False, True])
def test_new_or_partial_draft_uploads_only_missing_before_publication(candidate, monkeypatch, new):
    remote = Remote(candidate, exists=not new, draft=True)
    if not new: remote.release["assets"] = remote.release["assets"][:1]
    remote.install(monkeypatch)
    assert release.publish(*candidate[:3])["status"] == "published"
    assert remote.release["draft"] is False and len(remote.release["assets"]) == 4
    upload = next(args for path, args in remote.mutations if path == "upload")
    assert len(upload[4:upload.index("--repo")]) == (4 if new else 3)
    assert not any(path == "git/refs" for path, _ in remote.mutations) if not new else True


def test_tag_race_after_upload_leaves_draft_unpublished(candidate, monkeypatch):
    remote = Remote(candidate, draft=True); remote.release["assets"] = remote.release["assets"][:1]
    remote.swap_on_upload = True; remote.install(monkeypatch)
    with pytest.raises(ValueError, match="changed during"):
        release.publish(*candidate[:3])
    assert remote.release["draft"] is True


@pytest.mark.parametrize("state", ["new", "partial", "complete"])
def test_tag_404_uses_exact_draft_id_without_duplicate_creation(candidate, monkeypatch, state):
    remote = Remote(candidate, exists=state != "new", draft=True)
    remote.hide_draft_by_tag = True
    if state == "partial":
        remote.release["assets"] = remote.release["assets"][:1]
    remote.install(monkeypatch)
    assert release.publish(*candidate[:3])["status"] == "published"
    assert remote.release["draft"] is False and len(remote.release["assets"]) == 4
    assert sum(path == "releases" for path, _ in remote.mutations) == (state == "new")
    assert sum(path == "git/refs" for path, _ in remote.mutations) == (state == "new")
    assert sum(path == "upload" for path, _ in remote.mutations) == (state != "complete")
    assert remote.reads.count("releases/10") >= 3
    # Tag lookup may hide a draft; later reads must stay bound to its returned ID.
    assert remote.reads.count("releases/tags/" + remote.tag) == 1


def test_hidden_draft_on_later_page_is_reconciled(candidate, monkeypatch):
    remote = Remote(candidate, draft=True); remote.hide_draft_by_tag = True
    remote.install(monkeypatch)
    original = remote.api
    def paged(path, *args, **kwargs):
        if path == "releases?per_page=100&page=1":
            return [{"tag_name": f"unrelated-{i}"} for i in range(100)]
        if path == "releases?per_page=100&page=2":
            return [copy.deepcopy(remote.release)]
        return original(path, *args, **kwargs)
    monkeypatch.setattr(release, "api", paged)
    assert release.publish(*candidate[:3])["status"] == "published"
    assert [path for path, _ in remote.mutations] == ["releases/10"]


@pytest.mark.parametrize("fault", ["failure", "not-list", "malformed-entry", "duplicate", "duplicate-later-page", "incomplete"])
def test_failed_or_ambiguous_listing_never_creates(candidate, monkeypatch, fault):
    remote = Remote(candidate, draft=True); remote.hide_draft_by_tag = True
    remote.install(monkeypatch)
    original = remote.api
    def broken(path, *args, **kwargs):
        if path.startswith("releases?"):
            if fault == "failure":
                raise RuntimeError("Listing unavailable")
            if fault == "not-list":
                return {"message": "unavailable"}
            if fault == "malformed-entry":
                return [None]
            if fault == "duplicate":
                return [remote.release, remote.release]
            if fault == "duplicate-later-page":
                return ([remote.release] + [{"tag_name": f"unrelated-{i}"} for i in range(99)]
                        if path.endswith("page=1") else [remote.release])
            return [{"tag_name": f"unrelated-{i}"} for i in range(100)]
        return original(path, *args, **kwargs)
    monkeypatch.setattr(release, "api", broken)
    with pytest.raises((ValueError, RuntimeError)):
        release.publish(*candidate[:3])
    assert remote.mutations == []


@pytest.mark.parametrize("fault", ["wrong-ref", "missing-ref", "changed-asset", "extra-asset", "prerelease"])
def test_hidden_draft_conflicts_never_mutate(candidate, monkeypatch, fault):
    remote = Remote(candidate, draft=True); remote.hide_draft_by_tag = True
    if fault == "wrong-ref": remote.ref["object"]["sha"] = "f" * 40
    elif fault == "missing-ref": remote.ref = None
    elif fault == "changed-asset": remote.bytes[1] = b"changed"
    elif fault == "extra-asset": remote.release["assets"].append({"name": "other", "id": 99})
    else: remote.release["prerelease"] = True
    remote.install(monkeypatch)
    with pytest.raises(ValueError):
        release.publish(*candidate[:3])
    assert remote.mutations == []


@pytest.mark.parametrize("fault", ["id", "tag_name", "prerelease", "draft", "assets", "not-found"])
def test_listed_draft_requires_matching_exact_id_readback(candidate, monkeypatch, fault):
    remote = Remote(candidate, draft=True); remote.hide_draft_by_tag = True
    remote.install(monkeypatch)
    original = remote.api
    def changed(path, *args, **kwargs):
        value = original(path, *args, **kwargs)
        if path == "releases/10" and not args:
            if fault == "not-found":
                raise RuntimeError("Exact draft not found")
            value[fault] = {"id": 11, "tag_name": "other-tag", "prerelease": True,
                            "draft": "true", "assets": None}[fault]
        return value
    monkeypatch.setattr(release, "api", changed)
    with pytest.raises((ValueError, RuntimeError)):
        release.publish(*candidate[:3])
    assert remote.mutations == []


@pytest.mark.parametrize("phase", ["created", "uploaded", "published"])
def test_draft_identity_drift_stops_at_exact_id_checkpoint(candidate, monkeypatch, phase):
    remote = Remote(candidate, exists=phase != "created", draft=True)
    remote.hide_draft_by_tag = True
    remote.install(monkeypatch)
    original = remote.api
    checkpoint = {"created": 1, "uploaded": 2, "published": 3}[phase]
    def changed(path, *args, **kwargs):
        value = original(path, *args, **kwargs)
        if path == "releases/10" and not args and remote.reads.count(path) == checkpoint:
            value["id"] = 11
        return value
    monkeypatch.setattr(release, "api", changed)
    with pytest.raises(ValueError, match="identity changed"):
        release.publish(*candidate[:3])
    assert sum(path == "releases" for path, _ in remote.mutations) == (phase == "created")
    assert sum(path == "releases/10" for path, _ in remote.mutations) == (phase == "published")


@pytest.mark.parametrize("fault", ["missing-asset", "still-draft"])
def test_publication_readback_rechecks_assets_and_draft(candidate, monkeypatch, fault):
    remote = Remote(candidate, draft=True); remote.hide_draft_by_tag = True
    remote.install(monkeypatch)
    original = remote.api
    def changed(path, *args, **kwargs):
        value = original(path, *args, **kwargs)
        if path == "releases/10" and not args and remote.reads.count(path) == 3:
            if fault == "missing-asset":
                value["assets"].pop()
            elif fault == "still-draft":
                value["draft"] = True
        return value
    monkeypatch.setattr(release, "api", changed)
    with pytest.raises(ValueError):
        release.publish(*candidate[:3])
    assert [path for path, _ in remote.mutations] == ["releases/10"]


def test_api_listing_failure_is_not_an_empty_success(monkeypatch):
    calls = []
    def failed(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 1, "", "gh: unavailable (HTTP 404)" if len(calls) == 1 else "gh: unavailable (HTTP 503)")
    monkeypatch.setattr(release.subprocess, "run", failed)
    with pytest.raises(RuntimeError):
        release.find_release("publishing-v0.1.2")
    assert len(calls) == 2 and "releases?per_page=100&page=1" in calls[1][0][2]


@pytest.mark.parametrize("phase", ["create", "upload", "patch"])
def test_unknown_mutation_reply_is_not_retried(candidate, monkeypatch, phase):
    remote = Remote(candidate, exists=phase != "create", draft=True)
    remote.hide_draft_by_tag = True
    if phase == "upload":
        remote.release["assets"] = remote.release["assets"][:1]
    remote.install(monkeypatch)
    original_api, original_run = remote.api, release.run
    def uncertain_api(path, *args, **kwargs):
        value = original_api(path, *args, **kwargs)
        if "-X" in args and path == ("releases" if phase == "create" else "releases/10") and phase != "upload":
            raise RuntimeError("Unknown mutation response")
        return value
    def uncertain_run(*args, **kwargs):
        value = original_run(*args, **kwargs)
        if phase == "upload" and args[:3] == ("gh", "release", "upload"):
            raise RuntimeError("Unknown upload response")
        return value
    monkeypatch.setattr(release, "api", uncertain_api)
    monkeypatch.setattr(release, "run", uncertain_run)
    with pytest.raises(RuntimeError):
        release.publish(*candidate[:3])
    expected = {"create": ["git/refs", "releases"], "upload": ["upload"], "patch": ["releases/10"]}[phase]
    assert [path for path, _ in remote.mutations] == expected



@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt])
@pytest.mark.parametrize("phase", ["create", "upload", "patch"])
def test_explicit_retry_recovers_effect_after_failed_or_cancelled_reply(candidate, monkeypatch, phase, failure):
    remote = Remote(candidate, exists=False); remote.hide_draft_by_tag = True
    remote.install(monkeypatch)
    original_api, original_run = release.api, release.run
    def interrupted_api(path, *args, **kwargs):
        value = original_api(path, *args, **kwargs)
        if "-X" in args and path == {"create": "releases", "patch": "releases/10"}.get(phase):
            raise failure("reply not observed")
        return value
    def interrupted_run(*args, **kwargs):
        value = original_run(*args, **kwargs)
        if phase == "upload" and args[:3] == ("gh", "release", "upload"):
            raise failure("reply not observed")
        return value
    monkeypatch.setattr(release, "api", interrupted_api)
    monkeypatch.setattr(release, "run", interrupted_run)
    with pytest.raises(failure):
        release.publish(*candidate[:3])
    before = list(remote.mutations)
    assert [path for path, _ in before] == {"create": ["git/refs", "releases"], "upload": ["git/refs", "releases", "upload"], "patch": ["git/refs", "releases", "upload", "releases/10"]}[phase]
    # A separate explicit invocation reads the saved state. There is no automatic retry.
    monkeypatch.setattr(release, "api", original_api)
    monkeypatch.setattr(release, "run", original_run)
    result = release.publish(*candidate[:3])
    assert result["status"] == ("already-published-exact-bytes" if phase == "patch" else "published")
    assert remote.release["draft"] is False
    assert [path for path, _ in remote.mutations] == ["git/refs", "releases", "upload", "releases/10"]
    assert {row["name"] for row in remote.release["assets"]} == {path.name for path in candidate[2].iterdir()}


@pytest.mark.parametrize("fault", ["missing-governance", "missing-test", "extra-python", "symlink"])
def test_sdist_all_selected_inputs_and_no_unselected_code(candidate, fault):
    root, revision, dist, _ = candidate
    path = next(dist.glob("*.tar.gz"))
    with tarfile.open(path) as archive:
        rows = [(member, archive.extractfile(member).read()) for member in archive.getmembers()]
    with tarfile.open(path, "w:gz") as archive:
        for member, raw in rows:
            if fault == "missing-governance" and member.name.endswith("/SECURITY.md"): continue
            if fault == "missing-test" and member.name.endswith("/tests/test_publishing_store.py"): continue
            if fault == "symlink" and member.name.endswith("/README.md"):
                member.type = tarfile.SYMTYPE; member.linkname = "../../outside"; member.size = 0
                archive.addfile(member); continue
            archive.addfile(member, io.BytesIO(raw))
        if fault == "extra-python":
            member = tarfile.TarInfo("amplifier_publishing-0.1.2/scripts/unselected.py"); member.size = 4
            archive.addfile(member, io.BytesIO(b"pass"))
    with pytest.raises(ValueError):
        release.verify(root, revision, dist)


@pytest.mark.parametrize("fault", ["dependency", "test-constraint", "optional-test", "python", "license", "entrypoint", "second-package"])
def test_wheel_preserves_standalone_contract(candidate, fault):
    root, revision, dist, _ = candidate
    path = next(dist.glob("*.whl"))
    with zipfile.ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    info = "amplifier_publishing-0.1.2.dist-info/"
    if fault == "dependency": files[info + "METADATA"] += b"Requires-Dist: amplifier-core\n"
    elif fault == "test-constraint": files[info + "METADATA"] = files[info + "METADATA"].replace(b"pytest>=8", b"pytest>=9")
    elif fault == "optional-test": files[info + "METADATA"] = files[info + "METADATA"].replace(b'pytest>=8; extra == "test"', b"pytest>=8")
    elif fault == "python": files[info + "METADATA"] = files[info + "METADATA"].replace(b">=3.13", b">=3.14")
    elif fault == "license": files[info + "licenses/LICENSE"] = b"other"
    elif fault == "entrypoint": files[info + "entry_points.txt"] = b"[console_scripts]\nother=x:main\n"
    else: files["other/__init__.py"] = b""
    with zipfile.ZipFile(path, "w") as archive:
        for name, raw in files.items(): archive.writestr(name, raw)
    with pytest.raises(ValueError):
        release.verify(root, revision, dist)


