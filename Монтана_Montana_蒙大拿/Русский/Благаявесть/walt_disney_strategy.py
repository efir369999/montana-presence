#!/usr/bin/env python3
"""
Walt Disney Strategy для Montana
================================

Три роли:
- МЕЧТАТЕЛЬ (Dreamer) — генерирует идеальное видение
- РЕАЛИСТ (Realist) — создаёт план реализации
- КРИТИК (Critic) — находит слабости и улучшения

Использование:
    python walt_disney_strategy.py --vision "Создать аудиокнигу 1 серии"
    python walt_disney_strategy.py --analyze путь/к/проекту
    python walt_disney_strategy.py --report
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import argparse


@dataclass
class DreamerOutput:
    """Выход роли Мечтателя"""
    vision: str
    ideal_outcome: str
    innovations: list[str]
    possibilities: list[str]
    score: int  # 1-10
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RealistOutput:
    """Выход роли Реалиста"""
    working: list[str]
    missing: list[str]
    resources_needed: list[str]
    timeline_steps: list[str]
    score: int  # 1-10
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CriticOutput:
    """Выход роли Критика"""
    critical_issues: list[dict]  # {problem, solution, priority}
    important_issues: list[dict]
    minor_issues: list[dict]
    risks: list[str]
    score: int  # 1-10
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class DisneyReport:
    """Полный отчёт по стратегии Диснея"""
    project_name: str
    dreamer: DreamerOutput
    realist: RealistOutput
    critic: CriticOutput
    average_score: float
    recommendation: str
    next_steps: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class DisneyStrategy:
    """
    Реализация стратегии Уолта Диснея для проектов Montana

    Три комнаты:
    1. Комната Мечтателя — без ограничений, чистое видение
    2. Комната Реалиста — конкретный план
    3. Комната Критика — слабости и улучшения
    """

    def __init__(self, project_path: Optional[str] = None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.reports_dir = self.project_path / "disney_reports"
        self.reports_dir.mkdir(exist_ok=True)

    def dreamer(self, vision: str) -> DreamerOutput:
        """
        МЕЧТАТЕЛЬ — генерирует идеальное видение

        Правила:
        - Никаких ограничений
        - Что возможно в идеальном мире?
        - Какие инновации?
        - "А что если..."
        """
        print("\n🌟 МЕЧТАТЕЛЬ входит в комнату...")
        print(f"   Видение: {vision}\n")

        # Анализ проекта для определения возможностей
        innovations = self._find_innovations()
        possibilities = self._explore_possibilities(vision)
        ideal_outcome = self._define_ideal_outcome(vision)

        # Оценка потенциала
        score = min(10, len(innovations) + len(possibilities))

        return DreamerOutput(
            vision=vision,
            ideal_outcome=ideal_outcome,
            innovations=innovations,
            possibilities=possibilities,
            score=score
        )

    def realist(self, dream: DreamerOutput) -> RealistOutput:
        """
        РЕАЛИСТ — создаёт план реализации

        Правила:
        - Конкретные шаги
        - Что уже работает?
        - Что нужно сделать?
        - Какие ресурсы?
        """
        print("\n⚙️ РЕАЛИСТ входит в комнату...")
        print(f"   Анализирую видение: {dream.vision}\n")

        # Анализ текущего состояния
        working = self._find_working_parts()
        missing = self._find_missing_parts(dream)
        resources = self._calculate_resources(missing)
        timeline = self._create_timeline(missing)

        # Оценка реализуемости
        working_count = len(working)
        missing_count = len(missing)
        score = max(1, min(10, int(10 * working_count / (working_count + missing_count + 1))))

        return RealistOutput(
            working=working,
            missing=missing,
            resources_needed=resources,
            timeline_steps=timeline,
            score=score
        )

    def critic(self, plan: RealistOutput) -> CriticOutput:
        """
        КРИТИК — находит слабости и улучшения

        Правила:
        - Что может пойти не так?
        - Какие риски?
        - Что улучшить?
        """
        print("\n🔍 КРИТИК входит в комнату...")
        print(f"   Анализирую план: {len(plan.working)} работает, {len(plan.missing)} отсутствует\n")

        # Классификация проблем
        critical = self._find_critical_issues(plan)
        important = self._find_important_issues(plan)
        minor = self._find_minor_issues(plan)
        risks = self._assess_risks(plan)

        # Оценка качества
        total_issues = len(critical) + len(important) + len(minor)
        score = max(1, 10 - len(critical) * 2 - len(important))

        return CriticOutput(
            critical_issues=critical,
            important_issues=important,
            minor_issues=minor,
            risks=risks,
            score=score
        )

    def iterate(self, vision: str, project_name: str = "Montana Project") -> DisneyReport:
        """
        Полная итерация через все три роли

        Dreamer → Realist → Critic → Report
        """
        print(f"\n{'='*60}")
        print(f"  🎬 СТРАТЕГИЯ УОЛТА ДИСНЕЯ")
        print(f"  Проект: {project_name}")
        print(f"{'='*60}")

        # Три роли
        dream = self.dreamer(vision)
        plan = self.realist(dream)
        critique = self.critic(plan)

        # Средняя оценка
        avg_score = (dream.score + plan.score + critique.score) / 3

        # Рекомендация
        recommendation = self._generate_recommendation(avg_score, critique)
        next_steps = self._generate_next_steps(critique)

        report = DisneyReport(
            project_name=project_name,
            dreamer=dream,
            realist=plan,
            critic=critique,
            average_score=round(avg_score, 1),
            recommendation=recommendation,
            next_steps=next_steps
        )

        # Сохранить отчёт
        self._save_report(report)

        # Вывести отчёт
        self._print_report(report)

        return report

    # === Вспомогательные методы ===

    def _find_innovations(self) -> list[str]:
        """Найти инновации в проекте"""
        innovations = []

        # Проверяем наличие ключевых файлов
        if (self.project_path / "generate_audiobook.py").exists():
            innovations.append("AI-генерация аудиокниги с множеством персонажей")

        if (self.project_path / "animate_video.py").exists():
            innovations.append("Автоматическая синхронизация видео с музыкой")

        if (self.project_path / "walt_disney_strategy.py").exists():
            innovations.append("Встроенная стратегия Диснея для самоанализа")

        # Проверяем структуру
        if list(self.project_path.glob("*.md")):
            innovations.append("Полная документация в Markdown")

        return innovations if innovations else ["Потенциал для инноваций"]

    def _explore_possibilities(self, vision: str) -> list[str]:
        """Исследовать возможности"""
        possibilities = [
            "Мультиязычность (RU/EN/ZH)",
            "Real-time генерация на 5 узлах Montana",
            "Интеграция с Telegram ботом Юнона",
            "NFT-якоря для каждой серии",
            "Collaborative storytelling с AI"
        ]
        return possibilities

    def _define_ideal_outcome(self, vision: str) -> str:
        """Определить идеальный результат"""
        return f"Полностью автоматизированный pipeline: сырые мысли → готовое видео за 1 команду"

    def _find_working_parts(self) -> list[str]:
        """Найти что работает"""
        working = []

        # Проверяем файлы
        checks = [
            ("generate_audiobook.py", "Генерация аудиокниги"),
            ("СЦЕНАРИЙ_5MIN.md", "Сценарий 1 серии"),
            ("ФИНАЛЬНЫЙ_КАСТИНГ.md", "Кастинг голосов"),
            ("ПОТОК_МЫСЛЕЙ.md", "Внутренний монолог"),
        ]

        for filename, description in checks:
            if list(self.project_path.rglob(filename)):
                working.append(f"✓ {description}")

        # Проверяем папки
        if list(self.project_path.rglob("*.mp3")):
            working.append("✓ Аудио фрагменты сгенерированы")

        return working if working else ["Проект в начальной стадии"]

    def _find_missing_parts(self, dream: DreamerOutput) -> list[str]:
        """Найти что отсутствует"""
        missing = []

        # Проверяем критичные компоненты
        checks = [
            ("episode1_full.mp3", "Склеенная аудиокнига"),
            ("episode1.mp4", "Готовое видео"),
            ("soundtrack.mp3", "Музыкальная подложка"),
        ]

        for filename, description in checks:
            if not list(self.project_path.rglob(filename)):
                missing.append(f"❌ {description}")

        return missing if missing else ["Всё на месте!"]

    def _calculate_resources(self, missing: list[str]) -> list[str]:
        """Рассчитать необходимые ресурсы"""
        resources = []

        if any("аудио" in m.lower() for m in missing):
            resources.append("ElevenLabs API ($5-22/месяц)")

        if any("видео" in m.lower() for m in missing):
            resources.append("moviepy + librosa (бесплатно)")

        if any("музык" in m.lower() for m in missing):
            resources.append("Royalty-free музыка или AI генерация")

        return resources if resources else ["Ресурсы достаточны"]

    def _create_timeline(self, missing: list[str]) -> list[str]:
        """Создать timeline"""
        timeline = []

        for i, item in enumerate(missing, 1):
            timeline.append(f"Шаг {i}: {item.replace('❌ ', '')}")

        return timeline if timeline else ["Готово к запуску"]

    def _find_critical_issues(self, plan: RealistOutput) -> list[dict]:
        """Найти критические проблемы"""
        critical = []

        for missing in plan.missing:
            if "видео" in missing.lower():
                critical.append({
                    "problem": "Видео отсутствует",
                    "solution": "Запустить animate_video.py",
                    "priority": "КРИТИЧЕСКИЙ"
                })

        return critical

    def _find_important_issues(self, plan: RealistOutput) -> list[dict]:
        """Найти важные проблемы"""
        important = []

        for missing in plan.missing:
            if "музык" in missing.lower():
                important.append({
                    "problem": "Музыка не интегрирована",
                    "solution": "Добавить background music в pipeline",
                    "priority": "ВАЖНЫЙ"
                })

        return important

    def _find_minor_issues(self, plan: RealistOutput) -> list[dict]:
        """Найти второстепенные проблемы"""
        return [
            {
                "problem": "Нет автотестов",
                "solution": "Написать test_blagayavest.py",
                "priority": "ВТОРОСТЕПЕННЫЙ"
            }
        ]

    def _assess_risks(self, plan: RealistOutput) -> list[str]:
        """Оценить риски"""
        risks = [
            "API rate limits при массовой генерации",
            "Качество английских голосов для русского текста",
            "Стоимость при масштабировании"
        ]
        return risks

    def _generate_recommendation(self, score: float, critique: CriticOutput) -> str:
        """Сгенерировать рекомендацию"""
        if score >= 8:
            return "🟢 PRODUCTION READY — можно публиковать"
        elif score >= 6:
            return "🟡 MVP READY — нужны небольшие доработки"
        elif score >= 4:
            return "🟠 IN PROGRESS — требуется значительная работа"
        else:
            return "🔴 EARLY STAGE — на начальном этапе"

    def _generate_next_steps(self, critique: CriticOutput) -> list[str]:
        """Сгенерировать следующие шаги"""
        steps = []

        for issue in critique.critical_issues:
            steps.append(f"🔴 {issue['solution']}")

        for issue in critique.important_issues:
            steps.append(f"🟡 {issue['solution']}")

        return steps if steps else ["✅ Всё готово!"]

    def _save_report(self, report: DisneyReport):
        """Сохранить отчёт в JSON"""
        report_file = self.reports_dir / f"disney_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Конвертируем в dict
        report_dict = {
            "project_name": report.project_name,
            "timestamp": report.timestamp,
            "average_score": report.average_score,
            "recommendation": report.recommendation,
            "next_steps": report.next_steps,
            "dreamer": {
                "vision": report.dreamer.vision,
                "ideal_outcome": report.dreamer.ideal_outcome,
                "innovations": report.dreamer.innovations,
                "possibilities": report.dreamer.possibilities,
                "score": report.dreamer.score
            },
            "realist": {
                "working": report.realist.working,
                "missing": report.realist.missing,
                "resources_needed": report.realist.resources_needed,
                "timeline_steps": report.realist.timeline_steps,
                "score": report.realist.score
            },
            "critic": {
                "critical_issues": report.critic.critical_issues,
                "important_issues": report.critic.important_issues,
                "minor_issues": report.critic.minor_issues,
                "risks": report.critic.risks,
                "score": report.critic.score
            }
        }

        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)

        print(f"\n📄 Отчёт сохранён: {report_file}")

    def _print_report(self, report: DisneyReport):
        """Вывести отчёт в консоль"""
        print(f"\n{'='*60}")
        print(f"  📊 ИТОГОВЫЙ ОТЧЁТ")
        print(f"{'='*60}")

        print(f"\n🌟 МЕЧТАТЕЛЬ: {report.dreamer.score}/10")
        print(f"   Видение: {report.dreamer.vision}")
        print(f"   Идеальный результат: {report.dreamer.ideal_outcome}")

        print(f"\n⚙️ РЕАЛИСТ: {report.realist.score}/10")
        print(f"   Работает: {len([w for w in report.realist.working if '✓' in w])}")
        print(f"   Отсутствует: {len([m for m in report.realist.missing if '❌' in m])}")

        print(f"\n🔍 КРИТИК: {report.critic.score}/10")
        print(f"   Критичных: {len(report.critic.critical_issues)}")
        print(f"   Важных: {len(report.critic.important_issues)}")

        print(f"\n{'─'*60}")
        print(f"  СРЕДНЯЯ ОЦЕНКА: {report.average_score}/10")
        print(f"  {report.recommendation}")
        print(f"{'─'*60}")

        print(f"\n📋 СЛЕДУЮЩИЕ ШАГИ:")
        for step in report.next_steps:
            print(f"   {step}")

        print(f"\n{'='*60}")
        print(f"  金元Ɉ Montana | {report.timestamp}")
        print(f"{'='*60}\n")


def main():
    """CLI интерфейс"""
    parser = argparse.ArgumentParser(
        description="Walt Disney Strategy для Montana",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python walt_disney_strategy.py --vision "Создать аудиокнигу"
  python walt_disney_strategy.py --analyze ./Благаявесть
  python walt_disney_strategy.py --report
        """
    )

    parser.add_argument(
        '--vision', '-v',
        type=str,
        default="Создать первую серию Благаявести",
        help='Видение/цель проекта'
    )

    parser.add_argument(
        '--analyze', '-a',
        type=str,
        default=None,
        help='Путь к проекту для анализа'
    )

    parser.add_argument(
        '--name', '-n',
        type=str,
        default="Благаявесть",
        help='Название проекта'
    )

    parser.add_argument(
        '--report', '-r',
        action='store_true',
        help='Показать последний отчёт'
    )

    args = parser.parse_args()

    # Определяем путь
    project_path = args.analyze if args.analyze else str(Path(__file__).parent)

    # Создаём стратегию
    strategy = DisneyStrategy(project_path)

    # Запускаем итерацию
    report = strategy.iterate(
        vision=args.vision,
        project_name=args.name
    )

    return report


if __name__ == "__main__":
    main()
