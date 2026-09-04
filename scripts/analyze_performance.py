"""
STEP 8 (フェーズ3): 蓄積されたインサイトから、
・テーマ別のパフォーマンススコア更新
・カテゴリ比率(category_weights)の自動調整
を行う。データがまだ少ない期間は変化を小さく抑える。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import db


def compute_post_score(post: dict) -> float | None:
    """保存・シェアを重視した複合スコア。データが無いものはNoneを返す"""
    if post.get("saves") is None and post.get("reach") is None:
        return None
    saves = post.get("saves") or 0
    shares = post.get("shares") or 0
    likes = post.get("likes") or 0
    reach = post.get("reach") or 0
    comments = post.get("comments") or 0
    # KPI優先順位(フォロワー増>非フォロワーリーチ>フォロー転換率>シェア>保存...)を反映した重み付け。
    # new_followers/profile_visitsは現状取得できないため、保存・シェア・リーチ・コメントで代替する。
    return saves * 4 + shares * 4 + comments * 2 + likes * 1 + reach * 0.05


def analyze_and_update(min_samples_for_weight_change: int = 5) -> dict:
    posts = db.get_recent_posts(limit=200, status="posted")
    scored = [(p, compute_post_score(p)) for p in posts]
    scored = [(p, s) for p, s in scored if s is not None]

    if not scored:
        return {"message": "インサイト付きの投稿がまだありません。分析をスキップしました。"}

    # テーマ別パフォーマンス更新
    by_theme: dict[str, list[float]] = {}
    by_category: dict[str, list[float]] = {}
    for p, s in scored:
        by_theme.setdefault(p["theme"], []).append(s)
        if p.get("category"):
            by_category.setdefault(p["category"], []).append(s)

    for theme, scores in by_theme.items():
        avg = sum(scores) / len(scores)
        db.update_topic_performance(theme, avg)

    report = {"theme_performance": {t: sum(s) / len(s) for t, s in by_theme.items()}}

    # カテゴリ比率の調整(サンプルが少なすぎる場合は変更しない)
    if len(scored) >= min_samples_for_weight_change and by_category:
        overall_avg = sum(s for _, s in scored) / len(scored)
        current_weights = db.get_category_weights()
        new_weights = {}
        for category, weight in current_weights.items():
            cat_scores = by_category.get(category)
            if not cat_scores:
                new_weights[category] = weight
                continue
            cat_avg = sum(cat_scores) / len(cat_scores)
            ratio = cat_avg / overall_avg if overall_avg > 0 else 1.0
            # 一度に大きく動かしすぎないよう変化を±20%以内に制限
            ratio = max(0.8, min(1.2, ratio))
            new_weight = round(weight * ratio, 2)
            new_weights[category] = new_weight
            db.set_category_weight(category, new_weight)
        report["updated_category_weights"] = new_weights
    else:
        report["updated_category_weights"] = None
        report["note"] = f"サンプル数({len(scored)}件)が少ないため、カテゴリ比率は変更していません(閾値: {min_samples_for_weight_change}件)"

    return report


if __name__ == "__main__":
    result = analyze_and_update()
    import json

    print(json.dumps(result, ensure_ascii=False, indent=2))
