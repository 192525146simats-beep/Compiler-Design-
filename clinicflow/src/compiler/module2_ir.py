from .module1_syntax import num_str


def names(e):
    if e[0] == "id": return [e[1]]
    if e[0] == "not": return names(e[1])
    if e[0] == "bin": return names(e[2]) + names(e[3])
    return []


def analyze(prog, known):
    """Semantic analysis. `known` = variables supplied by the app (patient data + risk)."""
    defined, used, declared = set(known), set(), set()
    errors, warnings = [], []
    for s in prog:
        e = s["e"] if s["t"] == "set" else s["c"]
        for v in names(e):
            used.add(v)
            if v not in defined:
                errors.append(f"Line {s['line']}: variable '{v}' is not defined")
        if s["t"] == "set":
            defined.add(s["name"])
            declared.add(s["name"])
    for v in sorted(declared - used):
        warnings.append(f"Variable '{v}' is set but never used")
    return errors, warnings


def generate_tac(prog):
    """Three-address code with temporaries (t1..) and labels (L1..)."""
    out, cnt = [], {"t": 0, "l": 0}

    def tmp():
        cnt["t"] += 1
        return f"t{cnt['t']}"

    def gen(e):
        if e[0] == "num": return num_str(e[1])
        if e[0] == "id": return e[1]
        if e[0] == "not":
            a = gen(e[1]); r = tmp()
            out.append(f"{r} = not {a}")
            return r
        a, b = gen(e[2]), gen(e[3]); r = tmp()
        out.append(f"{r} = {a} {e[1]} {b}")
        return r

    for s in cnt and prog:
        if s["t"] == "set":
            out.append(f"{s['name']} = {gen(s['e'])}")
        elif s["c"][0] == "num" and s["c"][1]:       # always true: no branch needed
            out.append(f"{s['k'].upper()} {s['arg']}")
        else:
            c = gen(s["c"])
            cnt["l"] += 1
            label = f"L{cnt['l']}"
            out += [f"ifFalse {c} goto {label}", f"{s['k'].upper()} {s['arg']}", f"{label}:"]
    return out
