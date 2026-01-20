"""
protocol.py — Константы протокола TIME_BANK v3.0

Montana Protocol
Банк Времени — орган верификации эмиссии монет времени
"""


class Protocol:
    """Константы протокола TIME_BANK v3.0"""

    VERSION = "3.0"

    # Сеть
    NODES_COUNT = 5                        # 5 узлов Montana
    BANK_PRESENCE_PER_T2 = 600             # Банк всегда присутствует 600 сек (10 мин)

    # Временные координаты (Temporal Coordinates)
    TAU1_INTERVAL_SEC = 60                 # τ₁ = 1 минута — интервал подписи присутствия
    T2_DURATION_SEC = 10 * 60              # τ₂ = 10 минут = 600 секунд (slice/block)
    TAU3_DURATION_SEC = 14 * 24 * 60 * 60  # τ₃ = 14 дней = 1,209,600 сек (checkpoint)
    TAU4_DURATION_SEC = 4 * 365 * 24 * 60 * 60  # τ₄ = 4 года = 126,144,000 сек (epoch)

    # Иерархия
    T2_PER_TAU3 = 2016                     # 2016 × τ₂ в τ₃ (14 дней / 10 минут)
    TAU3_PER_YEAR = 26                     # 26 × τ₃ в году (365 / 14)
    TAU3_PER_TAU4 = 104                    # 104 × τ₃ в τ₄ (4 года)

    # Другие временные параметры
    INACTIVITY_LIMIT_SEC = 3 * 60          # 3 минуты без активности = пауза
    TICK_INTERVAL_SEC = 1                  # Интервал обновления

    # Монеты
    COINS_PER_SECOND = 1                   # 1 секунда = 1 монета (с халвингом)

    # Presence Proof
    PRESENCE_PROOF_VERSION = "MONTANA_PRESENCE_V1"
    GENESIS_HASH = "0" * 64                # Genesis prev_hash


# Экспорт
__all__ = ['Protocol']
