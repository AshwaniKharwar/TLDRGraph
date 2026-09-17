import subprocess
import os

from tldrgraph.source_inventory import build_source_inventory


def test_non_git_inventory_skips_generated_dependencies_and_binary(tmp_path):
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "blob.dat").write_bytes(b"abc\0def")
    (tmp_path / ".tldrgraph").mkdir()
    (tmp_path / ".tldrgraph" / "old.json").write_text("{}", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("ignored", encoding="utf-8")
    result = build_source_inventory(str(tmp_path))
    assert [item["path"] for item in result["files"]] == ["main.py"]


def test_hash_changes_with_path_or_content(source_repo):
    before = build_source_inventory(str(source_repo))["source_hash"]
    (source_repo / "app.py").write_text("print('changed')\n", encoding="utf-8")
    assert build_source_inventory(str(source_repo))["source_hash"] != before


def test_git_inventory_includes_untracked_and_honors_gitignore(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    (tmp_path / "tracked.py").write_text("tracked\n", encoding="utf-8")
    (tmp_path / "new.py").write_text("new\n", encoding="utf-8")
    (tmp_path / "ignored.py").write_text("ignored\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", ".gitignore", "tracked.py"], check=True)
    paths = {item["path"] for item in build_source_inventory(str(tmp_path))["files"]}
    assert {".gitignore", "tracked.py", "new.py"} <= paths
    assert "ignored.py" not in paths


def test_inventory_does_not_follow_symlinks_outside_repository(tmp_path):
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        os.symlink(outside, link)
    except OSError:
        return
    assert "link.txt" not in {item["path"] for item in build_source_inventory(str(tmp_path))["files"]}
