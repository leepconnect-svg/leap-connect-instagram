# leap_connect Instagram自動化システム

不動産管理会社アカウント **@leap_connect(首都圏オーナー相談室)** 向けの
自律型Instagramマーケティングシステムです。

毎日: テーマ企画 → 6枚カルーセル台本生成 → AI画像生成 → ブランドデザインで合成 →
AI品質審査(100点満点、80点未満は自動修正) → Instagram公式APIで投稿 → DB記録 →
(投稿から時間が経ったら)インサイト取得 → パフォーマンス分析 → 翌日以降の企画へ反映

を自動で行います。最終目標は「フォロワー増加 → 信頼 → 空室/管理相談 → 管理受託 → サブリース契約」の導線構築です。

---

## 0. 全体構成(3フェーズ)

| フェーズ | 内容 | ステータス |
|---|---|---|
| 1 | テーマ企画〜画像生成〜品質審査〜DRY_RUN確認 | ✅ 動作確認済み(モックテスト済み) |
| 2 | Instagram公式APIでの自動投稿 + 毎日のスケジュール実行 | ✅ 実装済み(実アカウントでの実地テストが必要) |
| 3 | 投稿後インサイト取得 → 分析 → カテゴリ比率の自動調整 | ✅ 実装済み(意味のあるデータが溜まるまで数週間かかる) |

フェーズ1・2は今すぐ使えます。フェーズ3は投稿実績が溜まるほど精度が上がる仕組みです。

---

## 1. 必要なAPIキー・アカウント

| サービス | 用途 | 費用目安 | 取得先 |
|---|---|---|---|
| Anthropic API (Claude) | 台本生成・品質審査 | 1投稿あたり数円〜十数円程度 | https://console.anthropic.com/ |
| OpenAI API (gpt-image-1) | 6枚の背景写真生成 | 1投稿(6枚)あたり数十円〜100円程度 | https://platform.openai.com/ |
| ImgBB | 画像を一時的に公開URL化 | 無料 | https://api.imgbb.com/ |
| Instagram (leap_connect) | 投稿先 | - | ビジネス/クリエイターアカウント化が必要 |

**月間コスト目安(1日1投稿・6枚)**: おおよそ数千円程度(画像生成が主なコスト)。
画質設定(`OPENAI_IMAGE_MODEL`のquality)を下げる/画像を使い回す等でさらに抑制可能です。

**注意**: Anthropic APIキーは、Claude Codeの月額契約とは別の従量課金契約です。console.anthropic.comで新規に発行し、支払い方法を登録してください。

---

## 2. Instagramアカウントの準備(Facebookページ連携なし)

今回は「Instagram API with Instagram Login」という、Facebookページとの連携が不要な新しい方式を使います。

### 2-1. Instagramをプロアカウント化
1. Instagramアプリ → プロフィール → 「アカウントの種類とツール」
2. 「プロアカウントに切り替える」→ 「ビジネス」を選択(Facebookページとの連携はスキップしてOK)

### 2-2. Meta for Developersでアプリ作成
1. https://developers.facebook.com/apps/ → 「アプリを作成」→ タイプ「ビジネス」
2. アプリのダッシュボードで「製品を追加」→ **「Instagram API setup with Instagram business login」** を追加
   (「Instagram Graph API」ではなく、こちらの新しい方を選ぶのがポイントです)
3. 「アプリ設定」→「基本設定」で **Instagram App ID** と **Instagram App Secret** を控える
4. Instagram側の設定で **リダイレクトURI** を登録する(httpsが必須。自社サイトの適当な1ページ、
   例: `https://leap-connect.example.com/ig-callback` のようなURLでよい。実際にページを作る必要はなく、
   認可後にブラウザのアドレスバーに表示される`code`パラメータを目視でコピーできればよい)
5. 「役割」→ 対象のInstagramアカウント(leap_connect)をテスターとして招待し、
   Instagramアプリ側(設定 → アプリとウェブサイト)で招待を承認する

### 2-3. アクセストークンを取得する

```bash
pip install requests

# ① 認可URLを発行
python scripts/setup_helper.py auth_url <APP_ID> <REDIRECT_URI>

# ② 表示されたURLをブラウザで開き、leap_connectアカウントでログイン・許可する
#    許可後のリダイレクト先URLの ?code=xxxx をコピーする

# ③ トークンを取得
python scripts/setup_helper.py exchange <APP_ID> <APP_SECRET> <REDIRECT_URI> <CODE>
```

