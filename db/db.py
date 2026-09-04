"""
SQLiteデータベースへの薄いアクセス層。
外部DBサーバー不要で、GitHub Actions上でも `db/leapconnect.sqlite3` を
リポジトリにコミットして永続化する運用を想定(insta-auto-posterのtopic_history.json方式と同じ考え方)。
"""
import datetime
import difflib
import json
import os
import sqlite3
import uuid

DB_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(DB_DIR, "leapconnect.sqlite3")
SCHEMA_PATH = os.path.join(DB_DIR, "schema.sql")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    conn = get_connection()
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- posts ----

def create_post(**fields) -> str:
    post_id = fields.get("id") or str(uuid.uuid4())
    fields["id"] = post_id
    fields.setdefault("date", now_iso()[:10])
    fields.setdefault("status", "draft")

    json_fields = ("slide_texts", "hashtags", "image_paths", "image_prompts", "quality_breakdown")
    for jf in json_fields:
        if jf in fields and not isinstance(fields[jf], str):
            fields[jf] = json.dumps(fields[jf], ensure_ascii=False)

    columns = ", ".join(fields.keys())
    placeholders = ", ".join(["?"] * len(fields))
    conn = get_connection()
    try:
        conn.execute(f"INSERT INTO posts ({columns}) VALUES ({placeholders})", tuple(fields.values()))
        conn.commit()
    finally:
        conn.close()
    return post_id


def update_post(post_id: str, **fields) -> None:
    json_fields = ("slide_texts", "hashtags", "image_paths", "image_prompts", "quality_breakdown")
    for jf in json_fields:
        if jf in fields and not isinstance(fields[jf], str):
            fields[jf] = json.dumps(fields[jf], ensure_ascii=False)

    set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
    conn = get_connection()
    try:
        conn.execute(f"UPDATE posts SET {set_clause} WHERE id = ?", (*fields.values(), post_id))
        conn.commit()
    finally:
        conn.close()


def get_post(post_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_recent_posts(limit: int = 60, status: str | None = None) -> list[dict]:
    conn = get_connection()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM posts WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status, limit)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_posts_pending_insights(older_than_hours: int = 24, limit: int = 30) -> list[dict]:
    """投稿済みだがまだインサイトを取得していない(または取得から日が浅い)投稿"""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM posts
            WHERE status = 'posted'
              AND posted_at IS NOT NULL
              AND datetime(posted_at) <= datetime('now', ?)
            ORDER BY posted_at ASC
            LIMIT ?
            """,
            (f"-{older_than_hours} hours", limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --------------------------------------------------------------- topics ----

def record_topic_usage(topic: str, category: str, score: float) -> None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT id, used_count FROM topics WHERE topic = ?", (topic,)).fetchone()
        if row:
            conn.execute(
                "UPDATE topics SET used_count = ?, last_used = ?, score = ? WHERE id = ?",
                (row["used_count"] + 1, now_iso(), score, row["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO topics (topic, category, score, used_count, last_used) VALUES (?, ?, ?, 1, ?)",
                (topic, category, score, now_iso()),
            )
        conn.commit()
    finally:
        conn.close()


def update_topic_performance(topic: str, performance: float) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE topics SET performance = ? WHERE topic = ?", (performance, topic))
        conn.commit()
    finally:
        conn.close()


def get_category_weights() -> dict[str, float]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT category, weight FROM category_weights").fetchall()
        return {r["category"]: r["weight"] for r in rows}
    finally:
        conn.close()


def set_category_weight(category: str, weight: float) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO category_weights (category, weight, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(category) DO UPDATE SET weight = excluded.weight, updated_at = excluded.updated_at",
            (category, weight, now_iso()),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------- layout使用履歴 ----

def record_layout_usage(layout_type: str, post_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute("INSERT INTO layout_history (layout_type, post_id) VALUES (?, ?)", (layout_type, post_id))
        conn.commit()
    finally:
        conn.close()


def get_recent_layouts(limit: int = 3) -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT layout_type FROM layout_history ORDER BY used_at DESC LIMIT ?", (limit,)).fetchall()
        return [r["layout_type"] for r in rows]
    finally:
        conn.close()


# ------------------------------------------------------- creative_assets ----

def record_creative_asset(post_id: str, slide_index: int, image_path: str, prompt: str, theme: str) -> None:
    import hashlib

    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO creative_assets (post_id, slide_index, image_path, prompt, theme, used_date, prompt_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (post_id, slide_index, image_path, prompt, theme, now_iso()[:10], prompt_hash),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_prompts(limit: int = 60) -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT prompt FROM creative_assets ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [r["prompt"] for r in rows]
    finally:
        conn.close()


# -------------------------------------------------------------- 重複チェック ----

def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def is_too_similar_to_recent(candidate_text: str, recent_texts: list[str], threshold: float = 0.72) -> tuple[bool, str | None]:
    """candidate_textが直近投稿のいずれかと似すぎていないかチェック。
    似すぎている場合は (True, 該当テキスト) を返す"""
    for t in recent_texts:
        if not t:
            continue
        if similarity(candidate_text, t) >= threshold:
            return True, t
    return False, None


if __name__ == "__main__":
    init_db()
    print(f"DB初期化しました: {DB_PATH}")
