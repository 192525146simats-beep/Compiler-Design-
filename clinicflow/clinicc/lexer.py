import re
from dataclasses import dataclass

KEYWORDS = {"let", "if", "then", "else", "order", "alert", "prescribe",
            "and", "or", "not", "true", "false"}

TOKEN_SPEC = [
    ("COMMENT", r"//[^\n]*"),
    ("NUMBER", r"\d+(\.\d+)?"),
    ("STRING", r'"[^"\n]*"'),
    ("ID", r"[A-Za-z_][A-Za-z_0-9]*"),
    ("OP", r"==|!=|<=|>=|[<>+\-*/=]"),
    ("PUNCT", r"[{}();,]"),
    ("NEWLINE", r"\n"),
    ("SKIP", r"[ \t\r]+"),
    ("MISMATCH", r"."),
]
MASTER = re.compile("|".join(f"(?P<{n}>{p})" for n, p in TOKEN_SPEC))


@dataclass
class Token:
    type: str
    value: str
    line: int
    col: int


def tokenize(src: str):
    tokens, errors = [], []
    line, line_start = 1, 0
    for m in MASTER.finditer(src):
        kind, val = m.lastgroup, m.group()
        col = m.start() - line_start + 1
        if kind == "NEWLINE":
            line += 1
            line_start = m.end()
            continue
        if kind in ("SKIP", "COMMENT"):
            continue
        if kind == "MISMATCH":
            errors.append(f"Line {line}, col {col}: unexpected character {val!r}")
            continue
        if kind == "ID" and val in KEYWORDS:
            kind = "KW"
        tokens.append(Token(kind, val, line, col))
    tokens.append(Token("EOF", "", line, 0))
    return tokens, errors
