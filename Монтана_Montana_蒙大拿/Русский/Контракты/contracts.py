#!/usr/bin/env python3
"""
КОНТРАКТЫ MONTANA — Смарт-контракты времени
============================================

Юнона = арбитр, свидетель, валидатор сделок.
Группа = контрактная комната (до 12 свидетелей).

Механика создания:
1. Диалог создания (Юнона ведёт)
2. Голосование участников (>50% за)
3. Юнона проверяет условия (ПОСЛЕДНЕЕ СЛОВО)
4. Escrow (заморозка средств)
5. Сторона Б принимает

Механика завершения (Bitcoin Pizza Style):
1. Сторона заявляет о выполнении (/contract done)
2. Стороны предоставляют доказательства (фото/видео/документы)
3. ВСЕ участники группы голосуют за валидность
4. Юнона = 2 голоса, свидетели = 1 голос
5. При кворуме + одобрении Юноны → COMPLETED

Статусы: draft → pending → accepted → completion_voting → completed
"""

import json
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum


class ContractStatus(Enum):
    """Статусы контракта"""
    DRAFT = "draft"                    # Черновик — ещё собирает голоса
    PENDING = "pending"                # Ожидает подтверждения Стороны Б
    ACCEPTED = "accepted"              # Принят, условия исполняются
    COMPLETION_VOTING = "completion_voting"  # Голосование за завершение
    COMPLETED = "completed"            # Исполнен, средства переведены
    CANCELLED = "cancelled"            # Отменён, средства разморожены
    REJECTED = "rejected"              # Отклонён большинством или Юноной


@dataclass
class ContractParty:
    """Сторона контракта"""
    user_id: str
    username: Optional[str] = None
    name: Optional[str] = None  # Имя из адресной книги

    def display_name(self) -> str:
        if self.username:
            return f"@{self.username}"
        if self.name:
            return self.name
        return str(self.user_id)


# Константы голосования
JUNONA_VOTE_WEIGHT = 2  # Юнона = 2 голоса
WITNESS_VOTE_WEIGHT = 1  # Свидетель = 1 голос
JUNONA_USER_ID = "JUNONA"  # Специальный ID для голосов Юноны


