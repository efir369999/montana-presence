#!/usr/bin/env python3
"""
创建第一个认知密钥（创世）的示例
================================

创世 = 参与者的第一个认知密钥。
这是他们在Montana网络中的身份。

运行：
    python example_genesis.py
"""

from pathlib import Path
from presence import (
    PresenceStorage,
    generate_cognitive_key,
    format_genesis_message
)


def main():
    """创世创建演示。"""

    print("=" * 60)
    print("  MONTANA 创世 — 第一个认知密钥")
    print("=" * 60)
    print()

    # =========================================================
    # 示例 1：为观察者创建创世
    # =========================================================

    print("📌 示例 1：观察者创世 (金元Ɉ)")
    print("-" * 60)

    observer_key = generate_cognitive_key(
        user_id=8552053404,                    # Telegram ID
        telegram_username="junomoneta",       # @username
        marker="#福音",                         # 认知标记
        first_response="是的。我在这里。一直都在，也将一直在。"
    )

    print(f"用户 ID：         {observer_key.user_id}")
    print(f"用户名：          @{observer_key.telegram_username}")
    print(f"标记：            {observer_key.marker}")
    print(f"创世哈希：        {observer_key.genesis_hash}")
    print(f"公钥：            {observer_key.public_key}")
    print(f"创世签名：        {observer_key.genesis_signature[:64]}...")
    print(f"时间戳：          {observer_key.genesis_timestamp}")
    print()

    # =========================================================
    # 示例 2：为新参与者创建创世
    # =========================================================

    print("📌 示例 2：新参与者创世")
    print("-" * 60)

    new_user_key = generate_cognitive_key(
        user_id=123456789,
        telegram_username="new_member",
        marker="#我的路",
        first_response="当下存在。"
    )

    print(f"用户 ID：         {new_user_key.user_id}")
    print(f"标记：            {new_user_key.marker}")
    print(f"创世哈希：        {new_user_key.genesis_hash[:32]}...")
    print(f"公钥：            {new_user_key.public_key[:32]}...")
    print(f"创世签名：        {new_user_key.genesis_signature[:32]}...")
    print()

    # =========================================================
    # 示例 3：保存到存储
    # =========================================================

    print("📌 示例 3：保存到存储")
    print("-" * 60)

    # 规范的机器人数据文件夹（在montana_bot/内）
    data_dir = Path(__file__).resolve().parent / "data"
    storage = PresenceStorage(data_dir)

    # 创建并保存
    if not storage.has_key(111222333):
        saved_key = storage.create_key(
            user_id=111222333,
            telegram_username="test_user",
            marker="#测试创世",
            first_response="测试第一个响应。"
        )
        print(f"✅ 创世已创建并保存！")
        print(f"   标记：{saved_key.marker}")
        print(f"   哈希：{saved_key.genesis_hash[:32]}...")
    else:
        existing_key = storage.get_key(111222333)
        print(f"ℹ️ 创世已存在：")
        print(f"   标记：{existing_key.marker}")
        print(f"   哈希：{existing_key.genesis_hash[:32]}...")

    print()

    # =========================================================
    # 示例 4：Telegram的完整消息
    # =========================================================

    print("📌 示例 4：Telegram消息")
    print("-" * 60)

    message = format_genesis_message(observer_key)
    print(message)

    # =========================================================
    # 创世哲学
    # =========================================================

    print("=" * 60)
    print("  创世哲学")
    print("=" * 60)
    print("""
创世是参与者的第一个认知密钥。

像比特币创世区块一样：
  • 一个人（中本聪）创建了创世
  • 之后 — 去中心化网络

Montana创世：
  • 机器人为每个参与者创建创世
  • 之后 — 在你想要的地方创作（Twitter、Telegram、GitHub）
  • 验证 — 通过Montana网络

公式：
  identity(user) = genesis(bot) + thoughts_trail(socials) + verification(Montana)

帕累托原则 80/20：
  • 80% 全节点（服务器，自动化）
  • 20% 验证用户（人类，"你在这里吗？"）

创世 ≠ 加密密钥。
创世 = 认知密钥。
创世 = 你是谁，而不是你拥有什么。

#福音
""")


if __name__ == "__main__":
    main()
