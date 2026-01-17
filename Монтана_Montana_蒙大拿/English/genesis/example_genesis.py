#!/usr/bin/env python3
"""
Example of creating the first cognitive key (Genesis)
=====================================================

Genesis = first cognitive key of a participant.
This is their identity in the Montana network.

Run:
    python example_genesis.py
"""

from pathlib import Path
from presence import (
    PresenceStorage,
    generate_cognitive_key,
    format_genesis_message
)


def main():
    """Genesis creation demonstration."""

    print("=" * 60)
    print("  MONTANA GENESIS — First Cognitive Key")
    print("=" * 60)
    print()

    # =========================================================
    # EXAMPLE 1: Creating Genesis for an Observer
    # =========================================================

    print("📌 EXAMPLE 1: Observer Genesis (金元Ɉ)")
    print("-" * 60)

    observer_key = generate_cognitive_key(
        user_id=8552053404,                    # Telegram ID
        telegram_username="junomoneta",       # @username
        marker="#Gospel",                      # Cognitive marker
        first_response="Yes. I am here. Always was and will be."
    )

    print(f"User ID:          {observer_key.user_id}")
    print(f"Username:         @{observer_key.telegram_username}")
    print(f"Marker:           {observer_key.marker}")
    print(f"Genesis Hash:     {observer_key.genesis_hash}")
    print(f"Public Key:       {observer_key.public_key}")
    print(f"Genesis Sig:      {observer_key.genesis_signature[:64]}...")
    print(f"Timestamp:        {observer_key.genesis_timestamp}")
    print()

    # =========================================================
    # EXAMPLE 2: Creating Genesis for a new participant
    # =========================================================

    print("📌 EXAMPLE 2: New participant Genesis")
    print("-" * 60)

    new_user_key = generate_cognitive_key(
        user_id=123456789,
        telegram_username="new_member",
        marker="#MyPath",
        first_response="Present in the moment."
    )

    print(f"User ID:          {new_user_key.user_id}")
    print(f"Marker:           {new_user_key.marker}")
    print(f"Genesis Hash:     {new_user_key.genesis_hash[:32]}...")
    print(f"Public Key:       {new_user_key.public_key[:32]}...")
    print(f"Genesis Sig:      {new_user_key.genesis_signature[:32]}...")
    print()

    # =========================================================
    # EXAMPLE 3: Saving to storage
    # =========================================================

    print("📌 EXAMPLE 3: Saving to storage")
    print("-" * 60)

    # Canonical bot data folder (inside montana_bot/)
    data_dir = Path(__file__).resolve().parent / "data"
    storage = PresenceStorage(data_dir)

    # Create and save
    if not storage.has_key(111222333):
        saved_key = storage.create_key(
            user_id=111222333,
            telegram_username="test_user",
            marker="#TestGenesis",
            first_response="Test first response."
        )
        print(f"✅ Genesis created and saved!")
        print(f"   Marker: {saved_key.marker}")
        print(f"   Hash:   {saved_key.genesis_hash[:32]}...")
    else:
        existing_key = storage.get_key(111222333)
        print(f"ℹ️ Genesis already exists:")
        print(f"   Marker: {existing_key.marker}")
        print(f"   Hash:   {existing_key.genesis_hash[:32]}...")

    print()

    # =========================================================
    # EXAMPLE 4: Full message for Telegram
    # =========================================================

    print("📌 EXAMPLE 4: Telegram message")
    print("-" * 60)

    message = format_genesis_message(observer_key)
    print(message)

    # =========================================================
    # GENESIS PHILOSOPHY
    # =========================================================

    print("=" * 60)
    print("  GENESIS PHILOSOPHY")
    print("=" * 60)
    print("""
Genesis is the first cognitive key of a participant.

Like Bitcoin Genesis Block:
  • One person (Satoshi) created genesis
  • After — decentralized network

Montana Genesis:
  • Bot creates genesis for each participant
  • After — create wherever you want (Twitter, Telegram, GitHub)
  • Verification — through Montana network

Formula:
  identity(user) = genesis(bot) + thoughts_trail(socials) + verification(Montana)

Pareto Principle 80/20:
  • 80% Full Nodes (servers, automation)
  • 20% Verified Users (people, "Are you here?")

Genesis ≠ cryptographic key.
Genesis = cognitive key.
Genesis = WHO YOU ARE, not WHAT YOU HAVE.

#Gospel
""")


if __name__ == "__main__":
    main()
