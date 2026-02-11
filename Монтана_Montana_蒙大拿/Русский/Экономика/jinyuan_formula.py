#!/usr/bin/env python3
"""
jinyuan_formula.py — Формула 金元∞Ɉ (максимальная компрессия)

Книга Монтана, Глава 05:
> "⾦元∞Ɉ — От золота через начало к бесконечности в идеальных деньгах."
> "Деньги это современный 'локоть' измерения времени."
> "Время = метр ценности. У всех одинаковое. 86400 секунд в сутках. Не напечатать."

Четыре символа — максимальная компрессия экономической истории:
- 金 (jīn) — золото, старая ценность
- 元 (yuán) — начало, единица, точка отсчёта
- ∞ — бесконечность, горизонт
- Ɉ — идеальные деньги, время
"""

from dataclasses import dataclass
from typing import Dict, List
from decimal import Decimal


@dataclass
class Symbol:
    """Символ в формуле."""
    char: str           # Символ
    pinyin: str         # Транскрипция
    meaning: str        # Значение
    era: str            # Эра
    description: str    # Описание


class JinYuanFormula:
    """
    Формула 金元∞Ɉ — максимальная компрессия.

    Книга Монтана:
    > "Четыре символа. Максимальная компрессия."
    > "Тысячи лет люди измеряли ценность золотом, серебром, ракушками,
    > бумажками с портретами. А время — было всегда."
    """

    FORMULA = "金元∞Ɉ"

    SYMBOLS = [
        Symbol(
            char="金",
            pinyin="jīn",
            meaning="Золото",
            era="Ancient",
            description="Старая ценность. Физический металл. Можно добыть, украсть, копить."
        ),
        Symbol(
            char="元",
            pinyin="yuán",
            meaning="Начало, единица",
            era="Classical",
            description="Точка отсчёта. Юань = единица. Genesis = начало системы."
        ),
        Symbol(
            char="∞",
            pinyin="infinity",
            meaning="Бесконечность",
            era="Modern",
            description="Горизонт. То, к чему стремится система. Недостижимый идеал."
        ),
        Symbol(
            char="Ɉ",
            pinyin="juno",
            meaning="Идеальные деньги",
            era="Montana",
            description="Время как валюта. 86400 секунд в сутках. Нельзя напечатать."
        )
    ]

    # Сравнение: локоть vs метр
    MEASUREMENT_EVOLUTION = {
        "локоть": {
            "type": "subjective",
            "description": "У каждого свой. Можно манипулировать.",
            "analogy": "Деньги (инфляция, курсы, манипуляции)"
        },
        "метр": {
            "type": "objective",
            "description": "У всех одинаковый. Физическая константа.",
            "analogy": "Время (86400 сек/день, не напечатать)"
        }
    }

    def __init__(self):
        self.formula = self.FORMULA
        self.symbols = self.SYMBOLS

    def get_symbol(self, index: int) -> Symbol:
        """Получить символ по индексу."""
        if 0 <= index < len(self.SYMBOLS):
            return self.SYMBOLS[index]
        raise IndexError(f"Symbol index {index} out of range")

    def decode(self) -> Dict:
        """Декодировать формулу."""
        return {
            "formula": self.FORMULA,
            "symbols": [
                {
                    "char": s.char,
                    "meaning": s.meaning,
                    "era": s.era
                }
                for s in self.SYMBOLS
            ],
            "reading": "От золота через начало к бесконечности в идеальных деньгах",
            "compression": "4 символа = вся экономическая история"
        }

    def get_transition(self) -> List[Dict]:
        """Получить переходы между символами."""
        transitions = []

        for i in range(len(self.SYMBOLS) - 1):
            current = self.SYMBOLS[i]
            next_sym = self.SYMBOLS[i + 1]

            transitions.append({
                "from": current.char,
                "to": next_sym.char,
                "transition": f"{current.meaning} → {next_sym.meaning}",
                "description": f"Эволюция от {current.era} к {next_sym.era}"
            })

        return transitions

    def time_vs_money(self) -> Dict:
        """Сравнение времени и денег как единиц измерения."""
        return {
            "money_as_cubit": {
                "type": "Локоть",
                "problems": [
                    "У каждого свой курс",
                    "Инфляция размывает",
                    "Манипуляции возможны",
                    "Можно напечатать"
                ]
            },
            "time_as_meter": {
                "type": "Метр",
                "advantages": [
                    "У всех одинаковое",
                    "86400 секунд в сутках",
                    "Нельзя напечатать",
                    "Абсолютно справедливое распределение"
                ]
            },
            "conclusion": "Время — единственный ресурс, распределённый абсолютно справедливо"
        }

    def seconds_per_day(self) -> int:
        """Секунд в сутках — константа для всех."""
        return 86400

    def __str__(self) -> str:
        return self.FORMULA


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    formula = JinYuanFormula()

    print("=" * 60)
    print(f"FORMULA: {formula}")
    print("=" * 60)
    print("\n'От золота через начало к бесконечности в идеальных деньгах'")

    print("\n--- СИМВОЛЫ ---")
    for i, symbol in enumerate(formula.symbols):
        print(f"\n{i+1}. {symbol.char} ({symbol.pinyin})")
        print(f"   Значение: {symbol.meaning}")
        print(f"   Эра: {symbol.era}")
        print(f"   {symbol.description}")

    print("\n--- ПЕРЕХОДЫ ---")
    for trans in formula.get_transition():
        print(f"  {trans['from']} → {trans['to']}: {trans['transition']}")

    print("\n--- ЛОКОТЬ vs МЕТР ---")
    comparison = formula.time_vs_money()

    print("\nДеньги (локоть):")
    for problem in comparison["money_as_cubit"]["problems"]:
        print(f"  ✗ {problem}")

    print("\nВремя (метр):")
    for advantage in comparison["time_as_meter"]["advantages"]:
        print(f"  ✓ {advantage}")

    print(f"\n--- КОНСТАНТА ---")
    print(f"Секунд в сутках: {formula.seconds_per_day():,}")
    print("Нельзя занять. Нельзя накопить. Нельзя передать.")

    print("\n" + "=" * 60)
    print(f"'{formula}' — максимальная компрессия")
    print("=" * 60)
