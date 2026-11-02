# Numbers4 第2回からの時系列予測とオンライン研究更新

**初版：2026-11-02 JST** · `numbers4-prequential-online-replay-v1` · 研究専用

## 運用対象と説明責任

ナンバーズ4は0〜9の4桁（先頭0を保持）を抽せんするため、公平な一回の抽せんで特定のストレート番号が出る理論確率は **1/10,000**、異なる5番号を選んだ場合の少なくとも一口のストレート一致確率は **5/10,000 = 0.05%** です。正規の結果情報と制度の説明は [みずほ銀行](https://www.mizuhobank.co.jp/takarakuji/products/numbers/index.html) / [宝くじ公式](https://www.takarakuji-official.jp/brand/suji/lineup-numbers4/) を確認してください。

**第2回以降の予測・採点は後から過去の結果を取り出して順番に再現したものであり、1994年に実際に事前発行したという意味ではありません。** 収録した全履歴は二次公開リポジトリの一致記録であり、みずほ銀行一次公表との全件照合・独立性確認は未実施です。したがって、履歴研究で一致した回を正式な事前発行成績・購入実績・利益と混同しません。

## 時系列処理の手順

1. `data/historical_results.csv` は第1回からの連続回号・厳密な日付・`0000`〜`9999`の4文字・Gitハッシュをチェックした研究用台帳です。`audit-history` は破損時に処理を停止します。
2. **第2回**を予測するときの入力は**第1回だけ**。各回で番号5口と確率分布を発行相当の順で生成し、当該回の結果を後から開いて採点した後に限り研究モデルの重みを更新します。対象回以降のデータは使用しません。
3. 4桁一様モデル（理論基準）と、直近60／250／1,000回の桁別Dirichletモデル3種を比較します。損失は確率予測のlog-score・Brier、別指標として5口ストレート一致回数です。
4. 研究モデルのオンライン選択は、直前までの結果だけで計算した損失の忘却係数0.99・学習率0.2の有界更新と、最少100回のウォームアップ／最近90回の平均対数改善を満たす場合に限定します。そうでなければ一様基準を使います。
5. 全回の再現結果は `research/online_round_predictions.csv`、集計と研究限定の次回候補は `research/online_replay.json` に記録します。`historical_frozen_forecasts=false`、`prediction_skill_confirmed=false`、`production_model_changed=false` は必須です。

### CLI

```bash
python -m numbers4_agent.cli --root . audit-history
python -m numbers4_agent.cli --root . replay-history
python -m numbers4_agent.cli --root . build-dashboard

# インターネットにアクセス可能な環境のみ:
python -m numbers4_agent.cli --root . refresh-secondary
python -m numbers4_agent.cli --root . audit-references
```

## オンライン参照・自動更新

`.github/workflows/online-learning.yml` がGitHub Actionsのベストエフォートで **平日23:25 JST／翌朝10:10 JST** に走ります。GitHub Actionsの時間保証はありません。また歴史的な再現・評価は全件を毎回再計算します。

- 固定された2つのGitHub公開リポジトリ `hazimekom/numbers4-api` と `kodai721229/kujilab` の **それぞれの現在のコミットSHAを取得→固定SHAの実データを取得**。
- 回号・4桁当せん番号を全回一致させ、日時をチェック。過去1件でも変更・削除されていたら**全バッチ停止**。公開元の独立性は保証しません。
- 新回が両サイトで追加されているときだけ研究用CSVに追記。古い番号の書換えは禁止。正式銀行結果の採点台帳 `data/auto_verified_draws.jsonl` 等は一切書き換えません。
- みずほ銀行／宝くじ公式の制度・ワシントン大学の proper scoring rules 研究報告を、**読み取り専用の固定HTTPS URL** で点検し、HTTP到達性と取得ボディのSHA-256だけを `research/online_reference_audit.json` に記録。ページ内容によるモデルコード実行・実験自動採用はありません。
- 取得に失敗したら過去の最後に確認済みの研究用CSVをそのまま保存し、取得失敗を明示。データ一致に矛盾した場合は止めます。

## 安全性・予測力について

最適な「改善」を選ぶ過程にも偶然の当たりや過学習が含まれます。統計的評価では過去の当たり回数だけでなく proper scoring rules が必要です。[Gneiting & Raftery (2007), JASA](https://doi.org/10.1198/016214506000001437) は適切な確率予測の評価法を論じています。これは抽せんの予測能力を保証する論文ではありません。

- 真正な未知の結果に先立ち発行した別台帳 `data/issued_forecasts.jsonl` と、公式銀行と販売元の結果が照合できた `data/auto_verified_draws.jsonl` は別権限です。
- **事前登録済み新規Future-OOSの実測と明示承認なしにProduction昇格はしません。** この段階で「予測精度改善を実証済み」と宣言できません。
- 自動購入・売上・個人情報アクセス・外部記事のコード実行は実装しません。
- 研究用の次回候補には抽せん日を付けず、`research_only_not_issued_not_purchased` と表示します。
