"""Formula validation and bytecode compilation.

Three-stage pipeline:

  Stage 1 - regex pre-screen
      Fast-fail on disallowed characters. NOT the security boundary
      (character classes can't distinguish ``3.5`` from ``x.real``); just
      a cheap reject for unicode, control chars, weird punctuation.

  Stage 2 - AST structural validation  (the actual security boundary)
      Parse with ``ast.parse(source, mode="eval")`` and walk the tree,
      allowing only:
        - BinOp with whitelisted operators
        - UnaryOp with whitelisted operators
        - Constant (int or float only)
        - Call where the function is B, S, or BIT, with int-literal args
      Anything else (Name, Attribute, Subscript, Lambda, comprehensions,
      walrus, f-strings, nested calls) raises :class:`FormulaValidationError`.
      After this visitor passes, the tree is structurally incapable of
      reaching ``__builtins__``, doing attribute traversal, or constructing
      arbitrary objects.

  Stage 3 - compile() to CPython bytecode  (the performance fix)
      ``compile(tree, filename="<elm327_obdii_formula>", mode="eval")``
      produces a real code object. At runtime,
      ``eval(code, {"__builtins__": {}}, ...)`` runs in the interpreter's
      eval loop directly - no per-poll AST walk, no per-call NodeVisitor
      dispatch, no per-call dict lookups.

The config flow runs only stages 1+2 (via :func:`validate_formula`) to
refuse save on a bad formula. The poller compiles to bytecode once at
startup via :func:`compile_formula` (cached with functools.lru_cache
on the source string) and reuses it for the life of the process.

Canonical formula notation
--------------------------
    B(n)         unsigned byte at index n            (0..255)
    B(n, m)      big-endian unsigned word, bytes n..m inclusive
    S(n)         signed byte at index n              (-128..127)
    S(n, m)      big-endian signed word, bytes n..m inclusive
    BIT(b, n)    single bit n of byte b              (0 or 1)

    For B and S, the call disambiguates by argument count:
      1 argument  -> single byte at that index
      2 arguments -> multi-byte slice from first..second (inclusive)

    Operators:  +  -  *  /  //  %  **  &  |  ^  ~  <<  >>
    Constants:  integer and float literals (including scientific notation)
    Grouping:   parentheses only

Examples:
    "B(0) / 2.55"            SOC percentage from a 0..255 byte
    "B(5, 6) / 100"          16-bit big-endian value scaled to hundredths
    "S(3) * 1.8 + 32"        Celsius to Fahrenheit
    "BIT(2, 0) * 1 + BIT(2, 1) * 2"   2-bit enum from byte 2
"""

import ast
from collections.abc import Callable
from functools import lru_cache
import re
from types import CodeType
from typing import Final

__all__ = [
    "ALLOWED_FUNCTIONS",
    "FormulaValidationError",
    "compile_formula",
    "make_evaluator",
    "validate_formula",
]


class FormulaValidationError(ValueError):
    """Raised when a formula fails the whitelist or AST structural check."""


_TOKEN_WHITELIST: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9+\-*/%().,&|^~<>\s]+$"
)

_FUNCTION_NAMES: Final[frozenset[str]] = frozenset({"B", "S", "BIT"})
_ALLOWED_BINOPS: Final[frozenset[type]] = frozenset(
    {
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.BitAnd,
        ast.BitOr,
        ast.BitXor,
        ast.LShift,
        ast.RShift,
    }
)
_ALLOWED_UNARYOPS: Final[frozenset[type]] = frozenset({ast.UAdd, ast.USub, ast.Invert})


class _AstWhitelistVisitor(ast.NodeVisitor):
    """Walk the AST and raise on any node type not in the whitelist.

    ``generic_visit`` is overridden to raise - so any node type without
    an explicit ``visit_*`` method (Name, Attribute, Subscript, Lambda,
    comprehensions, walrus, f-strings, BoolOp, Compare, IfExp, etc.)
    is rejected by default. Each allowed ``visit_*`` method recurses
    explicitly into the children it expects, so the visitor never
    silently skips a subtree.
    """

    def visit_Expression(self, node: ast.Expression) -> None:
        self.visit(node.body)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if type(node.op) not in _ALLOWED_BINOPS:
            raise FormulaValidationError(
                f"binary operator {type(node.op).__name__!r} is not allowed"
            )
        self.visit(node.left)
        self.visit(node.right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        if type(node.op) not in _ALLOWED_UNARYOPS:
            raise FormulaValidationError(
                f"unary operator {type(node.op).__name__!r} is not allowed"
            )
        self.visit(node.operand)

    def visit_Constant(self, node: ast.Constant) -> None:
        if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
            raise FormulaValidationError(
                f"constant of type {type(node.value).__name__!r} is not allowed; "
                f"only int and float literals"
            )

    def visit_Call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name):
            raise FormulaValidationError(
                "only direct calls to B, S, or BIT are allowed; "
                "no attribute calls or subexpressions as the function"
            )
        if node.func.id not in _FUNCTION_NAMES:
            raise FormulaValidationError(
                f"function {node.func.id!r} is not allowed; use B, S, or BIT"
            )
        if node.keywords:
            raise FormulaValidationError(
                "keyword arguments are not allowed in formulas"
            )

        for arg in node.args:
            if (
                not isinstance(arg, ast.Constant)
                or not isinstance(arg.value, int)
                or isinstance(arg.value, bool)
            ):
                raise FormulaValidationError(
                    f"arguments to {node.func.id}() must be integer literals"
                )
            if arg.value < 0:
                raise FormulaValidationError(
                    f"arguments to {node.func.id}() must be non-negative"
                )

        if node.func.id == "BIT":
            if len(node.args) != 2:
                raise FormulaValidationError("BIT(b, n) requires exactly 2 arguments")
        elif not (1 <= len(node.args) <= 2):
            raise FormulaValidationError(
                f"{node.func.id}(n) or {node.func.id}(n, m) - 1 or 2 arguments required"
            )

    def generic_visit(self, node: ast.AST) -> None:
        raise FormulaValidationError(
            f"disallowed expression element: {type(node).__name__!r}"
        )


