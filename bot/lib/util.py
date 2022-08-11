ORDINAL_WORDS = [
    "zeroeth",
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "nineth",
]


def ordinal(number: int) -> str:
    return f"{number}{ORDINAL_WORDS[number % 10][-2:]}"
