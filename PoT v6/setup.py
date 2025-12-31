"""
PoT Protocol v6 Setup
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read() if f else ""

setup(
    name="pot-protocol",
    version="0.6.1",
    author="PoT Protocol Team",
    description="Proof of Time Protocol v6 Implementation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pot-protocol/pot-v6",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.10",
    install_requires=[
        "pycryptodome>=3.19.0",
        "ntplib>=0.4.0",
        "httpx>=0.25.0",
        "aiohttp>=3.9.0",
        "aiosqlite>=0.19.0",
    ],
    extras_require={
        "crypto": [
            "liboqs-python>=0.9.0",
            "argon2-cffi>=23.1.0",
        ],
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-timeout>=2.2.0",
            "maturin>=1.4.0",
        ],
        "full": [
            "liboqs-python>=0.9.0",
            "argon2-cffi>=23.1.0",
            "websockets>=12.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "pot-node=pot.node.node:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Security :: Cryptography",
        "Topic :: System :: Distributed Computing",
    ],
    keywords="blockchain cryptocurrency proof-of-time vdf stark post-quantum",
)
