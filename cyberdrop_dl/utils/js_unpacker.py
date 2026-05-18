"""Unpacker for Dean Edward's p.a.c.k.e.r, adapted from javascript beautifier

https://github.com/beautifier/js-beautify/blob/e89b8269e198492b6e6026d2cc5e8d750d59c42c/python/jsbeautifier/unpackers/packer.py

Original License: MIT

The MIT License (MIT)

Copyright (c) 2007-2018 Einar Lielmanis, Liam Newman, and contributors.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_ALPHABET = {
    62: "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    95: (" !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"),
}


def unpack(source: str) -> str:
    content, base, count, words_list = _parse(source)

    if count != len(words_list):
        raise RuntimeError

    decode = _make_decoder(base)

    def replace(match: re.Match[str]) -> str:
        word = match.group(0)
        return words_list[decode(word)] or word

    content = content.replace("\\\\", "\\").replace("\\'", "'")
    return re.sub(r"\b\w+\b", replace, content, flags=re.ASCII)


def _parse(source: str) -> tuple[str, int, int, list[str]]:
    if match := re.search((r"}\('(.*)', *(\d+|\[\]), *(\d+), *'(.*)'\.split\('\|'\)"), source, re.DOTALL):
        content, base, count, words_list = match.groups()
        if base == "[]":
            base = 62

        return content, int(base), int(count), words_list.split("|")

    raise RuntimeError


def _make_decoder(base: int) -> Callable[[str], int]:
    if 2 <= base <= 36:
        return lambda text: int(text, base)

    if 36 < base < 62 and base not in _ALPHABET:
        _ALPHABET[base] = _ALPHABET[62][:base]

    lookup = {char: idx for idx, char in enumerate(_ALPHABET[base])}

    def decode(text: str) -> int:
        return sum((base**index) * lookup[char] for index, char in enumerate(reversed(text)))

    return decode
