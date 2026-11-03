import json
from .module1_syntax import num_str

OPS = {
    "+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b,
    "/": lambda a, b: a / b if b else 0.0,
    ">": lambda a, b: float(a > b), "<": lambda a, b: float(a < b),
    ">=": lambda a, b: float(a >= b), "<=": lambda a, b: float(a <= b),
    "==": lambda a, b: float(a == b), "!=": lambda a, b: float(a != b),
    "and": lambda a, b: float(bool(a) and bool(b)),
    "or": lambda a, b: float(bool(a) or bool(b)),
}
PRIORITY = {"alert": 0, "order": 1, "prescribe": 2}


def fold(e, c):
    """Constant folding. c[0] counts folds."""
    if e[0] == "bin":
        op, l, r = e[1], fold(e[2], c), fold(e[3], c)
        if l[0] == "num" and r[0] == "num":
            c[0] += 1
            return ("num", OPS[op](l[1], r[1]))
        if r[0] == "num" and ((op == "*" and r[1] == 1) or (op == "+" and r[1] == 0)):
            c[0] += 1
            return l
        return ("bin", op, l, r)
    if e[0] == "not":
        x = fold(e[1], c)
        if x[0] == "num":
            c[0] += 1
            return ("num", float(not x[1]))
        return ("not", x)
    return e


def optimize(prog):
    log, c = [], [0]
    out = [{**s, "e": fold(s["e"], c)} if s["t"] == "set" else {**s, "c": fold(s["c"], c)}
           for s in prog]
    log.append(f"Constant folding: {c[0]} expression(s) evaluated at compile time")

    dead = always = 0
    kept = []
    for s in out:
        if s["t"] == "if" and s["c"][0] == "num":
            if not s["c"][1]:
                dead += 1
                continue
            always += 1
        kept.append(s)
    out = kept
    log.append(f"Dead rule elimination: {dead} rule(s) that can never fire removed")
    log.append(f"Always-true rules: {always} converted to unconditional actions")

    seen, dup, kept = [], 0, []
    for s in out:
        if s["t"] == "set":
            seen.clear()
            kept.append(s)
            continue
        key, cond = (s["k"], s["arg"]), repr(s["c"])
        if any(k == key and (cd == cond or un) for k, cd, un in seen):
            dup += 1
            continue
        seen.append((key, cond, s["c"][0] == "num"))
        kept.append(s)
    out = kept
    log.append(f"Duplicate action removal: {dup} redundant action(s) removed")

    final, run = [], []
    def flush():
        run.sort(key=lambda s: PRIORITY[s["k"]])
        final.extend(run)
        run.clear()
    for s in out:
        if s["t"] == "set":
            flush(); final.append(s)
        else:
            run.append(s)
    flush()
    log.append("Priority scheduling: alerts first, then orders, then prescriptions")
    return final, log


def _py(e):
    if e[0] == "num": return num_str(e[1])
    if e[0] == "id": return e[1]
    if e[0] == "not": return f"not {_py(e[1])}"
    return f"({_py(e[2])} {e[1]} {_py(e[3])})"


def _top(e):
    s = _py(e)
    return s[1:-1] if e[0] == "bin" else s


def to_python(prog, params):
    """Automated code generation: emits a runnable Python function."""
    lines = [f"def run_workflow({', '.join(params)}):", "    actions = []"]
    for s in prog:
        if s["t"] == "set":
            lines.append(f"    {s['name']} = {_top(s['e'])}")
            continue
        add = f"actions.append(({s['k']!r}, {json.dumps(s['arg'])}))"
        if s["c"][0] == "num":
            lines.append(f"    {add}")
        else:
            lines += [f"    if {_top(s['c'])}:", f"        {add}"]
    lines.append("    return actions")
    return "\n".join(lines) + "\n"


def execute(prog, env):
    env, fired = dict(env), []

    def ev(e):
        if e[0] == "num": return e[1]
        if e[0] == "id": return env[e[1]]
        if e[0] == "not": return float(not ev(e[1]))
        return OPS[e[1]](ev(e[2]), ev(e[3]))

    for s in prog:
        if s["t"] == "set":
            env[s["name"]] = ev(s["e"])
        elif ev(s["c"]):
            fired.append((s["k"], s["arg"]))
    return fired
