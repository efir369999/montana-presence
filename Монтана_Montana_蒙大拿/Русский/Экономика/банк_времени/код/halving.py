"""
halving.py — Халвинг эмиссии каждые τ₄ (4 года)

Montana Protocol
Деление эмиссии на 2 каждые 4 года (как Bitcoin)
"""


def halving_coefficient(tau4_count: int) -> float:
    """
    Коэффициент халвинга — деление на 2 каждые τ₄ (4 года)

    Эмиссия уменьшается в 2 раза каждую эпоху τ₄

    Args:
        tau4_count: Количество пройденных τ₄ эпох (0, 1, 2, ...)

    Returns:
        Коэффициент эмиссии (1.0, 0.5, 0.25, 0.125, ...)

    Формула:
        emission_per_second = 1.0 / (2 ** tau4_count)

    Примеры:
        >>> halving_coefficient(0)  # τ₄ #0 (первые 4 года)
        1.0
        >>> halving_coefficient(1)  # τ₄ #1 (4-8 лет)
        0.5
        >>> halving_coefficient(2)  # τ₄ #2 (8-12 лет)
        0.25
        >>> halving_coefficient(3)  # τ₄ #3 (12-16 лет)
        0.125
        >>> halving_coefficient(10) # τ₄ #10 (40-44 года)
        0.0009765625

    График эмиссии:
        τ₄ = 0: 1 сек = 1.0 Ɉ
        τ₄ = 1: 1 сек = 0.5 Ɉ  (÷2)
        τ₄ = 2: 1 сек = 0.25 Ɉ (÷2)
        τ₄ = 3: 1 сек = 0.125 Ɉ (÷2)
        ...
        τ₄ → ∞: эмиссия → 0
    """
    return 1.0 / (2 ** tau4_count)


# Экспорт
__all__ = ['halving_coefficient']


if __name__ == "__main__":
    # Тесты
    print("Halving Coefficient Table:")
    print("=" * 50)
    print(f"{'τ₄':<5} {'Years':<12} {'Coefficient':<15} {'Ɉ per second'}")
    print("-" * 50)

    for tau4 in range(11):
        years = f"{tau4*4}-{(tau4+1)*4}"
        coef = halving_coefficient(tau4)
        print(f"{tau4:<5} {years:<12} {coef:<15.10f} {coef:.10f}")
