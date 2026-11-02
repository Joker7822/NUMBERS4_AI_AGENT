"""Official Numbers4 four-position rules; never normalize leading zeroes away."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from math import factorial, prod
import re

PRICE_PER_TICKET_YEN = 200
OUTCOMES = 10_000


class PlayType(str, Enum):
    STRAIGHT = "straight"
    BOX = "box"
    SET = "set"


def four_digits(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}", value):
        raise ValueError("Numbers4 must be a four-character string, including leading zeroes")
    return value


def validate_play(number: str, play_type: str | PlayType) -> tuple[str, PlayType]:
    number = four_digits(number)
    try:
        mode = PlayType(play_type)
    except (ValueError, TypeError) as exc:
        raise ValueError("play type must be straight, box or set") from exc
    if mode is not PlayType.STRAIGHT and len(set(number)) == 1:
        raise ValueError("box and set do not allow four identical digits")
    return number, mode


def permutation_count(number: str) -> int:
    four_digits(number)
    counts = Counter(number)
    return factorial(4) // prod(factorial(v) for v in counts.values())


@dataclass(frozen=True)
class Odds:
    straight: float
    box_only: float
    any_win: float
    combinations: int


def theoretical_odds(number: str, play_type: str | PlayType) -> Odds:
    number, mode = validate_play(number, play_type)
    ways = permutation_count(number)
    if mode is PlayType.STRAIGHT:
        return Odds(1 / OUTCOMES, 0.0, 1 / OUTCOMES, 1)
    if mode is PlayType.BOX:
        return Odds(0.0, ways / OUTCOMES, ways / OUTCOMES, ways)
    return Odds(1 / OUTCOMES, (ways - 1) / OUTCOMES, ways / OUTCOMES, ways)


def grade_number(number: str, winning_number: str, play_type: str | PlayType) -> str:
    number, mode = validate_play(number, play_type)
    winning_number = four_digits(winning_number)
    if number == winning_number:
        return {PlayType.STRAIGHT: "straight", PlayType.BOX: "box", PlayType.SET: "set_straight"}[mode]
    if mode in (PlayType.BOX, PlayType.SET) and sorted(number) == sorted(winning_number):
        return "box" if mode is PlayType.BOX else "set_box"
    return "miss"
