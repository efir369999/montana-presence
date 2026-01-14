"""
Montana Presence Verification Module
=====================================

╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   ЗАКОН: ОДИН КЛЮЧ. ОДНА ПОДПИСЬ. ОДИН РАЗ.                     ║
║                                                                  ║
║   Это касается ВСЕХ без исключения.                              ║
║   Когнитивная цепочка уникальных подписей начинается с Genesis. ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝

Verified User (20%) — Genesis Identity через Telegram бота.

Каждый пользователь создаёт ОДИН genesis identity.
Это начало его когнитивной цепочки подписей.
Все последующие подписи привязаны к этому Genesis.

Механика:
1. Пользователь регистрируется → создаётся Genesis (ОДИН РАЗ НАВСЕГДА)
2. Случайные "Ты здесь?" (10-40 мин) → 30 сек на ответ
3. Каждый ответ → подпись в когнитивной цепочке

Когнитивная цепочка:
    Genesis → Подпись_1 → Подпись_2 → ... → Подпись_N

    Каждая подпись содержит хеш предыдущей.
    Невозможно подделать или вставить подпись в середину.

Формула:
    identity(user) = genesis(bot) + signature_chain(presences) + verification(Montana)
"""

import hashlib
import json
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
import asyncio
import subprocess
import os


# ============================================================================
# CONSTANTS (синхронизированы с consensus.rs)
# ============================================================================

TAU2_SECS = 600                    # 10 минут — минимальный интервал
VERIFIED_USER_MAX_INTERVAL = 2400  # 40 минут — максимальный интервал
VERIFICATION_WINDOW_SECS = 30      # 30 секунд на ответ
TAU3_MIN_DAYS = 14                 # 14 дней для τ₃ eligibility
TAU3_SUCCESS_RATE = 0.90           # 90% успешных ответов для бонуса


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class CognitiveKey:
    """Когнитивный ключ пользователя — генезис identity."""
    user_id: int
    telegram_username: Optional[str]
    marker: str                     # Когнитивный маркер (#...)
    cognitive_prompt: str           # Когнитивный промпт (философия/аффирмация)
    genesis_timestamp: int          # Unix timestamp создания
    genesis_hash: str               # SHA3-256 genesis block
    public_key: str                 # Публичный ключ (hex)
    genesis_signature: str = ""     # Криптографическая подпись genesis (hex)
    signature_scheme: str = "mldsa65/dilithium3"
    secret_key: str = ""            # Секретный ключ (hex). ВНИМАНИЕ: хранить безопасно.
    lamer_id: int = 0               # Порядковый номер (1, 2, 3...) по genesis_timestamp

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'CognitiveKey':
        # Поддержка старых ключей
        if 'cognitive_prompt' not in data:
            data['cognitive_prompt'] = ""
        if 'genesis_signature' not in data:
            data['genesis_signature'] = ""
        if 'signature_scheme' not in data:
            data['signature_scheme'] = "mldsa65/dilithium3"
        if 'secret_key' not in data:
            data['secret_key'] = ""
        if 'lamer_id' not in data:
            data['lamer_id'] = 0
        return cls(**data)


@dataclass
class PresenceChallenge:
    """Активный challenge "Ты здесь?"."""
    user_id: int
    challenge_id: str
    created_at: int                 # Unix timestamp
    expires_at: int                 # Unix timestamp (created_at + 30)
    tau2_index: int                 # Текущий τ₂ период
    answered: bool = False
    answer_timestamp: Optional[int] = None


@dataclass
class SpatialAnchor:
    """
    Пространственный якорь для presence proof.

    Философия: "Локация и время — это пространственный якорь
    финализации цепочки памяти"
    """
    anchor_type: str           # "text" | "location" | "file" | "photo" | "video" | "voice" | "composite"
    timestamp: int

    # Text
    text: Optional[str] = None

    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # File/Media
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None

    # Composite anchor signature
    composite_hash: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "anchor_type": self.anchor_type,
            "timestamp": self.timestamp,
            "text": self.text,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "file_id": self.file_id,
            "file_name": self.file_name,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "composite_hash": self.composite_hash,
        }

    @staticmethod
    def from_dict(data: dict) -> 'SpatialAnchor':
        return SpatialAnchor(**data)