出力される `IG_USER_ID` と `IG_ACCESS_TOKEN` を後でGitHub Secretsに登録します。
このトークンは約60日で失効するため、期限が近づいたら `scripts/refresh_token.py` で更新してください
(更新もInstagramへの再ログインなしで可能です)。

---

## 3. GitHubリポジトリへのpushとSecrets登録

```bash
cd leap-connect-instagram-ai
git init
git add .
git commit -m "init: leap_connect instagram automation system"
```

GitHubで新規リポジトリを作成し(Private推奨。物件情報やAPIキーに近い情報を扱うため)、pushします。

```bash
git remote add origin <あなたのリポジトリURL>
git branch -M main
git push -u origin main
```

**Settings → Secrets and variables → Actions → New repository secret** で以下を登録:

| Name | 値 |
|---|---|
| `ANTHROPIC_API_KEY` | 1章で取得 |
| `OPENAI_API_KEY` | 1章で取得 |
| `IMGBB_API_KEY` | 1章で取得 |
| `IG_USER_ID` | 2章で取得 |
| `IG_ACCESS_TOKEN` | 2章で取得 |

**Variables**タブでは(任意):

| Name | 値 |
|---|---|
| `BRAND_HANDLE` | `@leap_connect` |

---

## 4. 動作確認

### ローカルでのDRY_RUN確認

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env   REM .envを編集してAPIキーを埋める(IG系は後回しでOK、DRY_RUN=1なら不要)
python scripts/main.py
```

`data/generated/<タイムスタンプ>/final/` に6枚の画像が生成されます。DRY_RUN=1のときはInstagramへの実投稿とDB更新の一部(status=readyまでは記録されます)をスキップします。

### GitHub Actionsでの確認
「Actions」タブ →「leap_connect Daily Instagram Post」→「Run workflow」→ `dry_run` を `1` にして実行。
ログでキャプション・品質スコア・生成された台本を確認できます。

問題なければ `dry_run` を `0` にして実行、または翌日の自動実行(毎日9:00 JST)を待ちます。

---

## 5. システム構成

```
scripts/
  brand_context.py      全AI呼び出しで共有するブランド/ビジネス文脈・禁止事項
  ai_clients.py          Anthropic API / OpenAI Images APIの薄いラッパー
  generate_topics.py     STEP1: テーマ候補生成(10件以上)→スコアリング→重複チェック→選定
  generate_script.py     STEP2: 6枚台本(見出し/本文/画像プロンプト)+キャプション+ハッシュタグ+CTA生成
  generate_images.py     STEP3: OpenAIで背景写真を生成(重複プロンプト検知つき)
  utils_image.py          画像のcover方式リサイズ/クロップ
  utils_text.py           日本語テキストの折り返し(孤立行回避)・フィット
  layouts.py              STEP4: ブランドデザイン(ネイビー×ホワイト×ゴールド)、6種のレイアウト(A/C/E/G/I/J)
  compose_slides.py       台本+写真からレイアウトを適用して6枚を書き出す
  quality_review.py       STEP5: AI品質審査(100点満点、vision入力)+自動修正
  upload_image.py         ImgBBへ画像アップロード(公開URL化)
  post_instagram.py       STEP6: Instagram API(Instagram Login方式)でカルーセル投稿・インサイト取得
  setup_helper.py          初回セットアップ用(アクセストークン取得補助)
  refresh_token.py         長期トークンの更新
  fetch_insights.py        STEP7(フェーズ3): 投稿後のインサイト取得
  analyze_performance.py   STEP8(フェーズ3): パフォーマンス分析・カテゴリ比率自動調整
  main.py                  STEP1〜7を順に実行するオーケストレーター
db/
  schema.sql / db.py       SQLiteスキーマとアクセス層(posts/topics/creative_assets/category_weights)
fonts/                     Noto Sans CJK JP(商用利用可・OFLライセンス)
.github/workflows/
  daily_post.yml            毎日9:00 JSTに自動投稿(フェーズ2)
  insights_and_analysis.yml 毎日22:00 JSTにインサイト取得・分析(フェーズ3)
