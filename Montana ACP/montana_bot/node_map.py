#!/usr/bin/env python3
"""
Montana Node Map — География Full Nodes
========================================

ЗАКОН: Один ключ, одна подпись, один раз.

Карта показывает все страны с активными Full Nodes сети Montana.
Москва — первый Full Node (Genesis).

Использование:
    from node_map import NodeMap, generate_map_image

    node_map = NodeMap()
    node_map.add_node("176.124.208.93", "Moscow Genesis")
    image_bytes = node_map.render()
"""

import io
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

# Для генерации изображения карты
try:
    import matplotlib
    matplotlib.use('Agg')  # Без GUI
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.colors import LinearSegmentedColormap
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    import geopandas as gpd
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False

# Координаты столиц для отображения на карте
COUNTRY_COORDS = {
    "RU": (55.7558, 37.6173, "Россия", "Moscow"),
    "US": (38.9072, -77.0369, "США", "Washington"),
    "DE": (52.5200, 13.4050, "Германия", "Berlin"),
    "GB": (51.5074, -0.1278, "Великобритания", "London"),
    "FR": (48.8566, 2.3522, "Франция", "Paris"),
    "JP": (35.6762, 139.6503, "Япония", "Tokyo"),
    "CN": (39.9042, 116.4074, "Китай", "Beijing"),
    "AU": (-35.2809, 149.1300, "Австралия", "Canberra"),
    "BR": (-15.7975, -47.8919, "Бразилия", "Brasilia"),
    "IN": (28.6139, 77.2090, "Индия", "New Delhi"),
    "CA": (45.4215, -75.6972, "Канада", "Ottawa"),
    "KR": (37.5665, 126.9780, "Южная Корея", "Seoul"),
    "SG": (1.3521, 103.8198, "Сингапур", "Singapore"),
    "NL": (52.3676, 4.9041, "Нидерланды", "Amsterdam"),
    "CH": (46.9480, 7.4474, "Швейцария", "Bern"),
    "SE": (59.3293, 18.0686, "Швеция", "Stockholm"),
    "NO": (59.9139, 10.7522, "Норвегия", "Oslo"),
    "FI": (60.1699, 24.9384, "Финляндия", "Helsinki"),
    "PL": (52.2297, 21.0122, "Польша", "Warsaw"),
    "UA": (50.4501, 30.5234, "Украина", "Kyiv"),
    "KZ": (51.1605, 71.4704, "Казахстан", "Astana"),
    "AE": (24.4539, 54.3773, "ОАЭ", "Abu Dhabi"),
    "IL": (31.7683, 35.2137, "Израиль", "Jerusalem"),
    "ZA": (-25.7479, 28.2293, "ЮАР", "Pretoria"),
    "AR": (-34.6037, -58.3816, "Аргентина", "Buenos Aires"),
    "MX": (19.4326, -99.1332, "Мексика", "Mexico City"),
    "TH": (13.7563, 100.5018, "Таиланд", "Bangkok"),
    "VN": (21.0285, 105.8542, "Вьетнам", "Hanoi"),
    "ID": (-6.2088, 106.8456, "Индонезия", "Jakarta"),
    "MY": (3.1390, 101.6869, "Малайзия", "Kuala Lumpur"),
    "PH": (14.5995, 120.9842, "Филиппины", "Manila"),
    "NZ": (-41.2865, 174.7762, "Новая Зеландия", "Wellington"),
    "IE": (53.3498, -6.2603, "Ирландия", "Dublin"),
    "PT": (38.7223, -9.1393, "Португалия", "Lisbon"),
    "ES": (40.4168, -3.7038, "Испания", "Madrid"),
    "IT": (41.9028, 12.4964, "Италия", "Rome"),
    "AT": (48.2082, 16.3738, "Австрия", "Vienna"),
    "CZ": (50.0755, 14.4378, "Чехия", "Prague"),
    "HU": (47.4979, 19.0402, "Венгрия", "Budapest"),
    "RO": (44.4268, 26.1025, "Румыния", "Bucharest"),
    "BG": (42.6977, 23.3219, "Болгария", "Sofia"),
    "GR": (37.9838, 23.7275, "Греция", "Athens"),
    "TR": (39.9334, 32.8597, "Турция", "Ankara"),
    "EG": (30.0444, 31.2357, "Египет", "Cairo"),
    "NG": (9.0765, 7.3986, "Нигерия", "Abuja"),
    "KE": (-1.2921, 36.8219, "Кения", "Nairobi"),
    "CL": (-33.4489, -70.6693, "Чили", "Santiago"),
    "CO": (4.7110, -74.0721, "Колумбия", "Bogota"),
    "PE": (-12.0464, -77.0428, "Перу", "Lima"),
}