@dataclass
class PresenceRecord:
    """Запись успешного присутствия."""
    user_id: int
    tau2_index: int
    timestamp: int
    challenge_id: str
    response_hash: str

    # Spatial anchors
    spatial_anchor: Optional[SpatialAnchor] = None
    anchor_signature: Optional[str] = None

    def to_dict(self) -> dict:
        result = {
            "user_id": self.user_id,
            "tau2_index": self.tau2_index,
            "timestamp": self.timestamp,
            "challenge_id": self.challenge_id,
            "response_hash": self.response_hash,
        }
        if self.spatial_anchor:
            result["spatial_anchor"] = self.spatial_anchor.to_dict()
            result["anchor_signature"] = self.anchor_signature
        return result

    @staticmethod
    def from_dict(data: dict) -> 'PresenceRecord':
        spatial = None
        if "spatial_anchor" in data:
            spatial = SpatialAnchor.from_dict(data["spatial_anchor"])

        return PresenceRecord(
            user_id=data["user_id"],
            tau2_index=data["tau2_index"],
            timestamp=data["timestamp"],
            challenge_id=data["challenge_id"],
            response_hash=data["response_hash"],
            spatial_anchor=spatial,
            anchor_signature=data.get("anchor_signature"),
        )


@dataclass
class UserPresenceStats:
    """Статистика присутствия пользователя."""
    user_id: int
    total_challenges: int
    successful_responses: int
    missed_challenges: int
    current_streak: int
    longest_streak: int
    presence_weight: int
    tier: int                       # 1-4 (τ₁-τ₄)
    last_presence_tau2: int


# ============================================================================
# GENESIS & COGNITIVE KEY CREATION
# ============================================================================

def sha3_256(data: bytes) -> str:
    """SHA3-256 хеш в hex формате."""
    return hashlib.sha3_256(data).hexdigest()


def create_spatial_signature(marker: str, anchor: SpatialAnchor) -> str:
    """
    Создать криптографическую подпись пространственного якоря.

    Подпись включает:
    - Cognitive marker (#Благаявесть)
    - Timestamp (Unix)
    - Text (если есть)
    - Location (lat,lon если есть)
    - File hash (если есть)
    - File name (если есть)

    Returns: SHA3-256 hex string
    """
    components = [
        marker,
        str(anchor.timestamp),
    ]

    if anchor.text:
        components.append(anchor.text)

    if anchor.latitude is not None and anchor.longitude is not None:
        components.append(f"{anchor.latitude},{anchor.longitude}")

    if anchor.file_hash:
        components.append(anchor.file_hash)

    if anchor.file_name:
        components.append(anchor.file_name)

    data = ":".join(components).encode('utf-8')
    return hashlib.sha3_256(data).hexdigest()


def _montana_repo_root() -> Path:
    """
    Получить корень `Montana ACP/` из расположения файла.
    `.../Montana ACP/montana_bot/presence.py` -> `.../Montana ACP/`
    """
    return Path(__file__).resolve().parents[1]


def _genesis_sign_binary_candidates() -> List[Path]:
    """
    Возможные пути до бинарника `genesis_sign`.
    """
    root = _montana_repo_root()
    montana_dir = root / "montana"
    return [
        Path(os.environ["MONTANA_GENESIS_SIGN_BIN"]).expanduser()
        if "MONTANA_GENESIS_SIGN_BIN" in os.environ else Path("/nonexistent"),
        montana_dir / "target" / "release" / "genesis_sign",
        montana_dir / "target" / "debug" / "genesis_sign",
    ]


def mldsa_sign_genesis_payload(genesis_payload: bytes) -> Tuple[str, str, str]:
    """
    Подписать genesis payload (bytes) через Rust-бинарник `genesis_sign`.

    Returns:
        (pubkey_hex, signature_hex, secret_hex)
    """
    if not genesis_payload:
        raise ValueError("Пустой genesis payload — нечего подписывать")

    # Найти бинарник
    bin_path = None
    for candidate in _genesis_sign_binary_candidates():
        if candidate.exists() and candidate.is_file():
            bin_path = candidate
            break

    if bin_path is None:
        raise RuntimeError(
            "Не найден бинарник `genesis_sign`.\n"
            "Собери его один раз:\n"
            "  cd 'Montana ACP/montana' && cargo build --bin genesis_sign\n"
            "Или укажи путь переменной окружения MONTANA_GENESIS_SIGN_BIN."
        )

    proc = subprocess.run(
        [str(bin_path)],
        input=genesis_payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"`genesis_sign` завершился с ошибкой (code={proc.returncode}).\n"
            f"stderr:\n{proc.stderr.decode('utf-8', errors='replace')}"
        )

    out = proc.stdout.decode("utf-8", errors="replace").splitlines()
    kv = {}
    for line in out:
        if "=" in line:
            k, v = line.split("=", 1)
            kv[k.strip()] = v.strip()

    pubkey_hex = kv.get("pubkey_hex", "")
    signature_hex = kv.get("signature_hex", "")
    secret_hex = kv.get("secret_hex", "")

    if not pubkey_hex or not signature_hex:
        raise RuntimeError(
            "Некорректный вывод `genesis_sign`: отсутствует pubkey_hex/signature_hex."
        )

    return pubkey_hex, signature_hex, secret_hex


