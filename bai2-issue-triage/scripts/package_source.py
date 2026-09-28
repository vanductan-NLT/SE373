"""Create a source ZIP without secrets or generated clutter."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "BTVN2_Issue_Triage_Van_Duc_Tan_24521586_source.zip"
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".playwright-cli",
    "tmp",
    "output",
}


def should_include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return not (
        any(part in EXCLUDED_PARTS for part in relative.parts)
        or path.name == ".env"
        or path.suffix in {".pyc", ".pyo"}
    )


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob("*")):
            if path.is_file() and should_include(path):
                archive.write(path, path.relative_to(ROOT))
    with ZipFile(OUTPUT) as archive:
        names = archive.namelist()
        if ".env" in names or any(name.startswith(".git/") for name in names):
            raise RuntimeError("ZIP chứa file bị cấm.")
    print(OUTPUT)


if __name__ == "__main__":
    main()
