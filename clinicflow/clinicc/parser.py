class ParseError(Exception):
    pass


STARTERS = {"let", "if", "order", "alert", "prescribe"}
CMP = ("<", ">", "<=", ">=", "==", "!=")


class Parser:
    def __init__(self, tokens):
        self.t, self.i, self.errors = tokens, 0, []

    def peek(self):
        return self.t[self.i]

    def next(self):
        tok = self.t[self.i]
        if tok.type != "EOF":
            self.i += 1
        return tok

    def match(self, type_, value=None):
        tok = self.peek()
        if tok.type == type_ and (value is None or tok.value == value):
            return self.next()
        return None

    def expect(self, type_, value=None):
        tok = self.match(type_, value)
        if tok:
            return tok
        p = self.peek()
        raise ParseError(
            f"Line {p.line}, col {p.col}: expected {value or type_} "
            f"but found {p.value or 'end of input'!r}")

    def sync(self):
        """Panic-mode recovery: skip to the next safe point."""
        start = self.i
        while self.peek().type != "EOF":
            tok = self.peek()
            if tok.type == "PUNCT" and tok.value == ";":
                self.next()
                return
            if tok.type == "KW" and tok.value in STARTERS:
                return
            if tok.type == "PUNCT" and tok.value == "}":
                if self.i == start:
                    self.next()
                return
            self.next()

    def parse(self):
        body = []
        while self.peek().type != "EOF":
            try:
                body.append(self.statement())
            except ParseError as e:
                self.errors.append(str(e))
                self.sync()
        return {"kind": "Program", "body": body}

    def block(self):
        self.expect("PUNCT", "{")
        body = []
        while self.peek().type != "EOF" and not (
                self.peek().type == "PUNCT" and self.peek().value == "}"):
            try:
                body.append(self.statement())
            except ParseError as e:
                self.errors.append(str(e))
                self.sync()
        self.expect("PUNCT", "}")
        return body

    def statement(self):
        tok = self.peek()
        if tok.type == "KW":
            if tok.value == "let":
                self.next()
                name = self.expect("ID")
                self.expect("OP", "=")
                e = self.expr()
                self.expect("PUNCT", ";")
                return {"kind": "Let", "name": name.value, "value": e, "line": tok.line}
            if tok.value == "if":
                return self.if_stmt()
            if tok.value in ("order", "alert"):
                self.next()
                s = self.expect("STRING")
                self.expect("PUNCT", ";")
                return {"kind": tok.value.capitalize(), "text": s.value.strip('"'), "line": tok.line}
            if tok.value == "prescribe":
                self.next()
                drug = self.expect("STRING")
                dose = self.expr()
                unit = self.expect("ID")
                self.expect("PUNCT", ";")
                return {"kind": "Prescribe", "drug": drug.value.strip('"'),
                        "dose": dose, "unit": unit.value, "line": tok.line}
        raise ParseError(
            f"Line {tok.line}, col {tok.col}: unexpected {tok.value or 'end of input'!r}; "
            f"a statement must start with let, if, order, alert or prescribe")

    def if_stmt(self):
        tok = self.next()
        cond = self.expr()
        self.expect("KW", "then")
        then = self.block()
        els = []
        if self.match("KW", "else"):
            if self.peek().type == "KW" and self.peek().value == "if":
                els = [self.if_stmt()]
            else:
                els = self.block()
        return {"kind": "If", "cond": cond, "then": then, "else": els, "line": tok.line}

    def expr(self):
        n = self.and_()
        while self.match("KW", "or"):
            n = {"kind": "Bin", "op": "or", "l": n, "r": self.and_()}
        return n

    def and_(self):
        n = self.not_()
        while self.match("KW", "and"):
            n = {"kind": "Bin", "op": "and", "l": n, "r": self.not_()}
        return n

    def not_(self):
        if self.match("KW", "not"):
            return {"kind": "Un", "op": "not", "e": self.not_()}
        return self.cmp()

    def cmp(self):
        n = self.add()
        tok = self.peek()
        if tok.type == "OP" and tok.value in CMP:
            self.next()
            n = {"kind": "Bin", "op": tok.value, "l": n, "r": self.add()}
        return n

    def add(self):
        n = self.mul()
        while self.peek().type == "OP" and self.peek().value in ("+", "-"):
            op = self.next().value
            n = {"kind": "Bin", "op": op, "l": n, "r": self.mul()}
        return n

    def mul(self):
        n = self.unary()
        while self.peek().type == "OP" and self.peek().value in ("*", "/"):
            op = self.next().value
            n = {"kind": "Bin", "op": op, "l": n, "r": self.unary()}
        return n

    def unary(self):
        if self.peek().type == "OP" and self.peek().value == "-":
            self.next()
            return {"kind": "Bin", "op": "-", "l": {"kind": "Num", "value": 0.0}, "r": self.unary()}
        return self.primary()

    def primary(self):
        tok = self.peek()
        if tok.type == "NUMBER":
            self.next()
            return {"kind": "Num", "value": float(tok.value)}
        if tok.type == "STRING":
            self.next()
            return {"kind": "Str", "value": tok.value.strip('"')}
        if tok.type == "KW" and tok.value in ("true", "false"):
            self.next()
            return {"kind": "Bool", "value": tok.value == "true"}
        if tok.type == "ID":
            self.next()
            return {"kind": "Var", "name": tok.value}
        if self.match("PUNCT", "("):
            e = self.expr()
            self.expect("PUNCT", ")")
            return e
        raise ParseError(
            f"Line {tok.line}, col {tok.col}: expected a value or '(' "
            f"but found {tok.value or 'end of input'!r}")


def pretty(n, d=0):
    """Indented text rendering of the parse tree (screen-reader friendly)."""
    pad = "  " * d
    if isinstance(n, list):
        return "".join(pretty(x, d) for x in n)
    k = n["kind"]
    if k == "Program":
        return "Program\n" + pretty(n["body"], 1)
    if k == "Let":
        return f"{pad}Let {n['name']}\n" + pretty(n["value"], d + 1)
    if k == "If":
        s = f"{pad}If\n{pad}  condition:\n" + pretty(n["cond"], d + 2)
        s += f"{pad}  then:\n" + pretty(n["then"], d + 2)
        if n["else"]:
            s += f"{pad}  else:\n" + pretty(n["else"], d + 2)
        return s
    if k in ("Order", "Alert"):
        return f'{pad}{k} "{n["text"]}"\n'
    if k == "Prescribe":
        return f'{pad}Prescribe "{n["drug"]}" unit={n["unit"]}\n' + pretty(n["dose"], d + 1)
    if k == "Num":
        v = n["value"]
        return f"{pad}Number {int(v) if v == int(v) else v}\n"
    if k == "Str":
        return f'{pad}Text "{n["value"]}"\n'
    if k == "Bool":
        return f"{pad}Boolean {str(n['value']).lower()}\n"
    if k == "Var":
        return f"{pad}Variable {n['name']}\n"
    if k == "Un":
        return f"{pad}Unary {n['op']}\n" + pretty(n["e"], d + 1)
    if k == "Bin":
        return f"{pad}Binary {n['op']}\n" + pretty(n["l"], d + 1) + pretty(n["r"], d + 1)
    return ""