# IP ranges по странам (упрощённая база)
IP_COUNTRY_RANGES = {
    # Timeweb (Россия)
    "176.124.": "RU",
    "185.221.": "RU",
    "77.222.": "RU",
    "92.53.": "RU",
    # Hetzner (Германия)
    "95.217.": "DE",
    "135.181.": "DE",
    "65.109.": "DE",
    # DigitalOcean (США)
    "167.99.": "US",
    "138.197.": "US",
    "159.65.": "US",
    # AWS regions
    "3.": "US",
    "52.": "US",
    "54.": "US",
    # Localhost
    "127.": "LOCAL",
    "192.168.": "LOCAL",
    "10.": "LOCAL",
}


@dataclass
class FullNode:
    """Информация о Full Node."""
    ip: str
    name: str
    country_code: str
    city: Optional[str] = None
    genesis_time: Optional[datetime] = None
    is_genesis: bool = False
    noise_pk: Optional[str] = None


@dataclass
class NodeMap:
    """Карта узлов Montana."""

    nodes: Dict[str, FullNode] = field(default_factory=dict)
    data_file: Optional[Path] = None

    def __post_init__(self):
        if self.data_file is None:
            self.data_file = Path(__file__).parent / "data" / "nodes.json"
        self._load()

    def _load(self):
        """Загрузить узлы из файла."""
        if self.data_file and self.data_file.exists():
            try:
                data = json.loads(self.data_file.read_text())
                for ip, info in data.get("nodes", {}).items():
                    self.nodes[ip] = FullNode(
                        ip=ip,
                        name=info.get("name", "Unknown"),
                        country_code=info.get("country", "??"),
                        city=info.get("city"),
                        genesis_time=datetime.fromisoformat(info["genesis_time"]) if info.get("genesis_time") else None,
                        is_genesis=info.get("is_genesis", False),
                        noise_pk=info.get("noise_pk")
                    )
            except Exception:
                pass

    def _save(self):
        """Сохранить узлы в файл."""
        if self.data_file:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "nodes": {
                    ip: {
                        "name": node.name,
                        "country": node.country_code,
                        "city": node.city,
                        "genesis_time": node.genesis_time.isoformat() if node.genesis_time else None,
                        "is_genesis": node.is_genesis,
                        "noise_pk": node.noise_pk
                    }
                    for ip, node in self.nodes.items()
                },
                "updated": datetime.now(timezone.utc).isoformat()
            }
            self.data_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def detect_country(self, ip: str) -> str:
        """Определить страну по IP (упрощённо)."""
        for prefix, country in IP_COUNTRY_RANGES.items():
            if ip.startswith(prefix):
                return country
        return "??"

    def add_node(self, ip: str, name: str, country_code: Optional[str] = None,
                 is_genesis: bool = False, noise_pk: Optional[str] = None) -> FullNode:
        """Добавить узел."""
        if country_code is None:
            country_code = self.detect_country(ip)

        city = None
        if country_code in COUNTRY_COORDS:
            city = COUNTRY_COORDS[country_code][3]

        node = FullNode(
            ip=ip,
            name=name,
            country_code=country_code,
            city=city,
            genesis_time=datetime.now(timezone.utc),
            is_genesis=is_genesis,
            noise_pk=noise_pk
        )
        self.nodes[ip] = node
        self._save()
        return node

    def remove_node(self, ip: str) -> bool:
        """Удалить узел."""
        if ip in self.nodes:
            del self.nodes[ip]
            self._save()
            return True
        return False

    def get_countries(self) -> Dict[str, List[FullNode]]:
        """Получить узлы по странам."""
        countries: Dict[str, List[FullNode]] = {}
        for node in self.nodes.values():
            if node.country_code not in countries:
                countries[node.country_code] = []
            countries[node.country_code].append(node)
        return countries

    def render_text(self) -> str:
        """Текстовое представление карты."""
        countries = self.get_countries()

        if not countries:
            return "🗺 Карта Montana пуста\n\nДобавьте первый Full Node."

        lines = [
            "🗺 MONTANA FULL NODES",
            "═" * 40,
            ""
        ]

        # Сортируем: сначала Genesis, потом по количеству узлов
        sorted_countries = sorted(
            countries.items(),
            key=lambda x: (-any(n.is_genesis for n in x[1]), -len(x[1]), x[0])
        )

        total_nodes = 0
        for country_code, nodes in sorted_countries:
            total_nodes += len(nodes)

            # Получаем название страны
            if country_code in COUNTRY_COORDS:
                country_name = COUNTRY_COORDS[country_code][2]
            elif country_code == "LOCAL":
                country_name = "Локальный"
            else:
                country_name = country_code

            # Флаг (эмодзи)
            flag = self._country_flag(country_code)

            # Genesis маркер
            has_genesis = any(n.is_genesis for n in nodes)
            genesis_mark = " ⭐ GENESIS" if has_genesis else ""

            lines.append(f"{flag} {country_name}: {len(nodes)} узел(ов){genesis_mark}")

            for node in nodes:
                prefix = "   └─ " if node == nodes[-1] else "   ├─ "
                genesis = "🌟 " if node.is_genesis else ""
                lines.append(f"{prefix}{genesis}{node.name}")
                if node.noise_pk:
                    lines.append(f"      PK: {node.noise_pk[:16]}...")

        lines.extend([
            "",
            "─" * 40,
            f"Всего: {total_nodes} узлов в {len(countries)} странах",
            "",
            "ЗАКОН: Один ключ, одна подпись, один раз."
        ])

        return "\n".join(lines)

    def _country_flag(self, code: str) -> str:
        """Эмодзи флаг страны."""
        if code == "LOCAL" or code == "??" or len(code) != 2:
            return "🏴"
        # Unicode regional indicator symbols
        return chr(ord('🇦') + ord(code[0]) - ord('A')) + chr(ord('🇦') + ord(code[1]) - ord('A'))

    def render_ascii_map(self) -> str:
        """ASCII карта мира с узлами."""
        countries = set(self.get_countries().keys())

        # Упрощённая ASCII карта
        map_template = """
    ┌──────────────────────────────────────────────────────────────┐
    │                    MONTANA WORLD MAP                          │
    │                                                               │
    │         ▄▄▄▄▄                                                 │
    │     ▄▄▄█{CA}███▄       {NO}{SE}{FI}                           │
    │   ▄█{US}██████▀    {GB}{NL}{DE}{PL}{RU}████████▄               │
    │   ▀███████▀       {FR}{CH}{AT}{CZ}{UA}{KZ}██████▀              │
    │        ▀▀▀▀       {ES}{IT}{HU}{RO}{TR}████▀                    │
    │      {MX}▄         {PT}  {GR}{BG}  {IL}{AE}  {IN}{TH}{VN}{CN}█▄{JP}{KR} │
    │     ▀██▀{CO}               {EG}    {PH}██████▀                 │
    │       ▀█{PE}  {BR}▄▄▄        {NG}  {ID}█▀  {MY}{SG}             │
    │        ▀{CL}██{AR}█▀        {KE}                               │
    │         ▀▀▀▀▀           {ZA}                                   │
    │                                 {AU}▄▄▄▄                       │
    │                                  ▀███▀ {NZ}                    │
    │                                                               │
    └──────────────────────────────────────────────────────────────┘
"""
        # Заменяем коды стран на символы
        for code in COUNTRY_COORDS.keys():
            if code in countries:
                map_template = map_template.replace("{" + code + "}", "●")
            else:
                map_template = map_template.replace("{" + code + "}", " ")

        # Удаляем оставшиеся placeholder'ы
        import re
        map_template = re.sub(r'\{[A-Z]{2}\}', ' ', map_template)

        return map_template

    def render_image(self, width: int = 1200, height: int = 600) -> Optional[bytes]:
        """
        Генерирует PNG изображение карты мира с закрашенными странами.
        Страны с Full Nodes закрашены золотым цветом.
        Genesis страна — особым цветом.

        Returns:
            bytes PNG изображения или None если библиотеки недоступны
        """
        if not HAS_MATPLOTLIB or not HAS_GEOPANDAS:
            return None

        countries_with_nodes = self.get_countries()
        active_countries = set(countries_with_nodes.keys())

        # Находим Genesis страну
        genesis_country = None
        for code, nodes in countries_with_nodes.items():
            if any(n.is_genesis for n in nodes):
                genesis_country = code
                break

        # Загружаем Natural Earth данные (встроено в geopandas)
        try:
            world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        except Exception:
            # Fallback: пытаемся скачать
            try:
                world = gpd.read_file(
                    "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
                )
            except Exception:
                return None

        # Маппинг ISO_A2 кодов
        # Natural Earth использует iso_a2 или ISO_A2
        iso_col = 'iso_a2' if 'iso_a2' in world.columns else 'ISO_A2'

        # Создаём колонку для цвета
        def get_color(iso_code):
            if iso_code == genesis_country:
                return 'genesis'
            elif iso_code in active_countries:
                return 'active'
            else:
                return 'inactive'

        world['node_status'] = world[iso_col].apply(get_color)

        # Настройка цветов
        color_map = {
            'inactive': '#2C2C2C',      # Тёмно-серый
            'active': '#D4AF37',         # Золотой
            'genesis': '#FFD700'         # Яркое золото для Genesis
        }

        # Создаём фигуру
        fig, ax = plt.subplots(1, 1, figsize=(width/100, height/100), dpi=100)
        fig.patch.set_facecolor('#1A1A1A')  # Тёмный фон
        ax.set_facecolor('#1A1A1A')

        # Рисуем страны
        for status, color in color_map.items():
            subset = world[world['node_status'] == status]
            if not subset.empty:
                subset.plot(
                    ax=ax,
                    color=color,
                    edgecolor='#3A3A3A',
                    linewidth=0.3
                )

        # Добавляем точки для узлов
        for code, nodes in countries_with_nodes.items():
            if code in COUNTRY_COORDS:
                lat, lon = COUNTRY_COORDS[code][0], COUNTRY_COORDS[code][1]
                is_genesis = any(n.is_genesis for n in nodes)

                # Точка
                marker_size = 150 if is_genesis else 80
                marker_color = '#FF4500' if is_genesis else '#FFFFFF'
                ax.scatter(
                    lon, lat,
                    s=marker_size,
                    c=marker_color,
                    marker='o',
                    edgecolors='white',
                    linewidth=1,
                    zorder=5
                )

                # Подпись для Genesis
                if is_genesis:
                    ax.annotate(
                        'GENESIS',
                        xy=(lon, lat),
                        xytext=(lon + 5, lat + 5),
                        fontsize=8,
                        color='#FFD700',
                        fontweight='bold',
                        zorder=6
                    )

        # Заголовок
        ax.set_title(
            'MONTANA FULL NODES',
            fontsize=16,
            color='#D4AF37',
            fontweight='bold',
            pad=10
        )

        # Статистика
        total_nodes = sum(len(nodes) for nodes in countries_with_nodes.values())
        stats_text = f"{total_nodes} узлов в {len(active_countries)} странах"
        ax.text(
            0.5, 0.02,
            stats_text,
            transform=ax.transAxes,
            fontsize=10,
            color='#888888',
            ha='center'
        )

        # Закон
        ax.text(
            0.99, 0.02,
            "ОДИН КЛЮЧ. ОДНА ПОДПИСЬ. ОДИН РАЗ.",
            transform=ax.transAxes,
            fontsize=7,
            color='#555555',
            ha='right'
        )

        # Легенда
        legend_elements = [
            mpatches.Patch(facecolor='#FFD700', edgecolor='white', label='Genesis'),
            mpatches.Patch(facecolor='#D4AF37', edgecolor='white', label='Full Node'),
            mpatches.Patch(facecolor='#2C2C2C', edgecolor='#3A3A3A', label='Нет узлов'),
        ]
        ax.legend(
            handles=legend_elements,
            loc='lower left',
            frameon=False,
            fontsize=8,
            labelcolor='#888888'
        )

        # Убираем оси
        ax.set_axis_off()
        ax.set_xlim(-180, 180)
        ax.set_ylim(-60, 85)

        # Сохраняем в байты
        buf = io.BytesIO()
        plt.savefig(
            buf,
            format='png',
            bbox_inches='tight',
            facecolor=fig.get_facecolor(),
            edgecolor='none',
            dpi=100
        )
        plt.close(fig)
        buf.seek(0)

        return buf.read()

    def get_stats(self) -> Dict:
        """Получить статистику узлов."""
        countries = self.get_countries()
        total_nodes = sum(len(nodes) for nodes in countries.values())

        genesis_node = None
        for nodes in countries.values():
            for node in nodes:
                if node.is_genesis:
                    genesis_node = node
                    break

        return {
            "total_nodes": total_nodes,
            "total_countries": len(countries),
            "countries": list(countries.keys()),
            "genesis_node": genesis_node.name if genesis_node else None,
            "genesis_country": genesis_node.country_code if genesis_node else None,
        }


def init_genesis_node() -> NodeMap:
    """Инициализировать карту с Genesis узлом (Москва)."""
    node_map = NodeMap()

    # Добавить Moscow Genesis если ещё нет
    if "176.124.208.93" not in node_map.nodes:
        node_map.add_node(
            ip="176.124.208.93",
            name="Moscow Genesis",
            country_code="RU",
            is_genesis=True,
            noise_pk="76737016f270e6a5"
        )

    return node_map


# Глобальный экземпляр
_node_map: Optional[NodeMap] = None

def get_node_map() -> NodeMap:
    """Получить глобальную карту узлов."""
    global _node_map
    if _node_map is None:
        _node_map = init_genesis_node()
    return _node_map


if __name__ == "__main__":
    # Демонстрация
    node_map = init_genesis_node()

    print(node_map.render_text())
    print()
    print(node_map.render_ascii_map())
