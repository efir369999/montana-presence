"""
Montana Bot — Verified Users (20%)
==================================

Принцип Парето 80/20:
- 80% Full Nodes (серверы, автоматика)
- 20% Verified Users (люди, "Ты здесь?")

Genesis = первый когнитивный ключ участника.
После genesis — твори где хочешь (Twitter, Telegram, GitHub).
Верификация — через Montana network.

Использование:
    from montana_bot import PresenceStorage, register_montana_handlers

lim(evidence → ∞) 1 Ɉ → 1 секунда
"""

from .presence import (
    PresenceStorage,
    CognitiveKey,
    PresenceChallenge,
    PresenceRecord,
    UserPresenceStats,
    generate_cognitive_key,
    create_challenge,
    verify_challenge_response,
    calculate_next_challenge_interval,
    format_genesis_message,
    format_challenge_message,
    format_stats_message,
    TAU2_SECS,
    VERIFICATION_WINDOW_SECS,
)

__all__ = [
    'PresenceStorage',
    'CognitiveKey',
    'PresenceChallenge',
    'PresenceRecord',
    'UserPresenceStats',
    'generate_cognitive_key',
    'create_challenge',
    'verify_challenge_response',
    'calculate_next_challenge_interval',
    'format_genesis_message',
    'format_challenge_message',
    'format_stats_message',
    'TAU2_SECS',
    'VERIFICATION_WINDOW_SECS',
]

__version__ = '1.0.0'
