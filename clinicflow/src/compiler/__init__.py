from .module1_syntax import lex, parse
from .module2_ir import analyze, generate_tac
from .module3_optimize import optimize, to_python


def run_pipeline(source, known):
    """Runs all 3 modules. 'failed_at' = module number that stopped the build."""
    r = {"failed_at": None, "errors": [], "warnings": []}
    toks, lex_err = lex(source)
    prog, syn_err = parse(toks)
    r.update(tokens=toks, ast=prog)
    if lex_err or syn_err:
        r.update(failed_at=1, errors=lex_err + syn_err)
        return r
    errs, warns = analyze(prog, known)
    r["warnings"] = warns
    if errs:
        r.update(failed_at=2, errors=errs)
        return r
    opt, log = optimize(prog)
    r.update(tac=generate_tac(prog), opt_prog=opt, log=log,
             tac_opt=generate_tac(opt), python=to_python(opt, sorted(known)))
    return r
