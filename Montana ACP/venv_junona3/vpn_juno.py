"""
VPN Juno Montana
Модуль для управления VPN через бота Юноны

За пользу миру. Резервное обеспечение сети. Вера в Монтану.
bc1qrezesm4qd9qyxtg2x7agdvzn94rwgsee8x77gw
"""

import asyncio
import subprocess
import os
import logging
from io import BytesIO
from datetime import datetime
from typing import Optional, Tuple

# Узлы сети Montana
VPN_NODES = {
    1: {"name": "Амстердам", "ip": "72.56.102.240", "flag": "🇳🇱"},
    2: {"name": "Москва", "ip": "176.124.208.93", "flag": "🇷🇺"},
    3: {"name": "Алматы", "ip": "91.200.148.93", "flag": "🇰🇿"},
    4: {"name": "СПб", "ip": "188.225.58.98", "flag": "🇷🇺"},
    5: {"name": "Новосибирск", "ip": "147.45.147.247", "flag": "🇷🇺"},
}

# Порт WireGuard
WG_PORT = 51820

# Лог
log = logging.getLogger(__name__)


def get_vpn_nodes_text() -> str:
    """Возвращает текст со списком узлов"""
    text = "🌐 *VPN Juno Montana*\n\n"
    text += "Выбери узел:\n\n"
    for num, node in VPN_NODES.items():
        text += f"{node['flag']} *{num}. {node['name']}*\n"
        text += f"   `{node['ip']}:{WG_PORT}`\n\n"
    text += "_За пользу миру. Резервное обеспечение сети._"
    return text


async def generate_vpn_config(
    node_num: int,
    client_name: str,
    user_id: int
) -> Tuple[Optional[str], Optional[bytes], Optional[str]]:
    """
    Генерирует VPN конфиг для клиента

    Returns:
        (config_text, qr_png_bytes, error_message)
    """
    if node_num not in VPN_NODES:
        return None, None, f"Неизвестный узел: {node_num}"

    node = VPN_NODES[node_num]
    server_ip = node['ip']

    # Уникальное имя клиента
    safe_name = f"tg_{user_id}_{client_name}".replace(" ", "_")[:32]

    try:
        # Команда для создания клиента на сервере
        # Скрипт add_client.sh должен быть установлен на сервере
        ssh_cmd = f"""ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 root@{server_ip} '
            if [ -f /etc/wireguard/add_client_silent.sh ]; then
                /etc/wireguard/add_client_silent.sh "{safe_name}"
            else
                echo "ERROR: VPN не настроен на этом узле"
                exit 1
            fi
        '"""

        log.info(f"VPN: Создание клиента {safe_name} на {node['name']}")

        # Выполняем команду
        process = await asyncio.create_subprocess_shell(
            ssh_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30
        )

        if process.returncode != 0:
            error = stderr.decode().strip() or stdout.decode().strip()
            log.error(f"VPN: Ошибка создания клиента: {error}")
            return None, None, f"Ошибка на сервере: {error}"

        config_text = stdout.decode().strip()

        if not config_text or "ERROR" in config_text:
            return None, None, config_text or "Неизвестная ошибка"

        # Генерируем QR локально из конфига
        qr_png = await generate_qr_png(config_text)

        log.info(f"VPN: Клиент {safe_name} создан успешно")
        return config_text, qr_png, None

    except asyncio.TimeoutError:
        log.error(f"VPN: Таймаут подключения к {server_ip}")
        return None, None, "Таймаут подключения к серверу"
    except Exception as e:
        log.error(f"VPN: Исключение: {e}")
        return None, None, f"Ошибка: {str(e)}"


async def generate_qr_png(config_text: str) -> Optional[bytes]:
    """Генерирует QR-код как PNG из конфига"""
    try:
        # Используем qrencode если доступен
        process = await asyncio.create_subprocess_exec(
            'qrencode', '-o', '-', '-t', 'PNG', '-s', '6',
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate(input=config_text.encode())

        if process.returncode == 0 and stdout:
            return stdout

        # Fallback: используем Python библиотеку
        try:
            import qrcode
            from io import BytesIO

            qr = qrcode.QRCode(version=1, box_size=6, border=2)
            qr.add_data(config_text)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            return buffer.getvalue()
        except ImportError:
            log.warning("VPN: qrcode library not available")
            return None

    except FileNotFoundError:
        log.warning("VPN: qrencode not installed")
        return None
    except Exception as e:
        log.error(f"VPN: QR generation error: {e}")
        return None


async def check_vpn_status(node_num: int) -> Tuple[bool, str]:
    """Проверяет статус VPN на узле"""
    if node_num not in VPN_NODES:
        return False, "Неизвестный узел"

    node = VPN_NODES[node_num]
    server_ip = node['ip']

    try:
        ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@{server_ip} 'wg show wg0 2>/dev/null || echo OFFLINE'"

        process = await asyncio.create_subprocess_shell(
            ssh_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(
            process.communicate(),
            timeout=10
        )

        output = stdout.decode().strip()

        if "OFFLINE" in output or not output:
            return False, "VPN не активен"

        # Парсим количество клиентов
        peers = output.count("peer:")
        return True, f"Активен, клиентов: {peers}"

    except Exception as e:
        return False, f"Ошибка: {str(e)}"


def get_vpn_help_text() -> str:
    """Справка по VPN"""
    return """🌐 *VPN Juno Montana*

*Команды:*
`/vpn` — список узлов
`/vpn 1` — подключиться к Амстердаму
`/vpn 2` — подключиться к Москве
`/vpn 3` — подключиться к Алматы
`/vpn 4` — подключиться к СПб
`/vpn 5` — подключиться к Новосибирску

*Как подключиться:*
1. Установи WireGuard на устройство
2. Напиши `/vpn 1` (или другой номер)
3. Отсканируй QR или импортируй файл

*Ссылки на WireGuard:*
• [iOS App Store](https://apps.apple.com/app/wireguard/id1441195209)
• [Android Play Store](https://play.google.com/store/apps/details?id=com.wireguard.android)
• [macOS App Store](https://apps.apple.com/app/wireguard/id1451685025)
• [Windows](https://www.wireguard.com/install/)

_За пользу миру. Резервное обеспечение сети. Вера в Монтану._
`bc1qrezesm4qd9qyxtg2x7agdvzn94rwgsee8x77gw`
"""
