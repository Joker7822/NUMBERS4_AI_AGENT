# Numbers4 第2回からの時系列予測とオンライン研究更新

**初版：2026-11-02 JST** · `numbers4-prequential-online-replay-v1` · 研究専用

## 運用対象と説明責任

ナンバーズ4は0〜9の4桁（先頭0を保持）を抽せんするため、公平な一回の抽せんで特定のストレート番号が出る理論確率は **1/10,000**、新方針の1番号のストレート一致確率は **1/10,000 = 0.01%** です。正規の結果情報と制度の説明は [みずほ銀行](https://www.mizuhobank.co.jp/takarakuji/products/numbers/index.html) / [宝くじ公式](https://www.takarakuji-official.jp/brand/suji/lineup-numbers4/) を確認してください。

**第2回以降の予測・採点は後から過去の結果を取り出して順番に再現したものであり、1994年に実際に事前発行したという意味ではありません。** 収録した全履歴は二次公開リポジトリの一致記録であり、みずほ銀行一次公表との全件照合・独立性確認は未実施です。したがって、履歴研究で一致した回を正式な事前発行成績・購入実績・利益と混同しません。

## 時系列処理の手順

1. `data/historical_results.csv` は第1回からの連続回号・厳密な日付・`0000`〜`9999`の4文字・Gitハッシュをチェックした研究用台帳です。`audit-history` は破損時に処理を停止します。
2. **第2回**を予測するときの入力は**第1回だけ**。各回で番号1口と確率分布を発行相当の順で生成し、当該回の結果を後から開いて採点した後に限り研究モデルの重みを更新します。対象回以降のデータは使用しません。
3. 4桁一様モデル（理論基準）と、直近60／250／1,000回の桁別Dirichletモデル3種を比較します。損失は確率予測のlog-score・Brier、別指標として1口ストレート一致回数です。
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


## 最新予測・過去一致・研究用収支の自動表示（2026-11-02）

`numbers4_agent/finance.py` が `data/secondary_straight_payouts.csv`（第三者公開の回別ストレート配当）と全履歴7,104回、`research/online_round_predictions.csv` を照合します。各回1口×200円とし、ストレート一致した回だけ公表配当を加算します。表示する当せん回数と配当合計はファイルハッシュ・対象回号・4桁番号・回別配当に紐づいており、データ不一致時は公開を拒否します。

`research/online_replay.json` の `retrospective_finance` と `docs/data/status.json` を公開ダッシュボードで使います。最新研究予測1口と、本当に事前発行された1口は**別欄**です。過去の一致一覧は`historical_walk_forward_reconstruction_only`であり、当時の予測を保存していたと主張するものではありません。

**本番の収支ではありません**。宝くじを購入・換金した記録がないため `actual_spend_yen`、`actual_income_yen`、`actual_profit_yen` はすべて `null`。銀行一次ソースでの全回配当検証も未実施です。仮想の的中・金額がプラスであってもモデルの予測精度向上を示しません。GitHub Actionsはベストエフォートで更新し、即時性を保証しません。


## ダッシュボードのボックス換算（2026-11-02 14時台 JSTから）

新方式で第2回から再計算したストレート1口の予測番号を**変更せず**、ボックスで購入できる番号だけを仮想購入したものとして第2回から全回を再評価します。並び順は無視し、4桁同一は申込不可として除外します（事後の代替番号は禁止）。各回最大1口のため、組合せが重なる複数購入口はありません。

`numbers4_agent/box_finance.py` は以下の照合を強制します。

- `research/online_round_predictions.csv` の事前履歴だけを使った全1口候補・当該回の当せん番号・元のストレート一致判定を再確認
- `data/secondary_box_payouts.csv` の番号・日付・回号・配当、固定Git blob SHAを検証。4桁同一の当せん回は配当が空欄であることを強制
- 的中**回数**と**口数**を別々に計上。ボックス配当は「その回の1口あたり配当×的中口数」
- 費用は「申込可能な候補総数×200円」。申込不可は費用に含めず、欠損や改変があれば全計算を停止
- 実購入費・実当せん金・実収支は `null`、本番昇格は `false`

`research/online_replay.json` の `retrospective_box_finance` と `docs/data/status.json` を公開画面に用います。従来の `retrospective_finance`（ストレート）は研究監査用に残りますが、**公開画面ではボックス換算の金額を表示**します。

出典：[みずほ銀行のナンバーズ購入ルール](https://www.mizuhobank.co.jp/takarakuji/products/numbers/index.html)、[二次公開の回別ボックス配当CSV](https://github.com/hazimekom/numbers4-api/blob/bc99c64c6ddd8e3183a257dfd36ab3fefe62212e/data/numbers4_results_v2.csv)。銀行一次の全回配当照合は未完了です。

## オンライン検索・公式ルール照合を運用監視へ組み込む（2026-11-02）

実装は `numbers4_agent/online_monitor.py`（公開元レジストリ／ルール文言チェック）、
`numbers4_agent/online_ops.py`（最新監査の鮮度・アラート判定）、
`.github/workflows/online-learning.yml`（定期実行、GitHub Issues通知、Pages更新）です。

**監視対象のオンライン情報:** 宝くじ公式の[購入方法](https://www.takarakuji-official.jp/kuji/numbers/numbers4/howto.html)と[当せん条件](https://www.takarakuji-official.jp/brand/suji/lineup-numbers4/)、[みずほ銀行の商品ルール](https://www.mizuhobank.co.jp/takarakuji/products/numbers/index.html)、[みずほ銀行の結果案内](https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html)、確率評価手法の学術ページ（参考／未査読）。承認済みURLに限定し、リダイレクト先・容量・HTML可視テキストとルール条件を検査します。

公式ルールの必須チェックは、1口200円、ナンバーズ4の区別、ストレート・ボックス、順不同の当せん条件、4桁同一のボックス不可、ストレート確率1/10,000（一部の公式ソース）です。取得できない場合は「未確認」、必須条件が消えた場合は「要手動確認」。HTMLから断定的な意味理解・変更理由の自動推測は行いません。ページのHTML取得成功＝実際の当せん番号や配当の一次確認ではありません。元の結果抽出パーサーに認証責任が残ります。

**通知:** ルール変更疑い・取得不能・96時間を超える監査遅延は、`docs/data/status.json` の `online_operations` とダッシュボードの監視欄へ反映。運用更新ワークフローは該当時、既存の未解決Issueを探して重複せず1件のGitHub Issueを作成します。GitHub Issuesの通知受信はリポジトリ側のWatch・通知設定に依存します。

**自動更新:** 二次公開元が2件完全一致した回のみ、既存履歴を書き換えず追記し、全時系列の逐次再現とストレート・ボックスの別々の仮想収支を再集計。抽せん前発行履歴・本当の購入履歴・予測モデル本体への自動変更を禁止します。オンライン監視が正常でも予測精度改善の証明にはなりません。

**スケジュール:** 平日23:25 JST、翌日10:10 JST（火～土曜日に再確認）。GitHub Actionsの定期実行には遅延・欠落・無活動による停止があり、「常時監視・即時取得」の保証はできません。

```bash
python -m numbers4_agent.cli --root . audit-references
python -m numbers4_agent.cli --root . refresh-secondary
python -m numbers4_agent.cli --root . replay-history
python -m numbers4_agent.cli --root . build-dashboard
python -m unittest discover -s tests -v
node --test tests/frontend.test.mjs
```

**公開元発見の範囲:** 現在の本番は固定した信頼できるURL群のオンライン巡回であり、Web全域の自律検索エンジンではありません。未知の情報源はレビューを経るまで自動採用しません。