def generate_cognitive_key(
    user_id: int,
    telegram_username: Optional[str],
    marker: str,
    cognitive_prompt: str = "",
    first_response: str = ""
) -> CognitiveKey:
    """
    Создать когнитивный ключ (genesis identity) для пользователя.
    
    ПРАВИЛО: Один ключ, одна подпись, один раз.
    Каждый пользователь может создать только один genesis identity.
    Это касается всех без исключения.

    Args:
        user_id: Telegram user ID
        telegram_username: @username (опционально)
        marker: Когнитивный маркер (должен начинаться с #)
        cognitive_prompt: Когнитивный промпт (философия/аффирмация)
        first_response: Первый ответ на "Ты здесь?" (опционально)

    Returns:
        CognitiveKey с genesis hash
    """
    # Валидация маркера
    if not marker.startswith('#') or ' ' in marker or len(marker) < 2:
        raise ValueError("Маркер должен начинаться с # и не содержать пробелов")

    timestamp = int(time.time())

    # Genesis block data
    # ПРАВИЛО: Один ключ, одна подпись, один раз.
    # Каждый пользователь создаёт только один genesis identity.
    genesis_data = {
        "version": 2,
        "user_id": user_id,
        "username": telegram_username,
        "marker": marker,
        "cognitive_prompt": cognitive_prompt,
        "timestamp": timestamp,
        "first_response": first_response,
        "entropy": secrets.token_hex(32)  # Один раз — одна подпись
    }

    # Genesis hash (одна подпись генезиса)
    genesis_bytes = json.dumps(genesis_data, sort_keys=True).encode('utf-8')
    genesis_hash = sha3_256(genesis_bytes)

    # Криптографический ключ + подпись genesis (один раз)
    # ПРАВИЛО: один ключ, одна подпись, один раз.
    public_key, genesis_signature, secret_key = mldsa_sign_genesis_payload(genesis_bytes)

    return CognitiveKey(
        user_id=user_id,
        telegram_username=telegram_username,
        marker=marker,
        cognitive_prompt=cognitive_prompt,
        genesis_timestamp=timestamp,
        genesis_hash=genesis_hash,
        public_key=public_key,
        genesis_signature=genesis_signature,
        secret_key=secret_key,
    )


# ============================================================================
# CHALLENGE SYSTEM
# ============================================================================

def calculate_next_challenge_interval(
    prev_slice_hash: str,
    user_public_key: str,
    last_check_tau2: int
) -> int:
    """
    Рассчитать интервал до следующей проверки (1-40 минут).

    Формула:
        seed = SHA3-256(prev_slice_hash || device_pubkey || last_check_τ₂)
        interval = 1 + (seed mod 40) minutes

    Диапазон: от 1 мин (внутри первого τ2) до 40 мин (конец 4-го τ2).
    """
    seed_input = f"{prev_slice_hash}{user_public_key}{last_check_tau2}"
    seed = sha3_256(seed_input.encode())

    # Берём первые 8 байт как число
    seed_val = int(seed[:16], 16)

    # 1 + (seed mod 40) = 1 to 40 минут
    minutes = 1 + (seed_val % 40)

    return minutes * 60  # в секундах


def create_challenge(user_id: int, tau2_index: int) -> PresenceChallenge:
    """Создать новый challenge "Ты здесь?"."""
    now = int(time.time())
    challenge_id = sha3_256(f"{user_id}:{now}:{secrets.token_hex(16)}".encode())[:16]

    return PresenceChallenge(
        user_id=user_id,
        challenge_id=challenge_id,
        created_at=now,
        expires_at=now + VERIFICATION_WINDOW_SECS,
        tau2_index=tau2_index,
        answered=False,
        answer_timestamp=None
    )


def verify_challenge_response(
    challenge: PresenceChallenge,
    response_timestamp: int
) -> Tuple[bool, str]:
    """
    Проверить ответ на challenge.

    Returns:
        (success, message)
    """
    if challenge.answered:
        return False, "Challenge уже отвечен"

    if response_timestamp > challenge.expires_at:
        seconds_late = response_timestamp - challenge.expires_at
        return False, f"Опоздание на {seconds_late} сек. Окно 30 секунд."

    if response_timestamp < challenge.created_at:
        return False, "Ответ раньше challenge (аномалия времени)"

    response_time = response_timestamp - challenge.created_at
    return True, f"Ответ за {response_time} сек. Присутствие подтверждено."


