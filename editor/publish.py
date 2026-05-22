#!/usr/bin/env python3
"""
publish.py — переносить редактором схвалені статті з pending_review.json
у відповідний дата-файл /data/YYYY-MM-DD.json.

Використання:
    python3 editor/publish.py ~/Downloads/ready-2026-05-22T14-30-00.json

Файл ready-*.json експортується з editor/review.html через кнопку
«↓ Експортувати готові». Формат:
{
  "ready":    [<статті з editor_reviewed=true>],
  "rejected": [<id які треба видалити з черги>],
  "kept":     [<id які лишаються в черзі>]
}

Що робить скрипт:
1. Читає ready-*.json
2. Для кожної ready-статті:
   - визначає цільовий день за полем published
   - додає її в data/YYYY-MM-DD.json (dedup за id)
3. Видаляє з pending_review.json всі ready+rejected id
4. Виводить summary

Після цього: git add data/ && git commit && git push
"""

import json
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PENDING_FILE = DATA_DIR / "pending_review.json"


def load_json(path: Path) -> list:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def target_date_file(story: dict) -> Path:
    """День публікації беремо з поля published. Fallback — сьогодні."""
    pub = story.get("published") or story.get("fetched") or ""
    try:
        day = pub[:10]
        datetime.strptime(day, "%Y-%m-%d")
    except Exception:
        day = datetime.now().strftime("%Y-%m-%d")
    return DATA_DIR / f"{day}.json"


def main(input_path: str):
    src = Path(input_path).expanduser()
    if not src.exists():
        print(f"❌ Файл не знайдено: {src}")
        sys.exit(1)

    payload = json.loads(src.read_text(encoding="utf-8"))
    ready = payload.get("ready", [])
    rejected_ids = set(payload.get("rejected", []))
    kept_ids = set(payload.get("kept", []))

    print(f"📥 Отримано: {len(ready)} готових, {len(rejected_ids)} відхилених, {len(kept_ids)} лишити в черзі\n")

    # 1. Розподілити ready-статті по днях
    by_day: dict[Path, list] = {}
    for story in ready:
        target = target_date_file(story)
        by_day.setdefault(target, []).append(story)

    total_added = 0
    for day_file, items in by_day.items():
        existing = load_json(day_file)
        existing_ids = {a.get("id") for a in existing if a.get("id")}
        new_items = [s for s in items if s.get("id") not in existing_ids]
        existing.extend(new_items)
        save_json(day_file, existing)
        total_added += len(new_items)
        print(f"  ✓ {day_file.name}: +{len(new_items)} (всього {len(existing)})")

    # 2. Оновити чергу — лишити тільки kept
    pending = load_json(PENDING_FILE)
    processed_ids = {s["id"] for s in ready if s.get("id")} | rejected_ids
    new_pending = [p for p in pending if p.get("id") not in processed_ids]
    save_json(PENDING_FILE, new_pending)

    print(f"\n  ✓ pending_review.json: {len(pending)} → {len(new_pending)} (видалено {len(pending)-len(new_pending)})")
    print(f"\n✅ Опубліковано {total_added} статей. Тепер:")
    print(f"   git add data/")
    print(f"   git commit -m 'editor: publish {total_added} reviewed stories'")
    print(f"   git push")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
