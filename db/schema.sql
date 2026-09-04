-- leap_connect Instagram自動化システム DBスキーマ (SQLite)

CREATE TABLE IF NOT EXISTS posts (
    id                       TEXT PRIMARY KEY,
    date                     TEXT NOT NULL,
    theme                    TEXT NOT NULL,
    sub_theme                TEXT,
    category                 TEXT,
    structure_type           TEXT,          -- ランキング型/比較型/チェックリスト型 等
    layout_type              TEXT,          -- A〜L のレイアウトパターン
    title                    TEXT,
    slide_texts              TEXT,          -- JSON配列 (6枚分の見出し/本文/役割)
    caption                  TEXT,
    hashtags                 TEXT,          -- JSON配列
    cta_text                 TEXT,
    image_paths              TEXT,          -- JSON配列 (ローカル保存パス、投稿順)
    image_prompts            TEXT,          -- JSON配列 (画像生成に使ったプロンプト)
    quality_score            INTEGER,
    quality_breakdown        TEXT,          -- JSON (項目別採点)
    revision_count           INTEGER DEFAULT 0,
    status                   TEXT DEFAULT 'draft',  -- draft/ready/posted/failed/rejected
    reject_reason            TEXT,
    ig_media_id              TEXT,
    posted_at                TEXT,
    reach                    INTEGER,
    non_follower_reach       INTEGER,
    likes                    INTEGER,
    saves                    INTEGER,
    shares                   INTEGER,
    comments                 INTEGER,
    profile_visits           INTEGER,
    new_followers            INTEGER,
    follow_conversion_rate   REAL,
    insights_fetched_at      TEXT,
    created_at               TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS topics (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    topic             TEXT NOT NULL,
    category          TEXT,
    score             REAL,
    used_count        INTEGER DEFAULT 0,
    performance       REAL,             -- 実績に基づく平均パフォーマンススコア
    last_used         TEXT,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS creative_assets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id       TEXT,
    slide_index   INTEGER,
    image_path    TEXT,
    prompt        TEXT,
    theme         TEXT,
    used_date     TEXT,
    prompt_hash   TEXT,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

-- カテゴリ別の出稿比率の重み。パフォーマンス分析により定期的に自動調整する。
CREATE TABLE IF NOT EXISTS category_weights (
    category      TEXT PRIMARY KEY,
    weight        REAL NOT NULL,
    updated_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO category_weights (category, weight) VALUES
    ('空室', 45),
    ('賃貸管理', 20),
    ('修繕設備トラブル', 12.5),
    ('オーナー損失リスク', 10),
    ('収益改善賃貸経営', 7.5),
    ('サブリース', 7.5);

-- 直近使用したレイアウトタイプ(連続使用防止用に直近のみ見れば十分だがログとして残す)
CREATE TABLE IF NOT EXISTS layout_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    layout_type   TEXT NOT NULL,
    post_id       TEXT,
    used_at       TEXT DEFAULT CURRENT_TIMESTAMP
);
