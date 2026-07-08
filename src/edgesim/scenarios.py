import random
from collections.abc import Callable

from pydantic import BaseModel

_LEAK_THRESHOLD = 5


class Tick(BaseModel):
    delta: float
    rolling: bool


def make_scenario(kind: str, seed: int) -> Callable[[int], Tick]:
    rng = random.Random(seed)

    def normal(_t: int) -> Tick:
        return Tick(delta=round(rng.uniform(0.05, 0.4), 3), rolling=rng.random() < 0.1)

    def leak(t: int) -> Tick:
        if t < _LEAK_THRESHOLD:
            return normal(t)
        return Tick(delta=round(rng.uniform(3.0, 6.0), 3), rolling=False)

    def flatline(_t: int) -> Tick:
        return Tick(delta=0.0, rolling=False)

    def lowconf(_t: int) -> Tick:
        return Tick(delta=round(rng.uniform(0.05, 0.4), 3), rolling=rng.random() < 0.7)

    table = {"normal": normal, "leak": leak, "flatline": flatline, "lowconf": lowconf}
    if kind not in table:
        raise ValueError(f"unknown scenario {kind!r}; valid: {sorted(table)}")
    return table[kind]