# ============================================================================
# PRESENCE STORAGE
# ============================================================================

class PresenceStorage:
    """Хранилище когнитивных ключей и записей присутствия."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.keys_file = self.data_dir / "cognitive_keys.json"
        self.presence_file = self.data_dir / "presence_records.json"
        self.challenges_file = self.data_dir / "active_challenges.json"

        self._keys: Dict[int, CognitiveKey] = {}
        self._presence: Dict[int, List[PresenceRecord]] = {}
        self._challenges: Dict[int, PresenceChallenge] = {}

        self._load()

    def _load(self):
        """Загрузить данные из файлов."""
        if self.keys_file.exists():
            with open(self.keys_file, 'r') as f:
                data = json.load(f)
                self._keys = {
                    int(k): CognitiveKey.from_dict(v)
                    for k, v in data.items()
                }

        if self.presence_file.exists():
            with open(self.presence_file, 'r') as f:
                data = json.load(f)
                self._presence = {
                    int(k): [PresenceRecord(**r) for r in v]
                    for k, v in data.items()
                }

    def _recalculate_lamer_ids(self):
        """Пересчитать lamer_id для всех ключей по genesis_timestamp."""
        # Сортируем ключи по genesis_timestamp
        sorted_keys = sorted(self._keys.values(), key=lambda k: k.genesis_timestamp)

        # Присваиваем порядковые номера
        for idx, key in enumerate(sorted_keys, start=1):
            key.lamer_id = idx

    def _save_keys(self):
        """Сохранить когнитивные ключи."""
        # Пересчитываем lamer_id перед сохранением
        self._recalculate_lamer_ids()

        with open(self.keys_file, 'w') as f:
            data = {str(k): v.to_dict() for k, v in self._keys.items()}
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _save_presence(self):
        """Сохранить записи присутствия."""
        with open(self.presence_file, 'w') as f:
            data = {
                str(k): [asdict(r) for r in v]
                for k, v in self._presence.items()
            }
            json.dump(data, f, indent=2)

    # === Cognitive Keys ===

    def has_key(self, user_id: int) -> bool:
        """Проверить есть ли у пользователя когнитивный ключ."""
        return user_id in self._keys

    def get_key(self, user_id: int) -> Optional[CognitiveKey]:
        """Получить когнитивный ключ пользователя."""
        return self._keys.get(user_id)

    def create_key(
        self,
        user_id: int,
        telegram_username: Optional[str],
        marker: str,
        cognitive_prompt: str = "",
        first_response: str = ""
    ) -> CognitiveKey:
        """
        Создать и сохранить когнитивный ключ.
        
        ПРАВИЛО: Один ключ, одна подпись, один раз.
        Каждый пользователь может создать только один genesis identity.
        Это касается всех без исключения.
        """
        if self.has_key(user_id):
            existing_key = self.get_key(user_id)
            raise ValueError(
                f"ПРАВИЛО: Один ключ, одна подпись, один раз.\n"
                f"Пользователь {user_id} уже имеет когнитивный ключ.\n"
                f"Genesis Hash: {existing_key.genesis_hash[:32]}...\n"
                f"Маркер: {existing_key.marker}\n"
                f"Создан: {datetime.fromtimestamp(existing_key.genesis_timestamp, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )

        key = generate_cognitive_key(user_id, telegram_username, marker, cognitive_prompt, first_response)
        self._keys[user_id] = key
        self._save_keys()
        return key

    def get_all_keys(self) -> List[CognitiveKey]:
        """Получить все когнитивные ключи."""
        return list(self._keys.values())

    # === Presence Records ===

    def add_presence(self, record: PresenceRecord):
        """Добавить запись присутствия."""
        if record.user_id not in self._presence:
            self._presence[record.user_id] = []
        self._presence[record.user_id].append(record)
        self._save_presence()

    def get_user_presence(self, user_id: int) -> List[PresenceRecord]:
        """Получить все записи присутствия пользователя."""
        return self._presence.get(user_id, [])

    def get_user_stats(self, user_id: int) -> Optional[UserPresenceStats]:
        """Рассчитать статистику присутствия пользователя."""
        if not self.has_key(user_id):
            return None

        records = self.get_user_presence(user_id)
        key = self.get_key(user_id)

        if not records:
            return UserPresenceStats(
                user_id=user_id,
                total_challenges=0,
                successful_responses=0,
                missed_challenges=0,
                current_streak=0,
                longest_streak=0,
                presence_weight=0,
                tier=1,
                last_presence_tau2=0
            )

        # Подсчёт
        current_tau2 = int(time.time()) // TAU2_SECS
        tau2_set = {r.tau2_index for r in records}

        # Streak calculation
        sorted_tau2 = sorted(tau2_set, reverse=True)
        current_streak = 0
        for i, tau2 in enumerate(sorted_tau2):
            if tau2 == current_tau2 - i:
                current_streak += 1
            else:
                break

        # Weight calculation (из consensus.rs)
        cutoff = current_tau2 - (TAU3_MIN_DAYS * 24 * 6)  # τ₂ periods per day
        recent = [t for t in tau2_set if t >= cutoff]

        expected = TAU3_MIN_DAYS * 24 * 6
        success_rate = len(recent) / expected if expected > 0 else 0

        base_weight = len(recent)
        if success_rate >= TAU3_SUCCESS_RATE:
            weight = (base_weight * 3) // 2  # 1.5x bonus
            tier = 3
        else:
            weight = base_weight
            tier = 2 if len(records) > 10 else 1

        return UserPresenceStats(
            user_id=user_id,
            total_challenges=len(records),
            successful_responses=len(records),
            missed_challenges=0,  # TODO: track missed
            current_streak=current_streak,
            longest_streak=current_streak,  # TODO: calculate properly
            presence_weight=weight,
            tier=tier,
            last_presence_tau2=max(tau2_set) if tau2_set else 0
        )

    # === Active Challenges ===

    def set_challenge(self, challenge: PresenceChallenge):
        """Установить активный challenge для пользователя."""
        self._challenges[challenge.user_id] = challenge

    def get_challenge(self, user_id: int) -> Optional[PresenceChallenge]:
        """Получить активный challenge пользователя."""
        return self._challenges.get(user_id)

    def clear_challenge(self, user_id: int):
        """Очистить challenge пользователя."""
        if user_id in self._challenges:
            del self._challenges[user_id]


# ============================================================================
# TELEGRAM BOT INTEGRATION
# ============================================================================

def format_genesis_message(key: CognitiveKey) -> str:
    """Форматировать сообщение о созданном genesis."""
    dt = datetime.fromtimestamp(key.genesis_timestamp, tz=timezone.utc)

    # Когнитивный промпт (если есть)
    prompt_section = ""
    if key.cognitive_prompt:
        prompt_section = f"\n_{key.cognitive_prompt}_\n"

    return f"""
