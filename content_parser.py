"""Parse Spainvitrin markdown lessons into generated JSON units.

The markdown files are the source of truth. This script only reads from
``source_content/<level>`` and writes generated JSON under
``generated_lessons/<level>``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
DEFAULT_LEVEL = "a1"
DEFAULT_EXPECTED_UNITS = 12

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
LESSON_HEADING_RE = re.compile(r"^#{1,6}\s*درس\s+([۰-۹٠-٩\d]+)(?:\s*[:：\-–—]\s*(.+))?\s*$", re.I)
UNIT_HEADING_RE = re.compile(
    r"^#{1,6}\s*(?:واحد|یونیت|unit)\s+([۰-۹٠-٩\d]+)(?:\s*[:：\-–—]\s*(.+))?\s*$",
    re.I,
)
KEY_VALUE_RE = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?([^:\n：]+?)(?:\*\*)?\s*[:：]\s*(.*)$")
MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")

FIELD_ALIASES = {
    "unit_number": {
        "unit",
        "unit_number",
        "unit number",
        "واحد",
        "شماره واحد",
        "یونیت",
    },
    "lesson_type": {
        "type",
        "lesson type",
        "lesson_type",
        "نوع",
        "نوع درس",
    },
    "title": {
        "title",
        "عنوان",
        "موضوع",
    },
    "pronunciation": {
        "pronunciation",
        "تلفظ",
        "آوانویسی",
        "آوا",
    },
    "meaning_fa": {
        "meaning fa",
        "meaning_fa",
        "persian meaning",
        "معنی فارسی",
        "ترجمه فارسی",
        "معنی",
    },
    "meaning_en": {
        "meaning en",
        "meaning_en",
        "english meaning",
        "ترجمه انگلیسی",
        "معنی انگلیسی",
    },
    "grammar_notes": {
        "grammar",
        "grammar notes",
        "grammar_notes",
        "گرامر",
        "نکات گرامری",
        "نکته گرامری",
    },
    "examples": {
        "examples",
        "example",
        "مثال",
        "مثال‌ها",
        "مثال ها",
        "نمونه",
    },
    "audio_text": {
        "audio",
        "audio text",
        "audio_text",
        "متن صوتی",
        "متن صدا",
        "متن برای صدا",
    },
}


class ParserError(Exception):
    """Raised when source content cannot be parsed safely."""


@dataclass
class SourceLine:
    text: str
    path: Path
    number: int


@dataclass
class LessonBlock:
    lesson_number: int
    heading_title: str
    source_file: Path
    start_line: int
    lines: list[SourceLine] = field(default_factory=list)
    current_unit: int | None = None


def normalize_digits(value: str) -> str:
    return value.translate(PERSIAN_DIGITS)


def parse_int(value: str, *, context: str) -> int:
    normalized = normalize_digits(value)
    match = re.search(r"\d+", normalized)
    if not match:
        raise ParserError(f"Expected a number in {context!r}, got {value!r}.")
    return int(match.group(0))


def normalize_key(value: str) -> str:
    value = value.strip().strip("*").strip()
    value = re.sub(r"\s+", " ", value)
    return normalize_digits(value).lower()


def canonical_field(key: str) -> str | None:
    normalized = normalize_key(key)
    for field_name, aliases in FIELD_ALIASES.items():
        if normalized in {normalize_key(alias) for alias in aliases}:
            return field_name
    return None


def read_source_lines(markdown_files: Iterable[Path]) -> list[SourceLine]:
    lines: list[SourceLine] = []
    for path in markdown_files:
        try:
            content = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ParserError(f"{path} is not valid UTF-8: {exc}") from exc
        for index, text in enumerate(content.splitlines(), start=1):
            lines.append(SourceLine(text=text.rstrip(), path=path, number=index))
        lines.append(SourceLine(text="", path=path, number=index + 1 if content else 1))
    return lines


def collect_lesson_blocks(markdown_files: list[Path]) -> list[LessonBlock]:
    source_lines = read_source_lines(markdown_files)
    lessons: list[LessonBlock] = []
    active_lesson: LessonBlock | None = None
    current_unit: int | None = None

    for line in source_lines:
        unit_match = UNIT_HEADING_RE.match(line.text)
        if unit_match:
            current_unit = parse_int(unit_match.group(1), context=f"{line.path}:{line.number}")
            if active_lesson is not None:
                active_lesson.lines.append(line)
            continue

        lesson_match = LESSON_HEADING_RE.match(line.text)
        if lesson_match:
            active_lesson = LessonBlock(
                lesson_number=parse_int(lesson_match.group(1), context=f"{line.path}:{line.number}"),
                heading_title=(lesson_match.group(2) or "").strip(),
                source_file=line.path,
                start_line=line.number,
                current_unit=current_unit,
            )
            lessons.append(active_lesson)
            continue

        if active_lesson is not None:
            active_lesson.lines.append(line)

    return lessons


def split_into_sections(lines: list[SourceLine]) -> tuple[dict[str, list[str]], dict[str, str]]:
    sections: dict[str, list[str]] = {"body": []}
    inline_fields: dict[str, str] = {}
    active_section = "body"

    for line in lines:
        text = line.text.strip()
        if not text:
            if active_section in sections and sections[active_section]:
                sections[active_section].append("")
            continue

        heading_match = MARKDOWN_HEADING_RE.match(text)
        if heading_match:
            field_name = canonical_field(heading_match.group(1))
            if field_name is not None:
                active_section = field_name
                sections.setdefault(active_section, [])
                continue

        key_value_match = KEY_VALUE_RE.match(text)
        if key_value_match:
            field_name = canonical_field(key_value_match.group(1))
            if active_section == "examples" and field_name != "examples":
                sections.setdefault(active_section, []).append(line.text)
                continue
            if field_name is not None:
                value = key_value_match.group(2).strip()
                if value:
                    if field_name in {"grammar_notes", "examples", "audio_text"}:
                        sections.setdefault(field_name, []).append(value)
                    else:
                        inline_fields[field_name] = value
                active_section = field_name
                sections.setdefault(active_section, [])
                continue

        sections.setdefault(active_section, []).append(line.text)

    return sections, inline_fields


def clean_text(lines: list[str]) -> str:
    text = "\n".join(line.rstrip() for line in lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def parse_examples(lines: list[str]) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    def finish_current() -> None:
        nonlocal current
        if current and any(value.strip() for value in current.values()):
            examples.append({key: value.strip() for key, value in current.items() if value.strip()})
        current = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            finish_current()
            continue

        bullet_match = re.match(r"^[-*]\s+(.+)$", line)
        if bullet_match:
            finish_current()
            current = {"text": bullet_match.group(1).strip()}
            continue

        key_value_match = KEY_VALUE_RE.match(line)
        if key_value_match:
            field_name = canonical_field(key_value_match.group(1)) or normalize_key(key_value_match.group(1)).replace(" ", "_")
            if current is None:
                current = {}
            current[field_name] = key_value_match.group(2).strip()
            continue

        if current is None:
            current = {"text": line}
        else:
            current["text"] = f"{current.get('text', '')}\n{line}".strip()

    finish_current()
    return examples


def build_audio_text(title: str, pronunciation: str, examples: list[dict[str, str]]) -> str:
    parts = [title, pronunciation]
    parts.extend(example.get("text", "") for example in examples)
    return "\n".join(part for part in parts if part).strip()


def parse_lesson(block: LessonBlock, *, lessons_per_unit: int | None) -> dict[str, object]:
    sections, inline_fields = split_into_sections(block.lines)

    title = inline_fields.get("title") or block.heading_title
    pronunciation = inline_fields.get("pronunciation") or clean_text(sections.get("pronunciation", []))
    meaning_fa = inline_fields.get("meaning_fa") or clean_text(sections.get("meaning_fa", []))
    meaning_en = inline_fields.get("meaning_en") or clean_text(sections.get("meaning_en", []))
    grammar_notes = clean_text(sections.get("grammar_notes", []))
    examples = parse_examples(sections.get("examples", []))
    audio_text = clean_text(sections.get("audio_text", [])) or build_audio_text(title, pronunciation, examples)

    unit_number = block.current_unit
    if "unit_number" in inline_fields:
        unit_number = parse_int(inline_fields["unit_number"], context=f"{block.source_file}:{block.start_line}")
    elif unit_number is None and lessons_per_unit:
        unit_number = ((block.lesson_number - 1) // lessons_per_unit) + 1

    lesson_type = inline_fields.get("lesson_type") or "lesson"

    try:
        source_file = block.source_file.relative_to(ROOT).as_posix()
    except ValueError:
        source_file = block.source_file.as_posix()

    lesson = {
        "lesson_number": block.lesson_number,
        "unit_number": unit_number,
        "lesson_type": lesson_type,
        "title": title,
        "pronunciation": pronunciation,
        "meaning_fa": meaning_fa,
        "meaning_en": meaning_en,
        "grammar_notes": grammar_notes,
        "examples": examples,
        "audio_text": audio_text,
        "source": {
            "file": source_file,
            "line": block.start_line,
        },
    }
    return lesson


def validate_lessons(lessons: list[dict[str, object]], *, expected_units: int) -> list[str]:
    errors: list[str] = []
    seen_lessons: set[int] = set()

    for lesson in lessons:
        lesson_number = lesson["lesson_number"]
        unit_number = lesson["unit_number"]
        source = lesson["source"]

        if lesson_number in seen_lessons:
            errors.append(f"Duplicate lesson number {lesson_number} at {source['file']}:{source['line']}.")
        seen_lessons.add(int(lesson_number))

        if unit_number is None:
            errors.append(
                f"Lesson {lesson_number} has no unit number at {source['file']}:{source['line']}. "
                "Add a unit heading/field or run with --lessons-per-unit."
            )
        elif not 1 <= int(unit_number) <= expected_units:
            errors.append(
                f"Lesson {lesson_number} has unit {unit_number}; expected 1..{expected_units}."
            )

        for field_name in ("title", "audio_text"):
            if not str(lesson.get(field_name, "")).strip():
                errors.append(f"Lesson {lesson_number} is missing required field {field_name}.")

    return errors


def write_unit_files(
    lessons: list[dict[str, object]],
    *,
    output_dir: Path,
    level: str,
    expected_units: int,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    lessons_by_unit: dict[int, list[dict[str, object]]] = {unit: [] for unit in range(1, expected_units + 1)}
    for lesson in lessons:
        unit_number = int(lesson["unit_number"])
        lessons_by_unit.setdefault(unit_number, []).append(lesson)

    written: list[Path] = []
    for unit_number in range(1, expected_units + 1):
        unit_lessons = sorted(lessons_by_unit.get(unit_number, []), key=lambda item: int(item["lesson_number"]))
        payload = {
            "level": level,
            "unit_number": unit_number,
            "lesson_count": len(unit_lessons),
            "lessons": unit_lessons,
        }
        path = output_dir / f"unit_{unit_number:02d}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


def parse_content(
    *,
    source_dir: Path,
    output_dir: Path,
    level: str,
    expected_units: int,
    lessons_per_unit: int | None,
    allow_empty: bool,
) -> tuple[list[dict[str, object]], list[Path]]:
    if not source_dir.exists():
        if allow_empty:
            return [], write_unit_files([], output_dir=output_dir, level=level, expected_units=expected_units)
        raise ParserError(f"Source directory does not exist: {source_dir}")

    markdown_files = sorted(source_dir.glob("*.md"))
    if not markdown_files:
        if allow_empty:
            return [], write_unit_files([], output_dir=output_dir, level=level, expected_units=expected_units)
        raise ParserError(f"No markdown files found in {source_dir}")

    blocks = collect_lesson_blocks(markdown_files)
    if not blocks:
        raise ParserError(f"No lesson headings like '### درس ۷۱' found in {source_dir}.")

    lessons = [parse_lesson(block, lessons_per_unit=lessons_per_unit) for block in blocks]
    errors = validate_lessons(lessons, expected_units=expected_units)
    if errors:
        raise ParserError("Validation failed:\n- " + "\n- ".join(errors))

    written = write_unit_files(lessons, output_dir=output_dir, level=level, expected_units=expected_units)
    return lessons, written


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse markdown language lessons into unit JSON files.")
    parser.add_argument("--level", default=DEFAULT_LEVEL, help="Level to parse, for example a1 or b2.")
    parser.add_argument("--source-dir", type=Path, help="Markdown source directory.")
    parser.add_argument("--output-dir", type=Path, help="Generated JSON output directory.")
    parser.add_argument("--expected-units", type=int, default=DEFAULT_EXPECTED_UNITS)
    parser.add_argument(
        "--lessons-per-unit",
        type=int,
        default=None,
        help="Optional fallback for deriving unit numbers when markdown has no unit markers.",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Create empty unit files when source markdown is not present. Intended for scaffolding only.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_arg_parser().parse_args(argv)
    level = args.level.lower()
    source_dir = args.source_dir or ROOT / "source_content" / level
    output_dir = args.output_dir or ROOT / "generated_lessons" / level

    try:
        lessons, written = parse_content(
            source_dir=source_dir,
            output_dir=output_dir,
            level=level,
            expected_units=args.expected_units,
            lessons_per_unit=args.lessons_per_unit,
            allow_empty=args.allow_empty,
        )
    except ParserError as exc:
        print(f"content_parser error: {exc}", file=sys.stderr)
        return 1

    units = sorted({int(lesson["unit_number"]) for lesson in lessons if lesson["unit_number"] is not None})
    print(f"Parsed {len(lessons)} lessons for {level.upper()}.")
    print(f"Detected units: {', '.join(f'{unit:02d}' for unit in units) if units else 'none'}.")
    print(f"Wrote {len(written)} unit files to {output_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
