import re
from dataclasses import dataclass

import numpy as np

from app.tickers import resolve_ticker


class ExpressionError(ValueError):
    pass


_NUMBER = re.compile(r"\d+(?:\.\d*)?|\.\d+")
_TICKER = re.compile(r"\^?[A-Z][A-Z0-9.=\-]*")


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str
    pos: int


def _tokenize(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    i = 0
    while i < len(source):
        ch = source[i]
        if ch.isspace():
            i += 1
            continue
        operand_before = bool(tokens) and tokens[-1].kind in ("num", "ticker", ")")
        if ch in "()*/-" or (ch == "^" and operand_before):
            tokens.append(_Token(ch, ch, i))
            i += 1
            continue
        if m := _NUMBER.match(source, i):
            tokens.append(_Token("num", m.group(), i))
        elif m := _TICKER.match(source, i):
            tokens.append(_Token("ticker", m.group(), i))
        else:
            raise ExpressionError(f"Unexpected '{ch}' at position {i + 1}")
        i = m.end()
    return tokens


@dataclass(frozen=True)
class Number:
    value: float

    def tickers(self) -> set[str]:
        return set()

    def value_of(self, env):
        return self.value

    def bounds_of(self, env):
        return self.value, self.value


@dataclass(frozen=True)
class Ticker:
    symbol: str

    def tickers(self) -> set[str]:
        return {self.symbol}

    def value_of(self, env):
        return env[self.symbol]

    def bounds_of(self, env):
        return env[self.symbol]


@dataclass(frozen=True)
class BinOp:
    op: str
    left: "Node"
    right: "Node"

    def tickers(self) -> set[str]:
        return self.left.tickers() | self.right.tickers()

    def value_of(self, env):
        a, b = self.left.value_of(env), self.right.value_of(env)
        return a * b if self.op == "*" else a / b

    def bounds_of(self, env):
        a_lo, a_hi = self.left.bounds_of(env)
        b_lo, b_hi = self.right.bounds_of(env)
        if self.op == "/":
            spans_zero = (np.asarray(b_lo) <= 0) & (np.asarray(b_hi) >= 0)
            b_lo, b_hi = np.where(spans_zero, np.nan, 1 / b_hi), np.where(spans_zero, np.nan, 1 / b_lo)
        products = np.stack(np.broadcast_arrays(a_lo * b_lo, a_lo * b_hi, a_hi * b_lo, a_hi * b_hi))
        return products.min(axis=0), products.max(axis=0)


@dataclass(frozen=True)
class Power:
    base: "Node"
    exponent: float

    def tickers(self) -> set[str]:
        return self.base.tickers()

    def value_of(self, env):
        return np.power(self.base.value_of(env), self.exponent)

    def bounds_of(self, env):
        lo, hi = self.base.bounds_of(env)
        a, b = np.power(lo, self.exponent), np.power(hi, self.exponent)
        return np.minimum(a, b), np.maximum(a, b)


Node = Number | Ticker | BinOp | Power


class _Parser:
    def __init__(self, source: str):
        self.tokens = _tokenize(source)
        self.i = 0

    def parse(self) -> Node:
        if not self.tokens:
            raise ExpressionError("Formula is empty")
        node = self._expr()
        if self.i < len(self.tokens):
            tok = self.tokens[self.i]
            raise ExpressionError(f"Unexpected '{tok.text}' at position {tok.pos + 1}")
        return node

    def _peek(self) -> _Token | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _take(self, kind: str | None = None) -> _Token:
        tok = self._peek()
        if tok is None:
            raise ExpressionError("Formula ends unexpectedly")
        if kind and tok.kind != kind:
            raise ExpressionError(f"Expected '{kind}' at position {tok.pos + 1}, got '{tok.text}'")
        self.i += 1
        return tok

    def _expr(self) -> Node:
        node = self._power()
        while (tok := self._peek()) and tok.kind in ("*", "/"):
            self.i += 1
            node = BinOp(tok.kind, node, self._power())
        return node

    def _power(self) -> Node:
        node = self._atom()
        if (tok := self._peek()) and tok.kind == "^":
            self.i += 1
            sign = -1.0 if (nxt := self._peek()) and nxt.kind == "-" and self._take() else 1.0
            node = Power(node, sign * float(self._take("num").text))
        return node

    def _atom(self) -> Node:
        tok = self._take()
        if tok.kind == "num":
            return Number(float(tok.text))
        if tok.kind == "ticker":
            return Ticker(resolve_ticker(tok.text))
        if tok.kind == "(":
            node = self._expr()
            self._take(")")
            return node
        raise ExpressionError(f"Unexpected '{tok.text}' at position {tok.pos + 1}")


def parse(source: str) -> Node:
    return _Parser(source.upper()).parse()


def normalize(source: str) -> str:
    return re.sub(r"\s+", "", source.upper())
