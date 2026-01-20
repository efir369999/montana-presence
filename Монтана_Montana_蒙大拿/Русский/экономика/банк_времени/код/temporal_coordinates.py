"""
temporal_coordinates.py — Временные координаты Montana

Montana Protocol
Работа с τ₁, τ₂, τ₃, τ₄ координатами
"""

from protocol import Protocol


def t2_to_tau3(t2_count: int) -> int:
    """
    Конвертирует номер τ₂ в номер τ₃

    Args:
        t2_count: Номер слайса τ₂

    Returns:
        Номер checkpoint τ₃

    Пример:
        >>> t2_to_tau3(0)      # T2 #0
        0
        >>> t2_to_tau3(2016)   # T2 #2016 = τ₃ #1
        1
        >>> t2_to_tau3(4032)   # T2 #4032 = τ₃ #2
        2
    """
    return t2_count // Protocol.T2_PER_TAU3


def tau3_to_year(tau3_count: int) -> int:
    """
    Конвертирует номер τ₃ в год

    Args:
        tau3_count: Номер checkpoint τ₃

    Returns:
        Год (0, 1, 2, ...)

    Пример:
        >>> tau3_to_year(0)    # τ₃ #0
        0
        >>> tau3_to_year(26)   # τ₃ #26 = год 1
        1
        >>> tau3_to_year(52)   # τ₃ #52 = год 2
        2
    """
    return tau3_count // Protocol.TAU3_PER_YEAR


def tau3_to_tau4(tau3_count: int) -> int:
    """
    Конвертирует номер τ₃ в номер τ₄

    Args:
        tau3_count: Номер checkpoint τ₃

    Returns:
        Номер epoch τ₄

    Пример:
        >>> tau3_to_tau4(0)     # τ₃ #0
        0
        >>> tau3_to_tau4(104)   # τ₃ #104 = τ₄ #1
        1
        >>> tau3_to_tau4(208)   # τ₃ #208 = τ₄ #2
        2
    """
    return tau3_count // Protocol.TAU3_PER_TAU4


def t2_to_tau4(t2_count: int) -> int:
    """
    Конвертирует номер τ₂ в номер τ₄ (через τ₃)

    Args:
        t2_count: Номер слайса τ₂

    Returns:
        Номер epoch τ₄

    Пример:
        >>> t2_to_tau4(0)        # T2 #0
        0
        >>> t2_to_tau4(209664)   # T2 #209664 = τ₄ #1
        1
    """
    tau3 = t2_to_tau3(t2_count)
    return tau3_to_tau4(tau3)


def is_tau3_checkpoint(t2_count: int) -> bool:
    """
    Проверяет, является ли τ₂ чекпоинтом τ₃

    Args:
        t2_count: Номер слайса τ₂

    Returns:
        True если τ₂ кратен 2016 (= τ₃ checkpoint)

    Пример:
        >>> is_tau3_checkpoint(2016)
        True
        >>> is_tau3_checkpoint(2015)
        False
    """
    return t2_count % Protocol.T2_PER_TAU3 == 0


def is_tau4_epoch(tau3_count: int) -> bool:
    """
    Проверяет, является ли τ₃ эпохой τ₄ (халвингом)

    Args:
        tau3_count: Номер checkpoint τ₃

    Returns:
        True если τ₃ кратен 104 (= τ₄ epoch = HALVING)

    Пример:
        >>> is_tau4_epoch(104)
        True
        >>> is_tau4_epoch(103)
        False
    """
    return tau3_count % Protocol.TAU3_PER_TAU4 == 0


def t2_remaining_to_tau3(t2_count: int) -> int:
    """
    Сколько τ₂ осталось до следующего τ₃

    Args:
        t2_count: Текущий номер τ₂

    Returns:
        Количество τ₂ до следующего checkpoint

    Пример:
        >>> t2_remaining_to_tau3(0)     # До τ₃ #1
        2016
        >>> t2_remaining_to_tau3(2000)  # До τ₃ #1
        16
        >>> t2_remaining_to_tau3(2016)  # До τ₃ #2
        2016
    """
    return Protocol.T2_PER_TAU3 - (t2_count % Protocol.T2_PER_TAU3)


# Экспорт
__all__ = [
    't2_to_tau3',
    'tau3_to_year',
    'tau3_to_tau4',
    't2_to_tau4',
    'is_tau3_checkpoint',
    'is_tau4_epoch',
    't2_remaining_to_tau3'
]


if __name__ == "__main__":
    # Тесты
    print("Temporal Coordinates Examples:")
    print("=" * 60)

    examples = [
        (0, "Начало"),
        (2016, "Первый τ₃"),
        (52416, "1 год (26 × τ₃)"),
        (104832, "2 года (52 × τ₃)"),
        (209664, "Первый τ₄ (4 года)"),
    ]

    for t2, desc in examples:
        tau3 = t2_to_tau3(t2)
        year = tau3_to_year(tau3)
        tau4 = t2_to_tau4(t2)
        is_cp = is_tau3_checkpoint(t2)
        is_ep = is_tau4_epoch(tau3) if tau3 > 0 else False

        print(f"\n{desc} (T2 #{t2}):")
        print(f"  τ₃: {tau3}")
        print(f"  Year: {year}")
        print(f"  τ₄: {tau4}")
        print(f"  Is τ₃ checkpoint: {is_cp}")
        print(f"  Is τ₄ epoch (halving): {is_ep}")
