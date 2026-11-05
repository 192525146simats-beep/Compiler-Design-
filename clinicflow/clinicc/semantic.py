import re

VITAL_RANGES = {"bp_sys": (40, 300), "bp_dia": (20, 200), "hr": (20, 250),
                "temp": (30, 45), "spo2": (0, 100), "age": (0, 120),
                "weight": (1, 400), "glucose": (20, 800)}

# drug -> (max daily dose, unit)   (teaching values only, NOT clinical guidance)
DRUG_MAX = {"paracetamol": (4000, "mg"), "ibuprofen": (2400, "mg"),
            "aspirin": (4000, "mg"), "metformin": (2550, "mg"),
            "amoxicillin": (3000, "mg"), "insulin": (100, "units")}


def analyze(ast):
    errors, warnings, symbols = [], [], {}

    def typeof(e, line):
        k = e["kind"]
        if k == "Num":
            return "number"
        if k == "Str":
            return "text"
        if k == "Bool":
            return "bool"
        if k == "Var":
            if e["name"] not in symbols:
                errors.append(f"Line {line}: variable '{e['name']}' is used before it is defined")
                return "error"
            return symbols[e["name"]]
        if k == "Un":
            t = typeof(e["e"], line)
            if t not in ("bool", "error"):
                errors.append(f"Line {line}: 'not' needs a true/false value but got {t}")
            return "bool"
        l, r, op = typeof(e["l"], line), typeof(e["r"], line), e["op"]
        bad = "error" in (l, r)
        if op in ("+", "-", "*", "/"):
            if not bad and (l != "number" or r != "number"):
                errors.append(f"Line {line}: '{op}' needs numbers but got {l} and {r}")
            if op == "/" and e["r"]["kind"] == "Num" and e["r"]["value"] == 0:
                errors.append(f"Line {line}: division by zero")
            return "number"
        if op in ("and", "or"):
            if not bad and (l != "bool" or r != "bool"):
                errors.append(f"Line {line}: '{op}' needs true/false values but got {l} and {r}")
            return "bool"
        if not bad:
            if l != r:
                errors.append(f"Line {line}: cannot compare {l} with {r}")
            elif op not in ("==", "!=") and l != "number":
                errors.append(f"Line {line}: '{op}' can only compare numbers")
        return "bool"

    def walk(stmts):
        for s in stmts:
            k, line = s["kind"], s.get("line", 0)
            if k == "Let":
                name = s["name"]
                t = typeof(s["value"], line)
                if re.fullmatch(r"[tL]\d+", name):
                    errors.append(f"Line {line}: '{name}' is reserved for the compiler; pick another name")
                if name in symbols and t != "error" and symbols[name] != t:
                    errors.append(f"Line {line}: '{name}' was {symbols[name]} and cannot become {t}")
                if t != "error":
                    symbols[name] = t
                else:
                    symbols.setdefault(name, "number")
                if name in VITAL_RANGES and s["value"]["kind"] == "Num":
                    lo, hi = VITAL_RANGES[name]
                    v = s["value"]["value"]
                    if not lo <= v <= hi:
                        warnings.append(f"Line {line}: {name} = {v:g} is outside the plausible range "
                                        f"{lo}-{hi}; possible data-entry error")
            elif k == "If":
                t = typeof(s["cond"], line)
                if t not in ("bool", "error"):
                    errors.append(f"Line {line}: an 'if' condition must be true/false, got {t}")
                walk(s["then"])
                walk(s["else"])
            elif k == "Prescribe":
                t = typeof(s["dose"], line)
                if t not in ("number", "error"):
                    errors.append(f"Line {line}: a dose must be a number, got {t}")
                drug, unit = s["drug"].lower(), s["unit"].lower()
                if drug not in DRUG_MAX:
                    warnings.append(f"Line {line}: '{s['drug']}' is not in the drug formulary; "
                                    f"dose limit was not checked")
                else:
                    mx, u = DRUG_MAX[drug]
                    if unit != u:
                        errors.append(f"Line {line}: {s['drug']} must be prescribed in {u}, not {s['unit']}")
                    elif s["dose"]["kind"] == "Num":
                        v = s["dose"]["value"]
                        if v <= 0:
                            errors.append(f"Line {line}: dose must be greater than zero")
                        elif v > mx:
                            errors.append(f"Line {line}: {s['drug']} dose {v:g} {u} exceeds the "
                                          f"safety limit of {mx} {u}")

    walk(ast["body"])
    return {"errors": errors, "warnings": warnings, "symbols": symbols}
