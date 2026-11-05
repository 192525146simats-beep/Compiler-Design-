from dataclasses import dataclass

BINOPS = {
    "+": lambda a, b: a + b, "-": lambda a, b: a - b,
    "*": lambda a, b: a * b, "/": lambda a, b: a / b,
    "<": lambda a, b: a < b, ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
    "and": lambda a, b: a and b, "or": lambda a, b: a or b,
}


@dataclass(frozen=True)
class Const:
    value: object


@dataclass(frozen=True)
class Instr:
    op: str
    arg1: object = None
    arg2: object = None
    res: object = None


def fmt(x):
    if isinstance(x, Const):
        v = x.value
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, float):
            return str(int(v)) if v == int(v) else f"{v:g}"
        return f'"{v}"'
    return "" if x is None else str(x)


def to_text(i: Instr) -> str:
    if i.op == "assign":
        return f"{i.res} = {fmt(i.arg1)}"
    if i.op in BINOPS:
        return f"{i.res} = {fmt(i.arg1)} {i.op} {fmt(i.arg2)}"
    if i.op == "not":
        return f"{i.res} = not {fmt(i.arg1)}"
    if i.op == "jz":
        return f"ifFalse {fmt(i.arg1)} goto {i.res}"
    if i.op == "jmp":
        return f"goto {i.res}"
    if i.op == "label":
        return f"{i.res}:"
    if i.op in ("order", "alert"):
        return f'{i.op} "{i.arg1}"'
    if i.op == "rx":
        return f'prescribe "{i.arg1}" {fmt(i.arg2)} {i.res}'
    return i.op


def listing(code):
    return "\n".join(f"{n:02d}  {to_text(i)}" for n, i in enumerate(code)) or "(empty program)"


def rows(code):
    return [{"#": n, "Op": i.op,
             "Arg 1": str(i.arg1) if i.op in ("order", "alert", "rx") else fmt(i.arg1),
             "Arg 2": fmt(i.arg2), "Result": "" if i.res is None else str(i.res)}
            for n, i in enumerate(code)]


class IRGen:
    def __init__(self):
        self.code, self.nt, self.nl = [], 0, 0

    def temp(self):
        self.nt += 1
        return f"t{self.nt}"

    def label(self):
        self.nl += 1
        return f"L{self.nl}"

    def emit(self, op, a=None, b=None, r=None):
        self.code.append(Instr(op, a, b, r))

    def expr(self, e):
        k = e["kind"]
        if k in ("Num", "Str", "Bool"):
            return Const(e["value"])
        if k == "Var":
            return e["name"]
        if k == "Un":
            a = self.expr(e["e"])
            t = self.temp()
            self.emit("not", a, None, t)
            return t
        l, r = self.expr(e["l"]), self.expr(e["r"])
        t = self.temp()
        self.emit(e["op"], l, r, t)
        return t

    def stmt(self, s):
        k = s["kind"]
        if k == "Let":
            v = self.expr(s["value"])
            self.emit("assign", v, None, s["name"])
        elif k == "If":
            c = self.expr(s["cond"])
            else_l = self.label()
            self.emit("jz", c, None, else_l)
            for x in s["then"]:
                self.stmt(x)
            if s["else"]:
                end_l = self.label()
                self.emit("jmp", None, None, end_l)
                self.emit("label", None, None, else_l)
                for x in s["else"]:
                    self.stmt(x)
                self.emit("label", None, None, end_l)
            else:
                self.emit("label", None, None, else_l)
        elif k == "Order":
            self.emit("order", s["text"])
        elif k == "Alert":
            self.emit("alert", s["text"])
        elif k == "Prescribe":
            d = self.expr(s["dose"])
            self.emit("rx", s["drug"], d, s["unit"])

    def generate(self, ast):
        for s in ast["body"]:
            self.stmt(s)
        return self.code
