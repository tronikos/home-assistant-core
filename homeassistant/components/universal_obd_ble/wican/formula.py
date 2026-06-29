"""Secure AST-based WiCAN Expression Evaluator."""

import ast
from functools import lru_cache
import logging
import operator
import re

_LOGGER = logging.getLogger(__name__)


def preprocess_expression(expr: str) -> str:
    """Translates WiCAN notation into secure Python function calls."""
    expr = expr.upper()
    expr = re.sub(r"\[B(\d+):B(\d+)\]", r"_slice_unsigned(\1, \2)", expr)
    expr = re.sub(r"\[S(\d+):S(\d+)\]", r"_slice_signed(\1, \2)", expr)
    expr = re.sub(r"\bB(\d+):(\d+)\b", r"_bit(\1, \2)", expr)
    expr = re.sub(r"\bB(\d+)\b", r"_byte_unsigned(\1)", expr)
    return re.sub(r"\bS(\d+)\b", r"_byte_signed(\1)", expr)


class SafeEvaluator(ast.NodeVisitor):
    """AST visitor implementing thread-safe execution of binary/unary expressions."""

    def __init__(self, dirty_array: list[int]) -> None:
        """Initialize the safe math evaluator."""
        self.payload = dirty_array

    def visit_BinOp(self, node):
        """Evaluate binary operations safely."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_type = type(node.op)
        ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.BitAnd: operator.and_,
            ast.BitOr: operator.or_,
            ast.BitXor: operator.xor,
            ast.LShift: operator.lshift,
            ast.RShift: operator.rshift,
        }
        if op_type in ops:
            if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
                return 0.0 if op_type is ast.Div else 0
            return ops[op_type](left, right)
        raise ValueError(f"Unsupported binary operator: {op_type}")

    def visit_UnaryOp(self, node):
        """Evaluate unary operations safely."""
        operand = self.visit(node.operand)
        op_type = type(node.op)
        if op_type == ast.USub:
            return -operand
        if op_type == ast.UAdd:
            return +operand
        if op_type == ast.Invert:
            return ~int(operand)
        raise ValueError(f"Unsupported unary operator: {op_type}")

    def visit_Constant(self, node):
        """Enforce numeric-only constants."""
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numeric constants allowed")

    def visit_Name(self, node):
        """Explicitly prevent raw variables/names."""
        raise ValueError("Raw variables not allowed")

    def visit_Expression(self, node):
        """Visit expression body."""
        return self.visit(node.body)

    def visit_Call(self, node):
        """Map customized preprocessing function signatures back to byte operations."""
        if not isinstance(node.func, ast.Name):
            raise TypeError("Unsupported complex function call structure")

        func_name = node.func.id
        args = [int(self.visit(a)) for a in node.args]

        if func_name == "_byte_unsigned":
            return self.payload[args[0]] if args[0] < len(self.payload) else 0

        if func_name == "_byte_signed":
            val = self.payload[args[0]] if args[0] < len(self.payload) else 0
            return val - 256 if val & 0x80 else val

        if func_name == "_slice_unsigned":
            expected_len = args[1] - args[0] + 1
            slice_bytes = bytes(self.payload[args[0] : args[1] + 1])
            if len(slice_bytes) != expected_len:
                raise ValueError(
                    f"Truncated slice: expected {expected_len} bytes at "
                    f"[{args[0]}:{args[1]}], got {len(slice_bytes)}"
                )
            return int.from_bytes(slice_bytes, byteorder="big", signed=False)

        if func_name == "_slice_signed":
            expected_len = args[1] - args[0] + 1
            slice_bytes = bytes(self.payload[args[0] : args[1] + 1])
            if len(slice_bytes) != expected_len:
                raise ValueError(
                    f"Truncated slice: expected {expected_len} bytes at "
                    f"[{args[0]}:{args[1]}], got {len(slice_bytes)}"
                )
            return int.from_bytes(slice_bytes, byteorder="big", signed=True)

        if func_name == "_bit":
            idx, bit = args[0], args[1]
            val = self.payload[idx] if idx < len(self.payload) else 0
            return (val >> bit) & 1

        raise ValueError(f"Unsupported function call: {func_name}")

    def generic_visit(self, node):
        """Throw errors on any other AST nodes."""
        raise ValueError(f"Unsupported AST node: {type(node).__name__}")


@lru_cache(maxsize=128)
def _get_compiled_expression(expr: str) -> ast.Expression:
    """Preprocess and compile a WiCAN expression string into a cached AST tree."""
    processed = preprocess_expression(expr)
    return ast.parse(processed, mode="eval")


def evaluate_wican_expression(expr: str, dirty_array: list[int]) -> float | None:
    """Preprocess and evaluate a WiCAN expression safely using the AST framework."""
    try:
        tree = _get_compiled_expression(expr)
        evaluator = SafeEvaluator(dirty_array)
        return float(evaluator.visit(tree))
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Failed to evaluate formula '%s': %s", expr, err)
        return None
