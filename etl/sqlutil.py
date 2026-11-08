import re
from pathlib import Path

_MARK = re.compile(r"^@@[ \t]*(\S*)[ \t]*$", re.MULTILINE)


def load_statements(path: Path) -> list[tuple[str, str]]:
    text = Path(path).read_text(encoding="utf-8")
    marks = list(_MARK.finditer(text))
    first_end = marks[0].start() if marks else len(text)
    chunks = [("stmt_0", text[:first_end])]
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        chunks.append((m.group(1) or f"stmt_{i + 1}", text[m.end():end]))
    return [(name, body.strip()) for name, body in chunks if body.strip()]
