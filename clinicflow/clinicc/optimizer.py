import re
from collections import Counter
from dataclasses import replace

from .ir import Instr, Const, BINOPS, fmt, to_text

TEMP = re.compile(r"t\d+")


def _positions(op):
    if op in BINOPS:
        return (0, 1)
    if op in ("assign", "not", "jz"):
        return (0,)
    if op == "rx":
        return (1,)
    return ()


def _get(i, p):
    return (i.arg1, i.arg2)[p]


def _fold(i):
    a, b = i.arg1, i.arg2
    try:
        if i.op == "not" and isinstance(a, Const):
            return Const(not a.value)
        if i.op in BINOPS and isinstance(a, Const) and isinstance(b, Const):
            return Const(BINOPS[i.op](a.value, b.value))
    except ZeroDivisionError:
        return None
    return None


def _propagate(code, log):
    """Constant propagation + constant folding inside basic blocks."""
    env, out = {}, []
    for ins in code:
        if ins.op == "label":
            env = {}
            out.append(ins)
            continue
        new = ins
        for p in _positions(ins.op):
            v = _get(new, p)
            if isinstance(v, str) and v in env:
                new = replace(new, **{("arg1", "arg2")[p]: env[v]})
                log.append(("Constant propagation",
                            f"Replaced '{v}' with {fmt(env[v])} in: {to_text(ins)}"))
        folded = _fold(new)
        if folded is not None:
            log.append(("Constant folding", f"{to_text(new)}   →   {new.res} = {fmt(folded)}"))
            new = Instr("assign", folded, None, new.res)
        if new.op == "assign":
            if isinstance(new.arg1, Const):
                env[new.res] = new.arg1
            else:
                env.pop(new.res, None)
        elif new.res is not None and new.op not in ("label", "jmp", "jz", "order", "alert", "rx"):
            env.pop(new.res, None)
        out.append(new)
    return out


def _branches(code, log):
    out = []
    for i in code:
        if i.op == "jz" and isinstance(i.arg1, Const):
            if i.arg1.value:
                log.append(("Branch folding", "A condition is always true, so its 'then' block always runs"))
            else:
                log.append(("Branch folding", f"A condition is always false, so execution always jumps to {i.res}"))
                out.append(Instr("jmp", None, None, i.res))
            continue
        out.append(i)
    return out


def _unreachable(code, log):
    referenced = {i.res for i in code if i.op in ("jmp", "jz")}
    out, dead = [], False
    for i in code:
        if i.op == "label" and i.res in referenced:
            dead = False
        if dead:
            if i.op != "label":
                log.append(("Unreachable code removal", f"Removed: {to_text(i)}"))
            continue
        out.append(i)
        if i.op == "jmp":
            dead = True
    return out


def _tidy_jumps(code, log):
    out = []
    for n, i in enumerate(code):
        if i.op == "jmp":
            j, redundant = n + 1, False
            while j < len(code) and code[j].op == "label":
                redundant = redundant or code[j].res == i.res
                j += 1
            if redundant:
                log.append(("Jump cleanup", f"Removed redundant 'goto {i.res}'"))
                continue
        out.append(i)
    used = {i.res for i in out if i.op in ("jmp", "jz")}
    return [i for i in out if not (i.op == "label" and i.res not in used)]


def _dead_code(code, log):
    changed = True
    while changed:
        changed = False
        read = set()
        for i in code:
            for p in _positions(i.op):
                v = _get(i, p)
                if isinstance(v, str):
                    read.add(v)
        out = []
        for i in code:
            if (i.op in ("assign", "not") or i.op in BINOPS) and i.res not in read:
                log.append(("Dead code elimination", f"Removed unused: {to_text(i)}"))
                changed = True
                continue
            out.append(i)
        code = out
    return code


def _duplicates(code, log):
    seen, out = set(), []
    for i in code:
        if i.op == "label" or (i.op == "assign" and not TEMP.fullmatch(i.res)):
            seen = set()
        if i.op in ("order", "alert", "rx"):
            key = (i.op, i.arg1, i.arg2, i.res)
            if key in seen:
                log.append(("Redundant order removal", f"Removed duplicate: {to_text(i)}"))
                continue
            seen.add(key)
        out.append(i)
    return out


def optimize(code):
    log, cur, passes = [], list(code), 0
    for _ in range(10):
        prev = cur
        cur = _propagate(cur, log)
        cur = _branches(cur, log)
        cur = _unreachable(cur, log)
        cur = _tidy_jumps(cur, log)
        cur = _dead_code(cur, log)
        cur = _duplicates(cur, log)
        passes += 1
        if cur == prev:
            break
    before, after = len(code), len(cur)
    stats = {"before": before, "after": after, "passes": passes,
             "reduction": round(100 * (before - after) / before) if before else 0,
             "by_pass": dict(Counter(p for p, _ in log))}
    return cur, log, stats
