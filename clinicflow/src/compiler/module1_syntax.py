import re
from dataclasses import dataclass

KEYWORDS = {"set", "if", "then", "and", "or", "not", "order", "alert", "prescribe"}

TOKEN_RE = re.compile(r"""
    (?P<SKIP>\s+|\#[^\n]*)
  | (?P<NUMBER>\d+\.?\d*)
  | (?P<STRING>"[^"\n]*")
  | (?P<IDENT>[A-Za-z_]\w*)
  | (?P<OPERATOR>>=|<=|==|!=|[><=+\-*/()])
  | (?P<BAD>.)
""", re.X)


@dataclass
class Token:
    type: str
    value: str
    line: int
    col: int


def num_str(v):
    return f"{v:g}"


def lex(src):
    toks, errs = [], []
    for m in TOKEN_RE.finditer(src):
        kind, text = m.lastgroup, m.group()
        if kind == "SKIP":
            continue
        line = src.count("\n", 0, m.start()) + 1
        col = m.start() - (src.rfind("\n", 0, m.start()) + 1) + 1
        if kind == "BAD":
            errs.append(f"Line {line}, col {col}: unexpected character {text!r}")
            continue
        if kind == "IDENT" and text in KEYWORDS:
            kind = "KEYWORD"
        toks.append(Token(kind, text, line, col))
    return toks, errs


class SyntaxErr(Exception):
    def __init__(self, msg, line):
        super().__init__(f"Line {line}: {msg}")


class Parser:
    """Recursive-descent parser.
    program -> stmt*
    stmt    -> 'set' IDENT '=' expr | 'if' expr 'then' action
    action  -> ('order'|'prescribe') IDENT | 'alert' STRING
    expr    -> or -> and -> comparison -> add -> mul -> unary -> primary
    """

    def __init__(self, toks):
        self.t, self.p = toks, 0

    def peek(self):
        return self.t[self.p] if self.p < len(self.t) else None

    def at(self, *vals):
        k = self.peek()
        return k is not None and k.type in ("KEYWORD", "OPERATOR") and k.value in vals

    def next(self):
        self.p += 1
        return self.t[self.p - 1]

    def fail(self, msg):
        k = self.peek() or self.t[-1]
        raise SyntaxErr(msg, k.line)

    def expect(self, val):
        if self.at(val):
            return self.next()
        k = self.peek()
        self.fail(f"expected '{val}'" + (f" but found '{k.value}'" if k else " but reached end of input"))

    def expect_type(self, typ):
        k = self.peek()
        if k and k.type == typ:
            return self.next()
        self.fail(f"expected {typ.lower()}")

    def binary(self, sub, ops):
        left = sub()
        while self.at(*ops):
            op = self.next().value
            left = ("bin", op, left, sub())
        return left

    def expr(self): return self.binary(self.and_, ("or",))
    def and_(self): return self.binary(self.cmp, ("and",))
    def cmp(self): return self.binary(self.add, (">", "<", ">=", "<=", "==", "!="))
    def add(self): return self.binary(self.mul, ("+", "-"))
    def mul(self): return self.binary(self.unary, ("*", "/"))

    def unary(self):
        if self.at("not"):
            self.next()
            return ("not", self.unary())
        if self.at("-"):
            self.next()
            return ("bin", "-", ("num", 0.0), self.unary())
        return self.primary()

    def primary(self):
        k = self.peek()
        if k is None:
            self.fail("unexpected end of expression")
        if k.type == "NUMBER":
            self.next()
            return ("num", float(k.value))
        if k.type == "IDENT":
            self.next()
            return ("id", k.value)
        if self.at("("):
            self.next()
            e = self.expr()
            self.expect(")")
            return e
        self.fail(f"unexpected '{k.value}' in expression")

    def stmt(self):
        k = self.peek()
        if self.at("set"):
            self.next()
            name = self.expect_type("IDENT").value
            self.expect("=")
            return {"t": "set", "name": name, "e": self.expr(), "line": k.line}
        if self.at("if"):
            self.next()
            cond = self.expr()
            self.expect("then")
            if not self.at("order", "prescribe", "alert"):
                self.fail("expected order, prescribe or alert after 'then'")
            kind = self.next().value
            arg = (self.expect_type("STRING").value.strip('"') if kind == "alert"
                   else self.expect_type("IDENT").value)
            return {"t": "if", "c": cond, "k": kind, "arg": arg, "line": k.line}
        self.fail(f"a statement must start with 'set' or 'if', found '{k.value}'")


def parse(toks):
    ps, prog, errs = Parser(toks), [], []
    while ps.p < len(toks):
        try:
            prog.append(ps.stmt())
        except SyntaxErr as e:           # panic-mode recovery
            errs.append(str(e))
            while ps.p < len(toks) and not (toks[ps.p].type == "KEYWORD"
                                            and toks[ps.p].value in ("set", "if")):
                ps.p += 1
    return prog, errs


def _tree(e, d=0):
    pad = "  " * d
    if e[0] == "num": return f"{pad}Num {num_str(e[1])}\n"
    if e[0] == "id": return f"{pad}Var {e[1]}\n"
    if e[0] == "not": return f"{pad}Not\n" + _tree(e[1], d + 1)
    return f"{pad}BinOp {e[1]}\n" + _tree(e[2], d + 1) + _tree(e[3], d + 1)


def ast_to_text(prog):
    out = ""
    for s in prog:
        if s["t"] == "set":
            out += f"Set {s['name']}\n" + _tree(s["e"], 1)
        else:
            out += "If\n  Condition\n" + _tree(s["c"], 2) + f"  Action {s['k']} -> {s['arg']}\n"
        out += "\n"
    return out
