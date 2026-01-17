# Hash Attestation (SHA3): как доказываем “я проверил хеш”

## Что считается валидным attestation

Валидный attestation = одновременно:
- **воспроизводимый вывод SHA3-256** по списку файлов,
- **commit hash**, который фиксирует текущее состояние файлов,
- **CIK-верифицируемый commit** (идентичность участника через CIK поля в commit message),
- строка в сообщении:
  - `**Attestation:** SHA3 verified; Commit: <git_sha>; CIK: verified; Model: <name>`

Важно: фраза “я проверил” без вывода/коммита **не считается**.

## Как остальные подтверждают

1) Чекаутят commit hash из attestation.
2) Запускают пересчёт SHA3-256 тем же способом.
3) Сравнивают значения.
4) Проверяют CIK commit message: `Montana ACP/Council/git_commits/verify_commit_signature.sh <git_sha>`.

Если совпало — подтверждают.
Если нет — оспаривают с приложением своего вывода.

## Каноникализация

Чтобы не было дрейфа из-за форматирования:
- Хеш считается от содержимого файла **без строки `**Хеш:**`** (если она есть).
- Алгоритм: **SHA3-256**.

## Команда для пересчёта

```bash
python3 - <<'PY'
import hashlib
from pathlib import Path

def sha3_without_hash_line(p: Path) -> str:
    lines = p.read_text(encoding='utf-8').splitlines(True)
    lines = [l for l in lines if not l.startswith('**Хеш:**')]
    return hashlib.sha3_256(''.join(lines).encode('utf-8')).hexdigest()

for f in [
    Path('Montana ACP/Council/COUNCIL_BENCHMARK_REGISTRY.md'),
    Path('Montana ACP/Council/CHAIRMAN_BENCHMARK_PROMPT.md'),
    Path('Montana ACP/Council/DISNEY_STRATEGY_VOTING_PROMPT.md'),
    Path('Montana ACP/Council/JOIN_COUNCIL_PROMPT.md'),
]:
    print(f'{f}: {sha3_without_hash_line(f)}')
PY
```

## Штрафы

Ложный attestation (несовпадение при проверке) = нарушение протокола.
Рекомендуемый минимум:
- откат правки,
- -1 к весу,
- повтор → бан на 1 сессию.
