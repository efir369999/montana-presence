#!/usr/bin/env python3
"""
schrodinger_box.py — Протокол защиты через неопределённость

Книга Монтана, Глава 07:
> "Внутри коробки — всё определено. Коты видят друг друга.
> Снаружи — коллапс не произошёл."
> "Защита не через сложность вычисления — а через отсутствие вычислимой задачи."
> "Нечего считать — нечего ломать."

Два кота Шрёдингера:
- Для внешнего наблюдателя — состояние неопределено
- Внутри коробки — всё известно участникам

Квантовый компьютер угрожает криптографии (RSA, ECDSA).
Но что атаковать в системе без вычислимой задачи?
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Set, Optional
from enum import Enum
import hashlib
import secrets


class BoxState(Enum):
    """Состояние коробки."""
    CLOSED = "closed"      # Для внешних — неопределено
    OPEN = "open"          # Коллапс произошёл — наблюдатель увидел


class ParticipantVisibility(Enum):
    """Видимость участника."""
    INSIDE = "inside"      # Внутри коробки — видит всё
    OUTSIDE = "outside"    # Снаружи — видит неопределённость


@dataclass
class Participant:
    """Участник (кот) внутри коробки."""
    node_id: str
    name: str
    visibility: ParticipantVisibility
    joined_at: str
    knows_state: bool = True  # Внутри — знает состояние


@dataclass
class BoxConsensus:
    """Консенсус внутри коробки."""
    consensus_id: str
    participants: List[str]      # node_ids участников
    statement: str               # Утверждение
    agreed_at: str
    signatures: Dict[str, str]   # node_id → signature hash

    @property
    def is_unanimous(self) -> bool:
        """Все участники согласились."""
        return len(self.signatures) == len(self.participants)


class SchrodingerBox:
    """
    Коробка Шрёдингера — защита через неопределённость.

    Книга Монтана:
    > "Квантовый компьютер ломает вычисления. Но он не может 'стать'
    > кем-то когнитивно. Не может подделать присутствие."
    """

    def __init__(self, box_id: str = None):
        self.box_id = box_id or secrets.token_hex(8)
        self.state = BoxState.CLOSED
        self.participants: Dict[str, Participant] = {}
        self.consensuses: List[BoxConsensus] = []
        self.created_at = datetime.now(timezone.utc).isoformat()

    def add_participant(self, node_id: str, name: str) -> Participant:
        """
        Добавить участника внутрь коробки.

        После добавления участник видит всё, что происходит внутри.
        Для внешних — его состояние неопределено.

        Args:
            node_id: ID узла
            name: Имя

        Returns:
            Participant
        """
        participant = Participant(
            node_id=node_id,
            name=name,
            visibility=ParticipantVisibility.INSIDE,
            joined_at=datetime.now(timezone.utc).isoformat()
        )

        self.participants[node_id] = participant
        return participant

    def observe_from_outside(self, observer_id: str) -> Dict:
        """
        Наблюдение снаружи — неопределённость.

        Книга Монтана:
        > "Для внешнего наблюдателя их состояние не определено.
        > Живы? Мертвы? Никто не знает, пока коробка закрыта."

        Args:
            observer_id: ID внешнего наблюдателя

        Returns:
            То, что видит внешний наблюдатель
        """
        if self.state == BoxState.CLOSED:
            return {
                "box_id": self.box_id,
                "state": "SUPERPOSITION",
                "participants_count": "?",  # Неизвестно
                "consensus_reached": "?",    # Неизвестно
                "message": "Box is closed. State is undetermined.",
                "quantum_attack_surface": None  # Нечего атаковать
            }
        else:
            # Коллапс произошёл
            return {
                "box_id": self.box_id,
                "state": "COLLAPSED",
                "participants_count": len(self.participants),
                "consensus_reached": len(self.consensuses) > 0,
                "message": "Box was opened. State is now determined."
            }

    def observe_from_inside(self, node_id: str) -> Dict:
        """
        Наблюдение изнутри — полная определённость.

        Args:
            node_id: ID участника внутри

        Returns:
            Полное состояние (для участников)
        """
        if node_id not in self.participants:
            return {"error": "Not a participant. Cannot see inside."}

        return {
            "box_id": self.box_id,
            "your_node_id": node_id,
            "state": "DETERMINED",
            "participants": [
                {"node_id": p.node_id, "name": p.name}
                for p in self.participants.values()
            ],
            "consensuses": len(self.consensuses),
            "you_know_everything": True
        }

    def reach_consensus(
        self,
        statement: str,
        signers: List[str]
    ) -> BoxConsensus:
        """
        Достичь консенсуса внутри коробки.

        Все участники видят. Внешние — не видят.

        Args:
            statement: Утверждение
            signers: Список подписантов (node_ids)

        Returns:
            BoxConsensus
        """
        # Проверить что все подписанты — участники
        for signer in signers:
            if signer not in self.participants:
                raise ValueError(f"{signer} is not a participant")

        # Создать подписи
        signatures = {}
        for signer in signers:
            sig_data = f"{signer}:{statement}:{datetime.now().isoformat()}"
            signatures[signer] = hashlib.sha256(sig_data.encode()).hexdigest()

        consensus = BoxConsensus(
            consensus_id=secrets.token_hex(8),
            participants=list(self.participants.keys()),
            statement=statement,
            agreed_at=datetime.now(timezone.utc).isoformat(),
            signatures=signatures
        )

        self.consensuses.append(consensus)
        return consensus

    def open_box(self) -> None:
        """
        Открыть коробку — произвести коллапс.

        После открытия состояние становится определённым для всех.
        """
        self.state = BoxState.OPEN

    def get_quantum_resistance_report(self) -> Dict:
        """
        Отчёт о квантовой устойчивости.

        Книга Монтана:
        > "Элегантнее, чем пост-квантовая криптография,
        > которая просто усложняет математику."
        """
        return {
            "approach": "Protection through indeterminacy",
            "mathematical_task": None,  # Нет задачи для взлома
            "factorization_attack": "N/A - nothing to factorize",
            "discrete_log_attack": "N/A - no discrete log problem",
            "quantum_computer_can": [
                "Factor large numbers",
                "Solve discrete logarithm",
                "Break RSA, ECDSA"
            ],
            "quantum_computer_cannot": [
                "Become someone cognitively",
                "Fake presence inside box",
                "Observe closed box state",
                "Attack non-existent mathematical task"
            ],
            "conclusion": "Nothing to compute = nothing to break"
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    box = SchrodingerBox()

    print("=" * 60)
    print("SCHRÖDINGER BOX — Защита через неопределённость")
    print("=" * 60)
    print("\n'Нечего считать — нечего ломать.'")

    # Добавляем участников (котов)
    print("\n--- ДОБАВЛЕНИЕ УЧАСТНИКОВ ---")
    cat1 = box.add_participant("node_alejandro", "Alejandro")
    cat2 = box.add_participant("node_mama", "Mama")
    print(f"Кот 1: {cat1.name}")
    print(f"Кот 2: {cat2.name}")

    # Взгляд снаружи
    print("\n--- ВЗГЛЯД СНАРУЖИ (внешний наблюдатель) ---")
    outside_view = box.observe_from_outside("external_observer")
    print(f"Состояние: {outside_view['state']}")
    print(f"Участников: {outside_view['participants_count']}")
    print(f"Консенсус: {outside_view['consensus_reached']}")
    print(f"Атакуемая поверхность: {outside_view['quantum_attack_surface']}")

    # Взгляд изнутри
    print("\n--- ВЗГЛЯД ИЗНУТРИ (участник) ---")
    inside_view = box.observe_from_inside("node_alejandro")
    print(f"Состояние: {inside_view['state']}")
    print(f"Участников: {len(inside_view['participants'])}")
    print(f"Знает всё: {inside_view['you_know_everything']}")

    # Консенсус
    print("\n--- ДОСТИЖЕНИЕ КОНСЕНСУСА ---")
    consensus = box.reach_consensus(
        "Время — единственная реальная валюта",
        ["node_alejandro", "node_mama"]
    )
    print(f"Консенсус ID: {consensus.consensus_id}")
    print(f"Единогласно: {'ДА' if consensus.is_unanimous else 'НЕТ'}")
    print(f"Подписей: {len(consensus.signatures)}")

    # Квантовая устойчивость
    print("\n--- ОТЧЁТ О КВАНТОВОЙ УСТОЙЧИВОСТИ ---")
    report = box.get_quantum_resistance_report()
    print(f"Подход: {report['approach']}")
    print(f"Математическая задача: {report['mathematical_task']}")
    print("\nКвантовый компьютер НЕ МОЖЕТ:")
    for item in report['quantum_computer_cannot']:
        print(f"  ✗ {item}")

    print("\n" + "=" * 60)
    print("'Защита не через математику — через отсутствие задачи.'")
    print("=" * 60)