def validate_formula(source: str) -> None:
    """Stages 1+2: regex pre-screen + AST structural validation.

    Raises :class:`FormulaValidationError` on any disallowed construct.
    Does NOT call :func:`compile` - that's :func:`compile_formula`'s job.

    The config flow calls this to refuse save on a bad formula. The
    poller calls :func:`compile_formula` (which internally calls
    :func:`validate_formula` first) at startup.
    """
    if not isinstance(source, str):
        raise FormulaValidationError("formula must be a string")
    if not source.strip():
        raise FormulaValidationError("formula is empty")
    if len(source) > 256:
        raise FormulaValidationError("formula too long (max 256 chars)")

    if not _TOKEN_WHITELIST.fullmatch(source):
        raise FormulaValidationError(
            "formula contains disallowed characters; only digits, math operators, "
            "parentheses, commas, and the functions B/S/BIT are permitted"
        )

    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        raise FormulaValidationError(
            f"formula is not valid Python syntax: {exc.msg}"
        ) from exc

    _AstWhitelistVisitor().visit(tree)


@lru_cache(maxsize=512)
def compile_formula(source: str) -> CodeType:
    """Stages 1+2+3: validate, then ``compile()`` to a Python code object.

    Cached on the source string for the life of the process. The first
    call from the poller's startup pays the parse+compile cost;
    subsequent calls (including from :func:`make_evaluator`) hit the
    cache.

    The returned code object is suitable for
    ``eval(code, {"__builtins__": {}}, locals)``.
    """
    validate_formula(source)
    tree = ast.parse(source, mode="eval")
    return compile(tree, filename="<elm327_obdii_formula>", mode="eval")


def make_evaluator(source: str) -> Callable[[list[int]], float | None]:
    """Compile + wrap in a safety closure.

    The closure:
      - returns None on ZeroDivisionError, IndexError, ValueError,
        TypeError, OverflowError - a single bad formula never crashes
        the polling cycle, the sensor just reads unavailable.
      - returns ``float(result)`` on success.

    Out-of-bounds byte accesses return 0 (matching the existing
    behavior) rather than raising, so a formula that references byte 7
    against a 6-byte response degrades gracefully instead of marking
    the sensor unavailable on every poll.
    """
    code = compile_formula(source)

    def evaluate(payload: list[int]) -> float | None:
        try:
            # Safe: code was produced by compile_formula() which only
            # accepts AST trees that passed _AstWhitelistVisitor - no
            # Attribute, Name, Subscript, or calls outside B/S/BIT.
            # __builtins__ is empty, so eval cannot reach any builtin.
            result = eval(code, {"__builtins__": {}}, _make_byte_helpers(payload))  # noqa: S307
        except ZeroDivisionError:
            return None
        except IndexError, ValueError, TypeError, OverflowError:
            return None
        try:
            return float(result)
        except TypeError, ValueError:
            return None

    return evaluate


def _make_byte_helpers(payload: list[int]) -> dict[str, object]:
    """Build the safe locals dict for ``eval()``.

    Each helper closes over ``payload`` and bounds-checks every access.
    Out-of-bounds reads return 0 instead of raising - this keeps a
    single bad byte index from marking the sensor unavailable on every
    poll.
    """

    def b(n: int, m: int | None = None) -> int:
        if n < 0 or n >= len(payload):
            return 0
        if m is None:
            return payload[n]
        if m < n or m >= len(payload):
            return 0
        return int.from_bytes(bytes(payload[n : m + 1]), byteorder="big", signed=False)

    def s(n: int, m: int | None = None) -> int:
        if n < 0 or n >= len(payload):
            return 0
        if m is None:
            v = payload[n]
            return v - 256 if v & 0x80 else v
        if m < n or m >= len(payload):
            return 0
        return int.from_bytes(bytes(payload[n : m + 1]), byteorder="big", signed=True)

    def bit(byte_idx: int, bit_idx: int) -> int:
        if byte_idx < 0 or byte_idx >= len(payload):
            return 0
        if bit_idx < 0 or bit_idx > 7:
            return 0
        return (payload[byte_idx] >> bit_idx) & 1

    return {"B": b, "S": s, "BIT": bit}


ALLOWED_FUNCTIONS: Final[frozenset[str]] = frozenset(_FUNCTION_NAMES)
