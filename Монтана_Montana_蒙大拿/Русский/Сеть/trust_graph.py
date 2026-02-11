#!/usr/bin/env python3
"""
trust_graph.py — Граф доверия Montana

Книга Монтана, Глава 03:
> "Это не blockchain. Это — trust graph через когнитивные подписи."
> "Узлы связаны через взаимные признания."
> "Я узнаю свой стиль. Дато говорит 'вот именно'. Мама держит за слово."

Trust Graph отличается от blockchain:
- Blockchain: защита математикой (сложность вычислений)
- Trust Graph: защита очевидностью (невозможность быть другим)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Set, Optional, Tuple
from enum import Enum
import hashlib
import json


class RecognitionType(Enum):
    """Типы узнавания в Trust Graph."""
    STYLE = "style"           # Узнаю стиль мышления
    VOICE = "voice"           # Узнаю голос
    PATTERN = "pattern"       # Узнаю паттерн поведения
    MEMORY = "memory"         # Общая память (только мы знаем)
    FAMILY = "family"         # Семейная связь
    TRUST = "trust"           # Прямое доверие


@dataclass
class Recognition:
    """Акт узнавания между двумя узлами."""
    from_node: str                    # Кто узнаёт
    to_node: str                      # Кого узнаёт
    recognition_type: RecognitionType # Тип узнавания
    timestamp: str                    # Когда произошло
    evidence: str                     # Доказательство (цитата, факт)
    confidence: float                 # Уверенность 0.0-1.0

    def to_dict(self) -> dict:
        return {
            "from": self.from_node,
            "to": self.to_node,
            "type": self.recognition_type.value,
            "timestamp": self.timestamp,
            "evidence": self.evidence,
            "confidence": self.confidence
        }


@dataclass
class TrustNode:
    """Узел в графе доверия."""
    node_id: str                      # Уникальный ID
    name: str                         # Имя/псевдоним
    cognitive_signature: str          # Hash когнитивной подписи
    created_at: str                   # Дата создания
    recognitions_given: List[str] = field(default_factory=list)    # Кого узнал
    recognitions_received: List[str] = field(default_factory=list) # Кто узнал

    @property
    def trust_score(self) -> float:
        """
        Score доверия на основе взаимных признаний.
        Взаимное признание весит больше одностороннего.
        """
        mutual = len(set(self.recognitions_given) & set(self.recognitions_received))
        one_way = len(self.recognitions_received) - mutual

        # Взаимные × 2 + односторонние × 1
        return mutual * 2.0 + one_way * 1.0


class TrustGraph:
    """
    Граф доверия Montana.

    Книга Монтана:
    > "Blockchain защищает данные математикой.
    > Montana защищает данные очевидностью."
    """

    def __init__(self):
        self.nodes: Dict[str, TrustNode] = {}
        self.recognitions: List[Recognition] = []
        self.edges: Dict[Tuple[str, str], Recognition] = {}

    def add_node(
        self,
        node_id: str,
        name: str,
        cognitive_signature: str
    ) -> TrustNode:
        """Добавить узел в граф."""
        if node_id in self.nodes:
            return self.nodes[node_id]

        node = TrustNode(
            node_id=node_id,
            name=name,
            cognitive_signature=cognitive_signature,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        self.nodes[node_id] = node
        return node

    def recognize(
        self,
        from_node_id: str,
        to_node_id: str,
        recognition_type: RecognitionType,
        evidence: str,
        confidence: float = 1.0
    ) -> Recognition:
        """
        Узел from_node узнаёт узел to_node.

        Args:
            from_node_id: Кто узнаёт
            to_node_id: Кого узнаёт
            recognition_type: Тип узнавания
            evidence: Доказательство (цитата, факт)
            confidence: Уверенность 0.0-1.0

        Returns:
            Recognition объект
        """
        if from_node_id not in self.nodes:
            raise ValueError(f"Node {from_node_id} not found")
        if to_node_id not in self.nodes:
            raise ValueError(f"Node {to_node_id} not found")

        recognition = Recognition(
            from_node=from_node_id,
            to_node=to_node_id,
            recognition_type=recognition_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            evidence=evidence,
            confidence=confidence
        )

        self.recognitions.append(recognition)
        self.edges[(from_node_id, to_node_id)] = recognition

        # Обновить узлы
        self.nodes[from_node_id].recognitions_given.append(to_node_id)
        self.nodes[to_node_id].recognitions_received.append(from_node_id)

        return recognition

    def is_mutual(self, node_a: str, node_b: str) -> bool:
        """Проверить взаимное признание."""
        return (
            (node_a, node_b) in self.edges and
            (node_b, node_a) in self.edges
        )

    def get_trust_path(
        self,
        from_node: str,
        to_node: str,
        max_depth: int = 5
    ) -> Optional[List[str]]:
        """
        Найти путь доверия между двумя узлами.

        Returns:
            Список узлов от from_node до to_node, или None если пути нет
        """
        if from_node not in self.nodes or to_node not in self.nodes:
            return None

        # BFS
        visited = {from_node}
        queue = [(from_node, [from_node])]

        while queue:
            current, path = queue.pop(0)

            if len(path) > max_depth:
                continue

            if current == to_node:
                return path

            for neighbor in self.nodes[current].recognitions_given:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def get_web_of_trust(self, node_id: str, depth: int = 2) -> Dict:
        """
        Получить "паутину доверия" вокруг узла.

        Returns:
            Dict с узлами и связями на глубину depth
        """
        if node_id not in self.nodes:
            return {"nodes": [], "edges": []}

        visited = {node_id}
        result_nodes = [node_id]
        result_edges = []

        current_level = {node_id}

        for _ in range(depth):
            next_level = set()

            for node in current_level:
                # Исходящие связи
                for target in self.nodes[node].recognitions_given:
                    if target not in visited:
                        visited.add(target)
                        next_level.add(target)
                        result_nodes.append(target)
                    result_edges.append((node, target))

                # Входящие связи
                for source in self.nodes[node].recognitions_received:
                    if source not in visited:
                        visited.add(source)
                        next_level.add(source)
                        result_nodes.append(source)
                    result_edges.append((source, node))

            current_level = next_level

        return {
            "center": node_id,
            "nodes": result_nodes,
            "edges": list(set(result_edges)),
            "depth": depth
        }

    def calculate_network_trust(self) -> Dict:
        """Рассчитать общие метрики доверия сети."""
        if not self.nodes:
            return {"total_nodes": 0, "total_edges": 0}

        mutual_count = sum(
            1 for (a, b) in self.edges
            if (b, a) in self.edges
        ) // 2

        return {
            "total_nodes": len(self.nodes),
            "total_recognitions": len(self.recognitions),
            "mutual_recognitions": mutual_count,
            "average_trust_score": sum(n.trust_score for n in self.nodes.values()) / len(self.nodes),
            "network_density": len(self.edges) / (len(self.nodes) * (len(self.nodes) - 1)) if len(self.nodes) > 1 else 0
        }


# ═══════════════════════════════════════════════════════════════════════════════
#                         DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    graph = TrustGraph()

    print("=" * 60)
    print("TRUST GRAPH — Граф доверия Montana")
    print("=" * 60)
    print("\n'Blockchain защищает математикой. Montana защищает очевидностью.'")

    # Создаём узлы (из книги)
    alejandro = graph.add_node("alejandro", "Alejandro Montana", "hash_alejandro")
    mama = graph.add_node("mama", "Мама", "hash_mama")
    dato = graph.add_node("dato", "Дато", "hash_dato")
    ilya = graph.add_node("ilya", "Илья", "hash_ilya")
    roma = graph.add_node("roma", "Рома", "hash_roma")

    # Семейные признания (из главы 03)
    graph.recognize("alejandro", "mama", RecognitionType.FAMILY,
                    "Мама у меня классная")
    graph.recognize("mama", "alejandro", RecognitionType.FAMILY,
                    "Анасун — дук ктеснес")

    graph.recognize("alejandro", "dato", RecognitionType.STYLE,
                    "Дато говорит 'вот именно'")
    graph.recognize("dato", "alejandro", RecognitionType.TRUST,
                    "Если не ты, то кто?")

    graph.recognize("alejandro", "ilya", RecognitionType.PATTERN,
                    "Илья — прагматик")
    graph.recognize("ilya", "alejandro", RecognitionType.PATTERN,
                    "Зачем пытаешься один переплюнуть Биток?")

    graph.recognize("roma", "alejandro", RecognitionType.TRUST,
                    "Если взял за хвост — тащи до конца")

    # Статистика
    print("\n--- УЗЛЫ ---")
    for node_id, node in graph.nodes.items():
        mutual = set(node.recognitions_given) & set(node.recognitions_received)
        print(f"{node.name}: trust_score={node.trust_score:.1f}, "
              f"взаимных={len(mutual)}")

    print("\n--- ВЗАИМНЫЕ ПРИЗНАНИЯ ---")
    for (a, b) in graph.edges:
        if graph.is_mutual(a, b) and a < b:
            print(f"  {graph.nodes[a].name} ↔ {graph.nodes[b].name}")

    print("\n--- МЕТРИКИ СЕТИ ---")
    metrics = graph.calculate_network_trust()
    print(f"Узлов: {metrics['total_nodes']}")
    print(f"Признаний: {metrics['total_recognitions']}")
    print(f"Взаимных: {metrics['mutual_recognitions']}")
    print(f"Средний trust score: {metrics['average_trust_score']:.2f}")

    print("\n--- ПУТЬ ДОВЕРИЯ ---")
    path = graph.get_trust_path("roma", "mama")
    if path:
        names = [graph.nodes[n].name for n in path]
        print(f"Рома → Мама: {' → '.join(names)}")

    print("\n" + "=" * 60)
    print("'Узлы связаны через взаимные признания.'")
    print("=" * 60)