@dataclass
class Contract:
    """Контракт Montana

    Механика голосования (создание):
    1. Создаётся в статусе DRAFT
    2. Участники голосуют (approve/reject)
    3. Когда большинство (>50%) одобрили — Юнона проверяет
    4. Юнона имеет ПОСЛЕДНЕЕ СЛОВО (может отклонить даже с кворумом)
    5. После одобрения Юноной → PENDING (ждёт Сторону Б)

    Механика голосования (завершение):
    1. Сторона А заявляет о выполнении → COMPLETION_VOTING
    2. Стороны предоставляют доказательства (фото/видео/документы)
    3. Все участники голосуют за валидность исполнения
    4. Юнона = 2 голоса, свидетели = 1 голос
    5. При достижении большинства + одобрении Юноны → COMPLETED
    """
    contract_id: str
    creator: ContractParty      # Сторона А (отправитель)
    target: ContractParty       # Сторона Б (получатель)
    amount: int                 # Сумма в Ɉ
    description: str            # Условие контракта
    status: ContractStatus = ContractStatus.DRAFT
    chat_id: Optional[str] = None           # ID группы (если групповой)
    witnesses: List[str] = field(default_factory=list)  # ID участников комнаты
    votes_approve: List[str] = field(default_factory=list)  # ID тех кто одобрил создание
    votes_reject: List[str] = field(default_factory=list)   # ID тех кто отклонил создание
    junona_approved: Optional[bool] = None  # Последнее слово Юноны (создание)
    junona_reason: Optional[str] = None     # Причина решения Юноны
    # Голосование за завершение
    completion_votes_approve: List[str] = field(default_factory=list)  # За исполнение
    completion_votes_reject: List[str] = field(default_factory=list)   # Против исполнения
    junona_completion_approved: Optional[bool] = None  # Юнона подтвердила завершение
    junona_completion_reason: Optional[str] = None     # Причина решения по завершению
    created_at: Optional[str] = None
    accepted_at: Optional[str] = None
    completed_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    escrow_tx_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "contract_id": self.contract_id,
            "creator_id": self.creator.user_id,
            "creator_username": self.creator.username,
            "target_id": self.target.user_id,
            "target_username": self.target.username,
            "amount": self.amount,
            "description": self.description,
            "status": self.status.value,
            "chat_id": self.chat_id,
            "witnesses": self.witnesses,
            "votes_approve": self.votes_approve,
            "votes_reject": self.votes_reject,
            "junona_approved": self.junona_approved,
            "junona_reason": self.junona_reason,
            # Голосование за завершение
            "completion_votes_approve": self.completion_votes_approve,
            "completion_votes_reject": self.completion_votes_reject,
            "junona_completion_approved": self.junona_completion_approved,
            "junona_completion_reason": self.junona_completion_reason,
            "created_at": self.created_at,
            "accepted_at": self.accepted_at,
            "completed_at": self.completed_at,
            "cancelled_at": self.cancelled_at,
            "escrow_tx_id": self.escrow_tx_id
        }

    # ───────────────────────────────────────────────────────────────
    # КОНСЕНСУС: Большинство + Юнона
    # ───────────────────────────────────────────────────────────────

    def vote(self, user_id: str, approve: bool) -> Tuple[bool, str]:
        """Участник голосует за/против контракта

        Returns:
            (success, message)
        """
        # Можно голосовать только в статусе DRAFT
        if self.status != ContractStatus.DRAFT:
            return False, "Голосование закрыто"

        # Только участники комнаты могут голосовать
        if user_id not in self.witnesses:
            return False, "Только участники комнаты могут голосовать"

        # Убираем из предыдущего списка если передумал
        if user_id in self.votes_approve:
            self.votes_approve.remove(user_id)
        if user_id in self.votes_reject:
            self.votes_reject.remove(user_id)

        # Добавляем голос
        if approve:
            self.votes_approve.append(user_id)
        else:
            self.votes_reject.append(user_id)

        return True, "Голос принят"

    def get_quorum_status(self) -> Dict:
        """Статус кворума

        Returns:
            {
                "total": количество участников,
                "voted": проголосовало,
                "approve": за,
                "reject": против,
                "has_quorum": достигнут ли кворум (>50% за),
                "ready_for_junona": можно ли отдать на решение Юноне
            }
        """
        total = len(self.witnesses) if self.witnesses else 1
        approve = len(self.votes_approve)
        reject = len(self.votes_reject)
        voted = approve + reject

        # Кворум = большинство (>50%) проголосовало ЗА
        has_quorum = approve > total / 2

        return {
            "total": total,
            "voted": voted,
            "approve": approve,
            "reject": reject,
            "has_quorum": has_quorum,
            "ready_for_junona": has_quorum  # Юнона решает когда есть кворум
        }

    def junona_decision(self, approve: bool, reason: str = None) -> Tuple[bool, str]:
        """Юнона принимает финальное решение

        ПОСЛЕДНЕЕ СЛОВО: Юнона может отклонить даже с кворумом
        если условия невыполнимы или опасны.

        Returns:
            (success, message)
        """
        if self.status != ContractStatus.DRAFT:
            return False, "Контракт не в статусе ожидания"

        quorum = self.get_quorum_status()
        if not quorum["ready_for_junona"]:
            return False, f"Нет кворума: {quorum['approve']}/{quorum['total']} (нужно >{quorum['total']//2})"

        self.junona_approved = approve
        self.junona_reason = reason

        if approve:
            self.status = ContractStatus.PENDING
            return True, "Контракт одобрен. Ожидает подтверждения Стороны Б"
        else:
            self.status = ContractStatus.REJECTED
            return True, f"Контракт отклонён Юноной: {reason or 'условия невыполнимы'}"

    # ───────────────────────────────────────────────────────────────
    # ГОЛОСОВАНИЕ ЗА ЗАВЕРШЕНИЕ (Bitcoin Pizza Style)
    # ───────────────────────────────────────────────────────────────

    def start_completion_voting(self) -> Tuple[bool, str]:
        """Запустить голосование за завершение

        Вызывается когда сторона заявляет о выполнении условий.
        Переводит контракт в статус COMPLETION_VOTING.

        Returns:
            (success, message)
        """
        if self.status != ContractStatus.ACCEPTED:
            return False, f"Голосование можно начать только для принятого контракта (сейчас: {self.status.value})"

        self.status = ContractStatus.COMPLETION_VOTING
        self.completion_votes_approve = []
        self.completion_votes_reject = []
        self.junona_completion_approved = None
        self.junona_completion_reason = None

        return True, "Голосование за завершение началось. Свидетели, проверьте доказательства!"

    def vote_completion(self, user_id: str, approve: bool, is_junona: bool = False) -> Tuple[bool, str]:
        """Голосование за завершение контракта

        ВЕСА ГОЛОСОВ:
        - Юнона = 2 голоса (JUNONA_VOTE_WEIGHT)
        - Свидетель = 1 голос (WITNESS_VOTE_WEIGHT)

        Args:
            user_id: ID голосующего
            approve: True = за завершение, False = против
            is_junona: True если голосует Юнона

        Returns:
            (success, message)
        """
        if self.status != ContractStatus.COMPLETION_VOTING:
            return False, "Голосование за завершение не активно"

        # Юнона голосует отдельно
        if is_junona:
            if self.junona_completion_approved is not None:
                return False, "Юнона уже проголосовала"
            self.junona_completion_approved = approve
            weight = JUNONA_VOTE_WEIGHT
            voter = "Юнона"
        else:
            # Только участники комнаты могут голосовать
            if user_id not in self.witnesses:
                return False, "Только участники комнаты могут голосовать"

            # Убираем из предыдущего списка если передумал
            if user_id in self.completion_votes_approve:
                self.completion_votes_approve.remove(user_id)
            if user_id in self.completion_votes_reject:
                self.completion_votes_reject.remove(user_id)

            weight = WITNESS_VOTE_WEIGHT
            voter = user_id

        # Добавляем голос
        if approve:
            if not is_junona:
                self.completion_votes_approve.append(user_id)
        else:
            if not is_junona:
                self.completion_votes_reject.append(user_id)

        return True, f"Голос принят ({voter}, вес: {weight})"

    def get_completion_quorum_status(self) -> Dict:
        """Статус кворума для завершения

        ВЕСА:
        - Юнона = 2 голоса
        - Свидетель = 1 голос

        Returns:
            {
                "total_weight": общий вес всех голосов,
                "approve_weight": вес за исполнение,
                "reject_weight": вес против,
                "has_quorum": достигнут ли кворум (>50% за),
                "junona_voted": проголосовала ли Юнона,
                "junona_approved": одобрила ли Юнона,
                "ready_to_complete": можно ли завершить
            }
        """
        # Считаем веса
        witness_approve = len(self.completion_votes_approve) * WITNESS_VOTE_WEIGHT
        witness_reject = len(self.completion_votes_reject) * WITNESS_VOTE_WEIGHT

        # Юнона
        junona_weight = 0
        junona_voted = self.junona_completion_approved is not None
        if junona_voted:
            if self.junona_completion_approved:
                junona_weight = JUNONA_VOTE_WEIGHT
            else:
                junona_weight = -JUNONA_VOTE_WEIGHT  # Против

        # Общий вес
        total_witnesses = len(self.witnesses) if self.witnesses else 1
        total_weight = total_witnesses * WITNESS_VOTE_WEIGHT + JUNONA_VOTE_WEIGHT

        approve_weight = witness_approve + (JUNONA_VOTE_WEIGHT if self.junona_completion_approved else 0)
        reject_weight = witness_reject + (JUNONA_VOTE_WEIGHT if self.junona_completion_approved is False else 0)

        # Кворум = большинство (>50%) за
        has_quorum = approve_weight > total_weight / 2

        # Готово к завершению: кворум + Юнона одобрила
        ready_to_complete = has_quorum and self.junona_completion_approved is True

        return {
            "total_weight": total_weight,
            "approve_weight": approve_weight,
            "reject_weight": reject_weight,
            "witnesses_voted": len(self.completion_votes_approve) + len(self.completion_votes_reject),
            "total_witnesses": total_witnesses,
            "has_quorum": has_quorum,
            "junona_voted": junona_voted,
            "junona_approved": self.junona_completion_approved,
            "ready_to_complete": ready_to_complete
        }

    def junona_completion_decision(self, approve: bool, reason: str = None) -> Tuple[bool, str]:
        """Юнона принимает финальное решение по завершению

        ПОСЛЕДНЕЕ СЛОВО: Даже при кворуме свидетелей, Юнона может отклонить.

        Returns:
            (success, message)
        """
        if self.status != ContractStatus.COMPLETION_VOTING:
            return False, "Контракт не в статусе голосования за завершение"

        self.junona_completion_approved = approve
        self.junona_completion_reason = reason

        quorum = self.get_completion_quorum_status()

        if approve and quorum["has_quorum"]:
            self.status = ContractStatus.COMPLETED
            return True, "Контракт исполнен! Свидетели подтвердили, Юнона одобрила."
        elif not approve:
            return True, f"Юнона не подтвердила завершение: {reason or 'требуются дополнительные доказательства'}"
        else:
            return True, f"Юнона одобрила, но нет кворума свидетелей ({quorum['approve_weight']}/{quorum['total_weight']})"

    @classmethod
    def from_dict(cls, data: Dict) -> "Contract":
        # Парсим JSON поля
        def parse_json_list(val):
            if not val:
                return []
            if isinstance(val, list):
                return val
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return []

        return cls(
            contract_id=data["contract_id"],
            creator=ContractParty(
                user_id=data["creator_id"],
                username=data.get("creator_username")
            ),
            target=ContractParty(
                user_id=data["target_id"],
                username=data.get("target_username")
            ),
            amount=data["amount"],
            description=data.get("description", ""),
            status=ContractStatus(data.get("status", "draft")),
            chat_id=data.get("chat_id"),
            witnesses=parse_json_list(data.get("witnesses")),
            votes_approve=parse_json_list(data.get("votes_approve")),
            votes_reject=parse_json_list(data.get("votes_reject")),
            junona_approved=data.get("junona_approved"),
            junona_reason=data.get("junona_reason"),
            # Голосование за завершение
            completion_votes_approve=parse_json_list(data.get("completion_votes_approve")),
            completion_votes_reject=parse_json_list(data.get("completion_votes_reject")),
            junona_completion_approved=data.get("junona_completion_approved"),
            junona_completion_reason=data.get("junona_completion_reason"),
            created_at=data.get("created_at"),
            accepted_at=data.get("accepted_at"),
            completed_at=data.get("completed_at"),
            cancelled_at=data.get("cancelled_at"),
            escrow_tx_id=data.get("escrow_tx_id")
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ГЕНЕРАЦИЯ ID
# ═══════════════════════════════════════════════════════════════════════════════

def generate_contract_id(prefix: str = "CONTRACT") -> str:
    """
    Генерирует уникальный ID контракта

    Формат: PREFIX-XXXX (например PIZZA-A7F3)
    """
    suffix = secrets.token_hex(2).upper()
    return f"{prefix}-{suffix}"


# ═══════════════════════════════════════════════════════════════════════════════
# ФОРМАТИРОВАНИЕ
# ═══════════════════════════════════════════════════════════════════════════════

def format_contract_card(contract: Contract, lang: str = "ru") -> str:
    """
    Форматирует карточку контракта для отображения в чате

    Args:
        contract: Объект контракта
        lang: Язык (ru/en/zh)
    """
    status_emoji = {
        ContractStatus.DRAFT: "📝",
        ContractStatus.PENDING: "⏳",
        ContractStatus.ACCEPTED: "✅",
        ContractStatus.COMPLETION_VOTING: "🗳️",
        ContractStatus.COMPLETED: "🎉",
        ContractStatus.CANCELLED: "❌",
        ContractStatus.REJECTED: "🚫"
    }

    status_text_map = {
        "ru": {
            ContractStatus.DRAFT: "ГОЛОСОВАНИЕ",
            ContractStatus.PENDING: "ОЖИДАЕТ ПОДТВЕРЖДЕНИЯ",
            ContractStatus.ACCEPTED: "ПРИНЯТ",
            ContractStatus.COMPLETION_VOTING: "ГОЛОСОВАНИЕ ЗА ЗАВЕРШЕНИЕ",
            ContractStatus.COMPLETED: "ИСПОЛНЕН",
            ContractStatus.CANCELLED: "ОТМЕНЁН",
            ContractStatus.REJECTED: "ОТКЛОНЁН"
        },
        "en": {
            ContractStatus.DRAFT: "VOTING",
            ContractStatus.PENDING: "PENDING CONFIRMATION",
            ContractStatus.ACCEPTED: "ACCEPTED",
            ContractStatus.COMPLETION_VOTING: "COMPLETION VOTING",
            ContractStatus.COMPLETED: "COMPLETED",
            ContractStatus.CANCELLED: "CANCELLED",
            ContractStatus.REJECTED: "REJECTED"
        }
    }
    status_text = status_text_map.get(lang, status_text_map["ru"]).get(
        contract.status, contract.status.value.upper()
    )

    # Блок участников и голосования (создание)
    participants_str = ""
    if contract.witnesses:
        total = len(contract.witnesses)
        approve = len(contract.votes_approve)
        reject = len(contract.votes_reject)
        participants_str = f"\n║  Участники: {total} чел."

        # Голосование за создание (если в DRAFT)
        if contract.status == ContractStatus.DRAFT:
            participants_str += f"\n║  Голоса: ✅ {approve} / ❌ {reject}"
            quorum = contract.get_quorum_status()
            if quorum["has_quorum"]:
                participants_str += " (КВОРУМ ✓)"
            else:
                need = total // 2 + 1
                participants_str += f" (нужно {need})"

    # Блок голосования за завершение (если COMPLETION_VOTING)
    completion_str = ""
    if contract.status == ContractStatus.COMPLETION_VOTING:
        quorum = contract.get_completion_quorum_status()
        completion_str = f"\n║  ─── ГОЛОСОВАНИЕ ЗА ЗАВЕРШЕНИЕ ───"
        completion_str += f"\n║  Голоса: ✅ {quorum['approve_weight']} / ❌ {quorum['reject_weight']} (всего: {quorum['total_weight']})"
        completion_str += f"\n║  Свидетелей: {quorum['witnesses_voted']}/{quorum['total_witnesses']}"
        if quorum['junona_voted']:
            junona_vote = "✅" if quorum['junona_approved'] else "❌"
            completion_str += f"\n║  Юнона (2 голоса): {junona_vote}"
        else:
            completion_str += f"\n║  Юнона: ожидает..."
        if quorum['ready_to_complete']:
            completion_str += f"\n║  🎯 ГОТОВО К ЗАВЕРШЕНИЮ!"

    # Решение Юноны (создание)
    junona_str = ""
    if contract.junona_approved is not None and contract.status not in [ContractStatus.COMPLETION_VOTING, ContractStatus.COMPLETED]:
        if contract.junona_approved:
            junona_str = "\n║  🤖 Юнона: ОДОБРЕНО"
        else:
            reason = contract.junona_reason or "условия невыполнимы"
            junona_str = f"\n║  🤖 Юнона: ОТКЛОНЕНО ({reason[:30]})"

    card = f"""
╔═══════════════════════════════════════════════════╗
║          КОНТРАКТ MONTANA #{contract.contract_id}
╠═══════════════════════════════════════════════════╣
║  Сторона А: {contract.creator.display_name()}
║  Сторона Б: {contract.target.display_name()}
║  Сумма: {contract.amount:,} Ɉ
║  Условие: {contract.description[:40]}{'...' if len(contract.description) > 40 else ''}
╠═══════════════════════════════════════════════════╣{participants_str}{completion_str}{junona_str}
║  Статус: {status_emoji.get(contract.status, '❓')} {status_text}
╚═══════════════════════════════════════════════════╝
"""
    return card.strip()


def format_contract_mini(contract: Contract) -> str:
    """Короткий формат для списков"""
    status_emoji = {
        ContractStatus.DRAFT: "📝",
        ContractStatus.PENDING: "⏳",
        ContractStatus.ACCEPTED: "✅",
        ContractStatus.COMPLETION_VOTING: "🗳️",
        ContractStatus.COMPLETED: "🎉",
        ContractStatus.CANCELLED: "❌",
        ContractStatus.REJECTED: "🚫"
    }
    return f"{status_emoji.get(contract.status, '❓')} #{contract.contract_id}: {contract.amount:,} Ɉ → {contract.target.display_name()}"


# ═══════════════════════════════════════════════════════════════════════════════
# ВАЛИДАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ValidationResult:
    """Результат валидации"""
    valid: bool
    error: Optional[str] = None
    error_code: Optional[str] = None


def validate_contract_creation(
    creator_id: str,
    target_id: str,
    amount: int,
    creator_balance: int,
    description: str = None
) -> ValidationResult:
    """
    Валидирует создание контракта

    Проверяет:
    - Получатель найден
    - Сумма > 0
    - Баланс >= суммы
    - Описание не пустое
    """
    # Проверка получателя
    if not target_id:
        return ValidationResult(
            valid=False,
            error="Получатель не указан",
            error_code="NO_TARGET"
        )

    # Нельзя отправлять себе
    if str(creator_id) == str(target_id):
        return ValidationResult(
            valid=False,
            error="Нельзя создать контракт с самим собой",
            error_code="SELF_CONTRACT"
        )

    # Проверка суммы
    if amount <= 0:
        return ValidationResult(
            valid=False,
            error="Сумма должна быть больше 0",
            error_code="INVALID_AMOUNT"
        )

    # Проверка баланса
    if creator_balance < amount:
        return ValidationResult(
            valid=False,
            error=f"Недостаточно средств: {creator_balance} Ɉ < {amount} Ɉ",
            error_code="INSUFFICIENT_BALANCE"
        )

    # Проверка описания
    if not description or len(description.strip()) < 3:
        return ValidationResult(
            valid=False,
            error="Укажите условие контракта (минимум 3 символа)",
            error_code="NO_DESCRIPTION"
        )

    return ValidationResult(valid=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ЮНОНА — РЕГУЛЯТОР ДОГОВОРЁННОСТЕЙ
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ExecutabilityCheck:
    """Результат проверки исполнимости"""
    executable: bool
    confidence: float  # 0.0 - 1.0
    concerns: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


def check_executability(description: str) -> ExecutabilityCheck:
    """
    Юнона проверяет исполнимость условия контракта

    Проверяет:
    - Конкретность (не абстрактно ли условие?)
    - Верифицируемость (как понять что выполнено?)
    - Временные рамки (когда должно быть выполнено?)
    - Реалистичность (возможно ли это физически?)

    Возвращает оценку и рекомендации
    """
    concerns = []
    suggestions = []
    confidence = 1.0

    desc_lower = description.lower()

    # Слишком короткое описание
    if len(description) < 10:
        confidence -= 0.3
        concerns.append("Условие слишком краткое")
        suggestions.append("Опиши подробнее что именно должно быть сделано")

    # Абстрактные формулировки
    abstract_words = ["помощь", "поддержка", "содействие", "что-то", "как-нибудь"]
    for word in abstract_words:
        if word in desc_lower:
            confidence -= 0.2
            concerns.append(f"Слово '{word}' слишком абстрактно")
            suggestions.append("Укажи конкретный результат")

    # Нет временных рамок
    time_words = ["сегодня", "завтра", "до", "через", "в течение", "час", "день", "неделя"]
    has_time = any(word in desc_lower for word in time_words)
    if not has_time:
        confidence -= 0.1
        concerns.append("Не указаны сроки")
        suggestions.append("Добавь когда должно быть выполнено")

    # Как верифицировать?
    verify_words = ["фото", "скриншот", "чек", "видео", "отчёт", "доказательство"]
    has_verification = any(word in desc_lower for word in verify_words)
    if not has_verification and confidence > 0.5:
        suggestions.append("Как я пойму что условие выполнено? Добавь способ подтверждения")

    # Ограничиваем confidence
    confidence = max(0.1, min(1.0, confidence))

    return ExecutabilityCheck(
        executable=confidence >= 0.5,
        confidence=confidence,
        concerns=concerns,
        suggestions=suggestions
    )


@dataclass
class GroupContractRoom:
    """
    Контрактная комната (группа)

    Юнона управляет всеми договорённостями в группе.
    До 12 участников могут быть сторонами контрактов.
    Все участники = потенциальные стороны контракта.
    Большинство должно одобрить + Юнона принимает финальное решение.
    """
    chat_id: str
    participants: List[str] = field(default_factory=list)  # До 12 участников
    active_contracts: List[str] = field(default_factory=list)  # ID активных контрактов
    total_volume: int = 0  # Общий объём сделок в Ɉ
    _verified_members: List[str] = field(default_factory=list)  # Верифицированные через Telegram API

    MAX_PARTICIPANTS = 12

    def add_participant(self, user_id: str, verified: bool = False) -> bool:
        """Добавить участника

        Args:
            user_id: ID пользователя
            verified: True если подтверждён через Telegram API (реальный участник группы)
        """
        if len(self.participants) >= self.MAX_PARTICIPANTS:
            return False
        if user_id not in self.participants:
            self.participants.append(user_id)
            if verified:
                self._verified_members.append(user_id)
        return True

    def is_verified_member(self, user_id: str) -> bool:
        """Проверяет верифицирован ли участник (через Telegram API)"""
        return user_id in self._verified_members

    def validate_witnesses(self, witness_ids: List[str]) -> Tuple[bool, str, List[str]]:
        """
        Валидирует список свидетелей

        DISNEY-SAFE: Нельзя указать произвольные ID как свидетелей.
        Только верифицированные участники группы.

        Returns:
            (valid, error_message, valid_witnesses)
        """
        valid_witnesses = []
        invalid = []

        for wid in witness_ids:
            if wid in self.participants:
                valid_witnesses.append(wid)
            else:
                invalid.append(wid)

        if invalid:
            return False, f"Участники {invalid} не в группе", valid_witnesses

        return True, "OK", valid_witnesses

    def can_create_contract(self, creator_id: str, target_id: str) -> Tuple[bool, str]:
        """Проверяет можно ли создать контракт между участниками"""
        if creator_id not in self.participants:
            return False, f"Пользователь {creator_id} не участник комнаты"
        if target_id not in self.participants:
            return False, f"Пользователь {target_id} не участник комнаты"
        return True, "OK"

    def get_witnesses(self, exclude: List[str] = None) -> List[str]:
        """Возвращает всех участников кроме исключённых (для голосования)"""
        exclude = exclude or []
        return [p for p in self.participants if p not in exclude]

    def get_quorum_threshold(self) -> int:
        """Порог кворума: >50% участников должны одобрить"""
        return len(self.participants) // 2 + 1


# ═══════════════════════════════════════════════════════════════════════════════
# ДИАЛОГ КОНТРАКТА
# ═══════════════════════════════════════════════════════════════════════════════

class ContractDialogState(Enum):
    """Состояния диалога создания контракта"""
    IDLE = "idle"
    WAITING_TARGET = "waiting_target"
    WAITING_AMOUNT = "waiting_amount"
    WAITING_DESCRIPTION = "waiting_description"
    WAITING_CONFIRMATION = "waiting_confirmation"


@dataclass
class ContractDialog:
    """Диалог создания контракта"""
    creator_id: str
    chat_id: Optional[str] = None
    state: ContractDialogState = ContractDialogState.IDLE
    target_id: Optional[str] = None
    target_username: Optional[str] = None
    amount: Optional[int] = None
    description: Optional[str] = None
    witnesses: List[str] = field(default_factory=list)

    def next_prompt(self, lang: str = "ru") -> str:
        """Возвращает следующий вопрос для диалога"""
        prompts = {
            ContractDialogState.WAITING_TARGET: "Кто будет второй стороной? Укажи @username, ID или имя из контактов",
            ContractDialogState.WAITING_AMOUNT: "Какую сумму хочешь заморозить в контракте? (в Ɉ)",
            ContractDialogState.WAITING_DESCRIPTION: "Что получишь взамен? Опиши условие контракта",
            ContractDialogState.WAITING_CONFIRMATION: "Проверь контракт. Всё верно?"
        }
        return prompts.get(self.state, "")

    def is_complete(self) -> bool:
        """Проверяет готовность к созданию контракта"""
        return all([
            self.target_id,
            self.amount and self.amount > 0,
            self.description
        ])


# ═══════════════════════════════════════════════════════════════════════════════
# РЕЗОЛВЕР ПОЛУЧАТЕЛЯ
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_target(
    input_str: str,
    contacts: List[Dict] = None,
    reply_user_id: str = None
) -> Tuple[Optional[str], Optional[str], str]:
    """
    Резолвит получателя из разных форматов

    Args:
        input_str: Ввод пользователя (@username, ID, имя)
        contacts: Адресная книга пользователя
        reply_user_id: ID из reply на сообщение

    Returns:
        (user_id, username, method) или (None, None, error)
    """
    input_str = input_str.strip()

    # 1. Reply на сообщение
    if reply_user_id:
        return reply_user_id, None, "reply"

    # 2. @username
    if input_str.startswith("@"):
        username = input_str[1:]
        # В реальности нужно резолвить через Telegram API
        return None, username, "username"

    # 3. Числовой ID
    if input_str.isdigit():
        return input_str, None, "id"

    # 4. Поиск в адресной книге
    if contacts:
        for contact in contacts:
            if contact.get("name", "").lower() == input_str.lower():
                return contact["target_id"], contact.get("target_username"), "contacts"

    return None, None, f"Не удалось найти '{input_str}'. Укажи @username или ID"


# ═══════════════════════════════════════════════════════════════════════════════
# УТИЛИТЫ
# ═══════════════════════════════════════════════════════════════════════════════

def now_iso() -> str:
    """Текущее время в ISO формате"""
    return datetime.now(timezone.utc).isoformat()


def parse_amount(text: str) -> Optional[int]:
    """Парсит сумму из текста"""
    # Убираем пробелы, запятые, символ валюты
    cleaned = text.replace(" ", "").replace(",", "").replace("Ɉ", "").strip()
    try:
        amount = int(cleaned)
        return amount if amount > 0 else None
    except ValueError:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Пример создания контракта
    contract = Contract(
        contract_id=generate_contract_id("PIZZA"),
        creator=ContractParty(user_id="8552053404", username="financier"),
        target=ContractParty(user_id="987654321", username="pizza_place"),
        amount=10000,
        description="Большая пицца пепперони за консультацию",
        chat_id="-1001234567890",
        witnesses=["111", "222", "333"],
        created_at=now_iso()
    )

    print(format_contract_card(contract))
    print()
    print("Mini:", format_contract_mini(contract))
    print()
    print("Dict:", json.dumps(contract.to_dict(), indent=2, ensure_ascii=False))