```

---

## 6. 実装済み/未実装の範囲(正直な現状)

**実装済み**
- テーマ企画AI(重複チェック・スコアリング・カテゴリ比率考慮)
- 6枚台本生成(構成タイプのバリエーション、禁止事項の遵守指示込み)
- AI画像生成(OpenAI、プロンプト重複回避)
- ブランドデザインでの6枚合成(レイアウト**A・C・E・G・I・J**の6種類をローテーション)
- AI品質審査(vision入力、100点満点、80点未満は自動修正を最大2回)
- Instagram公式APIでの自動投稿(カルーセル)
- 投稿DB(posts/topics/creative_assets/category_weights)
- インサイト取得・パフォーマンス分析・カテゴリ比率の自動調整

**未実装/簡略化している範囲(今後の拡張ポイント)**
- レイアウトパターンB・D・F・H・K・L(仕様書は12種類。現在は6種類が動作)。
  `scripts/layouts.py`の`LAYOUT_RENDERERS`に関数を追加すれば拡張できる構造にしてあります
- ファクトチェック(Web検索による最新情報確認)は自動化していません。
  `generate_script.py`のプロンプトで「断定しない・根拠のない数字を使わない」よう強く指示していますが、
  最終的な事実確認は人が行うことを推奨します(特にサブリース・法令に関わる投稿)
- `profile_visits`(プロフィールアクセス)・`new_followers`(フォロワー増加数)・`follow_conversion_rate`は、
  Instagram Graph APIの仕様上、個別投稿に厳密に紐付けて取得することができません
  (アカウント単位の集計値のみ提供されるため)。`reach`・`saves`・`shares`・`likes`・`comments`は
  投稿単位で自動取得・分析に使用しています。プロフィールアクセスやフォロワー増加数を厳密に見たい場合は、
  Instagramアプリの「インサイト」画面を投稿ごとに確認する運用を併用してください
- トークンの自動更新(60日ごと)は`scripts/refresh_token.py`を手動実行する想定です
  (GitHub Secretsの自動更新まで完全自動化する場合はGitHub REST APIとの追加連携が必要です)

---

## 7. カテゴリ比率・重複防止の仕組み

- `db/schema.sql`の`category_weights`テーブルに初期比率(空室45%・賃貸管理20%等)を保持
- `analyze_performance.py`が投稿実績(保存・シェア・リーチ・コメントの複合スコア)を見て、
  好調なカテゴリの比率を±20%の範囲で自動的に増やす(サンプルが5件未満の間は変更しない)
- `generate_topics.py`は過去30件の投稿テーマ・タイトルとの類似度(difflib)をチェックし、
  類似度0.72以上のテーマは大きく減点。台本の言い回し・CTA・画像プロンプトも
  `brand_context.py`で「使い回し禁止」を明示的に指示しています

---

## 8. サブリース導線について

投稿の大半(空室・管理・損失系)ではサブリースを直接売り込みません。
`brand_context.py`にポジショニング方針(営業感を出さない、信頼構築の順序)を明記しており、
すべてのAI呼び出しがこの方針を踏まえて生成します。カテゴリ「サブリース」は
比率5〜10%程度に抑えられ、選択肢の一つとして自然に触れる内容になるよう指示しています。

プロフィールのリンク(bio)には、`LP_URL`(公式サイト/LP)を設定し、
必要であれば`.env.example`の`UTM_PARAMS`を付与したURLをInstagramのプロフィール欄に
手動で設定してください(Instagramの仕様上、キャプション内のURLはクリックできないため、
bioリンクに集約するのが一般的です)。

---

## 9. 注意事項

- 生成される投稿内容は、不動産・法律・税務等について断定的な助言をしないよう設計していますが、
  AIが生成した内容の正確性は保証されません。特にサブリース・法令・管理規約に関わる投稿は、
  運用初期は人の目でも確認することを強く推奨します
- Instagramの規約・API仕様は変更されることがあります。エラーが増えた場合はMeta for Developersの
  最新ドキュメントを確認してください
- 品質スコアが80点未満のまま2回の自動修正でも改善しない場合、投稿は自動的に中止されます
  (`status=failed`としてDBに記録され、無理に投稿はしません)
