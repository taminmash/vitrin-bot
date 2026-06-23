# Generated Lessons

This folder contains generated lesson JSON files. Markdown files under
`source_content/<level>/` remain the single source of truth and must not be
modified by the parser.

## Parser Usage

Run the A1 parser from the repository root:

```bash
python content_parser.py
```

By default this reads:

```text
source_content/a1/*.md
```

and writes:

```text
generated_lessons/a1/unit_01.json
generated_lessons/a1/unit_02.json
...
generated_lessons/a1/unit_12.json
```

Useful options:

```bash
python content_parser.py --level a1
python content_parser.py --level a1 --source-dir source_content/a1 --output-dir generated_lessons/a1
python content_parser.py --level a1 --lessons-per-unit 6
```

`--lessons-per-unit` is only a fallback for markdown that does not include unit
markers. Prefer explicit unit headings or fields in the source content.

## Folder Structure

```text
source_content/
  a1/
    *.md

generated_lessons/
  README.md
  a1/
    unit_01.json
    unit_02.json
    ...
    unit_12.json
```

The same structure is intended to scale to future levels:

```text
source_content/a2 -> generated_lessons/a2
source_content/b1 -> generated_lessons/b1
source_content/b2 -> generated_lessons/b2
source_content/c1 -> generated_lessons/c1
source_content/c2 -> generated_lessons/c2
```

## Output Format

Each unit file is UTF-8 JSON:

```json
{
  "level": "a1",
  "unit_number": 1,
  "lesson_count": 1,
  "lessons": [
    {
      "lesson_number": 1,
      "unit_number": 1,
      "lesson_type": "lesson",
      "title": "Lesson title",
      "pronunciation": "Pronunciation text",
      "meaning_fa": "Persian meaning",
      "meaning_en": "English meaning",
      "grammar_notes": "Grammar notes",
      "examples": [
        {
          "text": "Example sentence",
          "meaning_fa": "Persian translation",
          "meaning_en": "English translation"
        }
      ],
      "audio_text": "Text reserved for a future audio generation step",
      "source": {
        "file": "source_content/a1/example.md",
        "line": 1
      }
    }
  ]
}
```

## Validation

The parser validates that:

- source markdown exists unless `--allow-empty` is used
- lesson boundaries such as `### درس ۷۱` are present
- lesson numbers are unique
- each lesson has a valid unit number
- unit numbers stay inside the expected unit range
- required text fields needed by later pipeline steps are present
- input markdown is valid UTF-8

The parser does not create cards, audio, video, Telegram publishing, or
workflow automation.
