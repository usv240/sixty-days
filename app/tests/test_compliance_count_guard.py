"""The documented-test-count guard must be able to fail.

It could not, for as long as it existed. The lookahead in its regex was written through a heredoc,
"\b" arrived in the file as a literal backspace, and the pattern demanded a character that occurs
in no document. It matched nothing, found nothing stale, and reported PASS -- which is worse than
having no check, because a green line was standing in for the thing not being checked.

So the guard is tested the only way a guard can be: by showing it catches a document that lies.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from verify_rules_compliance import _claimed_counts  # noqa: E402


def write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_a_stale_count_is_found(tmp_path: Path) -> None:
    doc = write(tmp_path, "README.md", "| Standalone automated tests | **123 passed** |\n")
    assert _claimed_counts(doc) == [("123", 1)]


def test_the_counts_this_repository_actually_writes_are_all_recognised(tmp_path: Path) -> None:
    # Every shape in use across the repository, so a reworded claim cannot slip out of scope
    # unnoticed.
    body = "\n".join([
        "| Standalone automated tests | **361 passed** |",
        "- Standalone tests: 361 passed",
        "- [x] 361 standalone tests",
        "- standalone repository: 361 tests; this suite is the submission authority",
        "The standalone completion baseline is 361 tests, accessibility green",
        "- The standalone repository passes 361 tests.",
        "| Standalone test suite | 361 passed | python -m pytest -q |",
    ])
    doc = write(tmp_path, "SPREAD.md", body)
    assert [n for n, _ in _claimed_counts(doc)] == ["361"] * 7


def test_a_different_suite_is_left_alone(tmp_path: Path) -> None:
    # The combined integration workspace has its own count and always will. Only a line that names
    # the standalone suite is this guard's business.
    doc = write(tmp_path, "TECHNICAL_DESIGN.md",
                "The combined integration workspace currently has 300 tests; never substitute it.\n")
    assert _claimed_counts(doc) == []


def test_prose_without_a_count_is_ignored(tmp_path: Path) -> None:
    doc = write(tmp_path, "NOTES.md", "The standalone repository is the submission authority.\n")
    assert _claimed_counts(doc) == []
