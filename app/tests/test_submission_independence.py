from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {".css", ".html", ".js", ".json", ".md", ".mmd", ".py", ".sh", ".toml", ".yaml", ".yml"}


def assert_repository_has_no_sibling_references(forbidden: tuple[str, ...]) -> None:
    failures: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for term in forbidden:
            if term in text:
                failures.append(f"{path.relative_to(ROOT)}: {term}")
    assert not failures, "\n".join(failures)


def test_repository_contains_no_sibling_project_references() -> None:
    assert_repository_has_no_sibling_references((
        " ".join(("Day", "Three")),
        "-".join(("day", "three")),
        "Down" + "stream",
    ))

