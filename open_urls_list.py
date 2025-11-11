"""Utility to open batches of image URLs in Floorp.

This script reads a list of URLs from ``urls.txt``, filters out entries that
should not be opened (existing files or excluded extensions), launches Floorp
to open the remaining URLs in batches, then truncates the URL file.  The script
waits for Floorp to exit and propagates its exit code.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import TypeVar
from urllib.parse import urlsplit, unquote


DEFAULT_FILEPATH = Path("/home/youruser/dir/urls.txt")
CHECK_DIR = Path("/home/youruser/dir")
BATCH_SIZE = 10
BATCH_DELAY_SECONDS = 60
FLOORP_PATH = Path("/usr/bin/floorp")
EXCLUDED_EXTENSIONS = {".webp", ".tiff", ".bmp"}

T = TypeVar("T")


def read_url_file(path: Path = DEFAULT_FILEPATH) -> list[str]:
    """Return a list of unique, non-empty URLs from ``path``.

    Lines are stripped of whitespace, blanks are dropped, and duplicate values
    are removed while preserving their original order.  If ``path`` does not
    exist, the function prints ``"file not found"`` and returns an empty list.
    """

    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        print("file not found")
        return []

    seen: set[str] = set()
    urls: list[str] = []
    for line in raw_lines:
        cleaned = line.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        urls.append(cleaned)
    return urls


def list_existing_filenames(check_dir: Path = CHECK_DIR) -> set[str]:
    """Return filenames in ``check_dir`` that do not have excluded suffixes."""

    filenames: set[str] = set()
    for entry in check_dir.iterdir():
        if not entry.is_file():
            continue
        suffix = entry.suffix.lower()
        if suffix in EXCLUDED_EXTENSIONS:
            continue
        filenames.add(entry.name)
    return filenames


def extract_url_basename(url: str) -> str:
    """Return the final path segment of ``url``'s path component."""

    try:
        parts = urlsplit(url)
    except ValueError:
        return ""

    path = parts.path
    if not path or "/" not in path:
        return ""

    basename = path.rsplit("/", 1)[-1]
    if not basename:
        return ""
    return unquote(basename)


def filename_matches_existing(name: str, existing: set[str]) -> bool:
    """Return ``True`` if ``name`` exactly matches an existing filename."""

    if not name:
        return False
    return name in existing


def filter_urls_by_existing_images(
    urls: list[str], existing_filenames: set[str]
) -> list[str]:
    """Remove URLs whose basenames match entries in ``existing_filenames``."""

    filtered: list[str] = []
    for url in urls:
        basename = extract_url_basename(url)
        if filename_matches_existing(basename, existing_filenames):
            continue
        filtered.append(url)
    return filtered


def chunked(sequence: Sequence[T], size: int) -> Iterator[list[T]]:
    """Yield consecutive chunks of ``sequence`` of length ``size``."""

    if size <= 0:
        raise ValueError("size must be positive")

    seq_len = len(sequence)
    for index in range(0, seq_len, size):
        yield list(sequence[index : index + size])


def launch_floorp_initial(
    urls: list[str], floorp_path: Path = FLOORP_PATH
) -> subprocess.Popen[bytes]:
    """Launch a new Floorp instance with ``urls`` and return its process."""

    if not urls:
        raise ValueError("urls must not be empty")

    command = [str(floorp_path), "--new-instance", *urls]
    try:
        return subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, OSError) as exc:  # pragma: no cover - subprocess failure
        raise RuntimeError("Floorp launch failed") from exc


def launch_floorp_additional_batch(
    urls: list[str], floorp_path: Path = FLOORP_PATH
) -> None:
    """Launch Floorp to open ``urls`` as new tabs in the existing instance."""

    if not urls:
        return

    command = [str(floorp_path), "--new-tab", *urls]
    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, OSError) as exc:  # pragma: no cover - subprocess failure
        raise RuntimeError("Floorp launch failed") from exc


def wait_for_browser_close(proc: subprocess.Popen[bytes]) -> int:
    """Wait for ``proc`` to exit and return its exit code."""

    if proc is None:
        raise ValueError("process handle is required")
    try:
        return proc.wait()
    except OSError as exc:  # pragma: no cover - unexpected failure
        raise RuntimeError("Failed while waiting for Floorp") from exc


def clear_file(path: Path) -> None:
    """Truncate the file at ``path`` to zero bytes (creating it if needed)."""

    if path.is_dir():
        raise ValueError("path must not be a directory")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem failure
        raise RuntimeError("Failed to clear URL file") from exc


def main() -> int:
    """Run the URL-opening workflow and return an exit status."""

    url_file = DEFAULT_FILEPATH

    try:
        urls = read_url_file(url_file)
    except OSError as exc:
        print(str(exc))
        return 1

    if not urls:
        if not url_file.exists():
            return 1
        print("no URLs in file")
        return 0

    urls_without_excluded: list[str] = []
    for url in urls:
        basename = extract_url_basename(url)
        if basename:
            suffix = Path(basename).suffix.lower()
            if suffix in EXCLUDED_EXTENSIONS:
                continue
        urls_without_excluded.append(url)

    if not urls_without_excluded:
        print("no URLs to open after filtering")
        return 0

    try:
        existing_filenames = list_existing_filenames(CHECK_DIR)
    except OSError as exc:
        print(str(exc))
        return 1

    urls_to_open = filter_urls_by_existing_images(
        urls_without_excluded, existing_filenames
    )

    if not urls_to_open:
        print("no URLs to open after filtering")
        return 0

    batches = list(chunked(urls_to_open, BATCH_SIZE))
    first_batch = batches[0]

    try:
        browser_proc = launch_floorp_initial(first_batch, FLOORP_PATH)
    except (RuntimeError, ValueError) as exc:
        print(str(exc))
        return 1

    try:
        for batch in batches[1:]:
            time.sleep(BATCH_DELAY_SECONDS)
            try:
                launch_floorp_additional_batch(batch, FLOORP_PATH)
            except RuntimeError as exc:
                print(str(exc))
                return 1

        try:
            clear_file(url_file)
        except (RuntimeError, ValueError) as exc:
            print(str(exc))
            return 1

        return wait_for_browser_close(browser_proc)
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