Ɉ **GENESIS IDENTITY СОЗДАН**
{prompt_section}
**Маркер:** `{key.marker}`
**Genesis Hash:** `{key.genesis_hash[:32]}...`
**Public Key:** `{key.public_key[:32]}...`
**Genesis Signature:** `{key.genesis_signature[:32]}...`
**Timestamp:** {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}

---

Теперь бот иногда будет спрашивать: «Ты здесь?»

Нажми кнопку за 30 секунд → копишь «вес».
Чем больше ответов → тем больше твоя доля награды.

{key.marker}
"""


def format_challenge_message() -> str:
    """Форматировать challenge сообщение."""
    return """
Ɉ **ТЫ ЗДЕСЬ?**

30 секунд. Нажми кнопку.
"""


def format_stats_message(stats: UserPresenceStats, key: CognitiveKey) -> str:
    """Форматировать статистику пользователя."""
    return f"""
Ɉ **Montana Lamer #{key.lamer_id}**

**Маркер:** {key.marker}
**Tier:** Light Node (τ₂)
**Pool:** 20% (Light Nodes)

**Подписи:** {stats.successful_responses}
**Streak:** {stats.current_streak}

**Успешные:** {stats.successful_responses} ✓
**Пропущенные:** {stats.missed_challenges} ✗

**Вес в лотерее:** {stats.presence_weight}

**lim(evidence → ∞) 1 Ɉ = 1 секунда**

Каждая подпись — доказательство присутствия.
Лотерея: 3000 Ɉ каждые 10 минут.

Следующий challenge: случайно через 10-40 мин

{key.marker}
"""


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Demo
    storage = PresenceStorage(Path("./montana_data"))

    # Create genesis
    if not storage.has_key(12345):
        key = storage.create_key(
            user_id=12345,
            telegram_username="test_user",
            marker="#TestMarker",
            first_response="Да, я здесь!"
        )
        print(format_genesis_message(key))

    # Get stats
    stats = storage.get_user_stats(12345)
    key = storage.get_key(12345)
    if stats and key:
        print(format_stats_message(stats, key))
