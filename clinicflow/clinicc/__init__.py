from .lexer import tokenize
from .parser import Parser, pretty
from .semantic import analyze
from .ir import IRGen, to_text, rows, listing
from .optimizer import optimize
from .codegen import to_assembly, to_python, execute, to_orders_json


def compile_source(src: str, enabled=None) -> dict:
    """enabled: which optimizations to run (None = all)."""
    tokens, lex_errors = tokenize(src)
    parser = Parser(tokens)
    ast = parser.parse()
    r = {"tokens": tokens, "ast": ast, "syntax_errors": lex_errors + parser.errors,
         "sem": None, "ir": [], "opt": [], "log": [], "stats": {}, "ok": False}
    if r["syntax_errors"]:
        return r
    r["sem"] = analyze(ast)
    if r["sem"]["errors"]:
        return r
    r["ir"] = IRGen().generate(ast)
    r["opt"], r["log"], r["stats"] = optimize(r["ir"], enabled)
    r["asm"] = to_assembly(r["opt"])
    r["py"] = to_python(r["opt"])
    r["run_raw"] = execute(r["ir"])
    r["run_opt"] = execute(r["opt"])
    # duplicates are removed on purpose, so compare with duplicates collapsed
    r["equivalent"] = list(dict.fromkeys(r["run_raw"])) == list(dict.fromkeys(r["run_opt"]))
    r["ok"] = True
    return r
