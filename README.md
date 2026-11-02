# NUMBERS4_AI_AGENT

**Numbers4（ナンバーズ4）専用の、独立したAI研究・予測台帳・照合監査プロジェクト**。LOTO7のコード・履歴・秘密情報は引き継ぎません。

> **状態（2026-11-02、v0.3.0）:** 銀行公式結果の自動取得と別の公開元照合、歴史的ウォークフォワード実行を追加しました。取得元サイトの形式によっては結果を取れず、その場合は正式照合済みとして登録しません。発行済みNumbers4予測は未登録で、予測精度改善は実証されていません。

## 第1回からの全回当せん結果（2026-11-02取得）

- **収録：7,104回、1994-10-07（第1回）から2026-10-30（第7104回）まで、回号欠落0。**
- **[data/historical_results.csv](data/historical_results.csv)**：`round,draw_date,winning_number` の3列。先頭ゼロのある `0097` なども文字列として保存。
- **[data/historical_archive_provenance.json](data/historical_archive_provenance.json)**：GitオブジェクトSHA・取得時の2公開リポジトリの固定コミットSHA、ソースの限界、昇格禁止のフラグを記録。
- データ元：[numbers4-apiの日付付き全件CSV](https://github.com/hazimekom/numbers4-api/blob/bc99c64c6ddd8e3183a257dfd36ab3fefe62212e/data/numbers4_results_v2.csv) と [kujilabの全件番号一覧](https://github.com/kodai721229/kujilab/blob/5ec30ce16afed035d151c2e007367601d141dbab/public/data/numbers4.json)。**7,104回すべてで回号と4桁当せん番号が一致**。日付は日付付きCSVから取得し、単調増加と期間を検査。
- **注意：両公開リポジトリが同じ上流CSVを参照している可能性があり、独立した公式一次ソース2件の照合ではありません。** みずほ銀行の当せん番号との全件照合は未実施。予測の正式採点、事前発行実績の創作、Production昇格には利用不可。
- 2026-11-02の第7105回は抽せん前なので、履歴に含めません。新規抽せんについては引き続き正式な一次データ確認が必要です。

全件の整合性を読み取り専用で再検査できます。

```bash
python -m numbers4_agent.cli --root . audit-history
python -m unittest discover -s tests -v
```

ダッシュボードの「過去当せん番号の全履歴」は **二次公開データの収録件数** です。銀行＋販売元の照合済み抽せん件数や、実際に採点できた予測回数とは別の値です。

## 第2回から全件の逐次予測・オンライン研究更新（2026-11-02）

2026-11-02実装の **[ONLINE_LEARNING.md](ONLINE_LEARNING.md)** を参照してください。第1回の履歴だけを使って第2回を予測し、第2回の当せん番号を確認してからモデルの評価値を更新する操作を、収録された全7,104回にわたり順番に再現します。対象は第2〜第7104回の **7,103回** です。

- 再現した5口と照合結果： [research/online_round_predictions.csv](research/online_round_predictions.csv)
- 累積成績と研究モデル選択： [research/online_replay.json](research/online_replay.json)
- 2公開リポジトリのオンライン更新検査： [research/online_source_audit.json](research/online_source_audit.json)
- みずほ・宝くじ公式ルールおよびproper scoring rulesの定期参照： [research/online_reference_audit.json](research/online_reference_audit.json)
- 定期運用： [online-learning.yml](.github/workflows/online-learning.yml) で平日23:25 JSTと翌朝10:10 JST、ベストエフォート実行（GitHub cronの遅延あり）。

```bash
python -m numbers4_agent.cli --root . replay-history
python -m numbers4_agent.cli --root . build-dashboard
# インターネットにアクセスできる環境でのみ
python -m numbers4_agent.cli --root . refresh-secondary
python -m numbers4_agent.cli --root . audit-references
```

**誤認防止：7,103回の数字は過去に実際に事前発行した予測ではなく、厳密に過去データのみで再構成した研究です。** 自動重み更新は研究モデルに限定し、公式銀行照合済み結果・事前発行台帳・Productionモデルを書き換えません。予測改善を証明するための新規Future-OOS実測は別途必要です。オンライン公開元の独立性も保証されていません。


## ダッシュボード：ボックス購入の過去的中・仮想収支（2026-11-02）

[Numbers4ダッシュボード](https://joker7822.github.io/NUMBERS4_AI_AGENT/)の過去的中・仮想収支を**ストレートからボックスへ切り替え**ました。

- **最新の研究用5口**：第7104回までの履歴を使った元の候補5口をボックス購入と解釈して表示。ボックス専用に予測し直したものではありません。事前発行・実購入実績ではありません。
- **的中回数と口数を区別**：4桁の並び順を無視して判定。異なる順序で同じ組合せを複数口仮想購入したときは、それぞれの口が当たったものとして配当を計算。ハズレは一覧に表示しません。
- **申込不可の候補は費用から除外**：`0000`、`1111`など4桁同一は、公式ルールでボックス申込不可のため **仮想購入0口・費用0円**。事後的に代替番号を選ばず、購入不可の候補数を別表示。
- **ボックス配当は回別実績**：第1〜第7104回の`data/secondary_box_payouts.csv`を使用。4桁同一の当せん番号だった8回は配当が空欄で、購入できるボックス当せんは存在しません。`data/secondary_box_payouts_provenance.json`に固定コミット・ハッシュ・権限制約を保存。
- **仮想収支**：第2回からの逐次研究予測（1回最大5口）をそのままボックス申込とした場合の費用は「購入可能な候補総数×200円」。仮想当せん金は「当せんした仮想口数×その回のボックス当せん金」。差引収支は両者の差。
- **実購入の収支**：購入・換金証明がないため**未確認**。過去研究の照合を、実際に購入して当てた実績や真の将来予測能力の証明として扱いません。

ボックスの公的ルール・購入制限：[みずほ銀行](https://www.mizuhobank.co.jp/takarakuji/products/numbers/index.html)、[宝くじ公式](https://www.takarakuji-official.jp/brand/suji/lineup-numbers4/)。
回別配当データの公開元：[numbers4-api二次公開CSV](https://github.com/hazimekom/numbers4-api/blob/bc99c64c6ddd8e3183a257dfd36ab3fefe62212e/data/numbers4_results_v2.csv)。
当せん番号は別のGitHub公開元と全件照合していますが、**当せん金額の銀行一次ソースでの全件照合は未実施**です。

## 公式ルール

- 4桁の数字を選択。`0000`、`0012`など先頭0も意味を持つため、**数値型ではなく4文字の文字列**で保存します。
- 申込タイプ: `straight`（順序まで完全一致）、`box`（順不同）、`set`（ストレートとボックスの組合せ）。ボックス／セットでは4桁同一数字（例: `1111`）は申込不可です。
- 1口200円。原則月曜日〜金曜日に抽せん（年末年始等の例外あり）。当せん金は回ごとに変動します。
- 参考: [宝くじ公式サイト・ナンバーズ4](https://www.takarakuji-official.jp/kuji/numbers/numbers4/howto.html) / [当せん条件と確率](https://www.takarakuji-official.jp/brand/suji/lineup-numbers4/) / [みずほ銀行結果一覧](https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html)。

## 機能

- 4桁入力の厳密な型検査（先頭0を保持、数字が重複するボックス・セットは組合せ数を正しく計算）。
- **みずほ銀行公式結果＋楽天宝くじ公開結果**を同じ回号・日付・4桁で機械照合。銀行側の結果を読めない場合は `blocked_no_bank_verified_results` として、楽天側の記録は**未照合の研究用履歴**に限ります。手動2系統入力も従来どおり使用可能です。双方とも抽せん受託主体から独立した2回の抽せんではないため、「独立した公式2ソース」とは呼びません。
- 最低30回の一致履歴がある場合のみ、桁別度数＋Dirichlet平滑化を研究候補に使用。履歴未登録なら一様参考候補。いずれも**予測力は未実証**。
- 記録を追記する5口分の明示的事前発行。抽せん当日18:30 JSTを超える後付けは拒否。**実際の購入はしません**。
- 事前発行台帳と2ソース手入力一致結果に限定した採点。真正な将来検証と過去のウォークフォワード研究を分離。過去分析は各対象回より前の履歴だけで学習し、一様理論基準に対する**log-score・Brier・Top5一致数**を測定。移動ブロックbootstrap区間は探索的で、事前登録の証明ではありません。
- 読取り専用の日本語ダッシュボード、CI、定期監査、GitHub Pages用の生成ワークフロー。結果自動取得は平日22:15 JST・翌朝09:30 JSTのベストエフォートで再確認します（GitHub Actionsの遅延や取得元側の仕様変更に依存）。

## 初期設定・検証

Python 3.12以上、Node.js 22（ブラウザの純粋関数テストのみ）。外部Pythonパッケージ不要（HTML解析とHTTPSには標準ライブラリ）。

```bash
python -m unittest discover -s tests -v
node --test tests/*.test.mjs
python -m numbers4_agent.cli audit
python -m numbers4_agent.cli build-dashboard
python -m http.server 8000 --directory docs
```

`http://localhost:8000`を開くと、未登録であることを明示したダッシュボードを表示します。

## 公式結果の自動取得と予測精度の検証（2026-11-02実装）

```bash
# 銀行公式結果と第二公開元を月ごとに取得し、完全一致した回だけ追記記録
python -m numbers4_agent.cli --root . fetch-official --months-back 12

# 過去時点以前の情報だけで各回の予測を生成して時系列評価。
# 未照合の楽天単独データは研究用のみ。本番予測の採点には使用しない。
python -m numbers4_agent.cli --root . prove --output research/historical_backtest.json

# 表示は計測値と「将来予測能力未実証」を別にする。
python -m numbers4_agent.cli --root . build-dashboard --output docs/data/status.json
```

`fetch-official` は `https://www.mizuhobank.co.jp` の **Numbers4結果**と
`https://takarakuji.rakuten.co.jp` の月別結果のみへHTTPSでアクセスし、
ページURL、応答SHA-256、確認時刻を保存します。発行予測を書き換えません。
**みずほ銀行の現行ページはJavaScript依存で結果が空のことがあり、その回は正式照合と認めません。**
その場合でも楽天履歴で探索的なwalk-forwardは実施できますが、信頼性・事前登録・予測力の確認にはなりません。
研究報告は `research/historical_backtest.json`、自動照合済み結果は
`data/auto_verified_draws.jsonl` にそれぞれ分離します。

指標は、事前に過去データから得た桁別Dirichlet確率と一様4桁基準の対数スコア差、
Brier差、5口ストレート一致回数、探索的移動ブロックbootstrap 95%区間です。
**勝ちを検証するための未知の事前発行・外部評価記録がないので、
`prediction_skill_confirmed` は必ず `false` です。** 数字が良くても自動昇格しません。

## 運用例（**実データが発表・照合できてから**）

次のコマンドの番号・回号・日付・URLは**書式説明用の架空値**です。真正な過去の結果であると解釈しないでください。

```bash
# 回号・抽せん日・4桁の公式結果を実際に確認して別々に登録する。
python -m numbers4_agent.cli observe --round 9999 --draw-date 2026-11-02 --number 0007 \
  --source mizuhobank --url https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html
python -m numbers4_agent.cli observe --round 9999 --draw-date 2026-11-02 --number 0007 \
  --source takarakuji_official --url https://www.takarakuji-official.jp/kuji/numbers/numbers4/howto.html

# 次回分の研究候補。未発行で購入を伴いません。
python -m numbers4_agent.cli recommend --target-round 10000 --mode straight --count 5

# 発行例。期日が過ぎた場合は必ずエラーになります。
python -m numbers4_agent.cli issue --target-round 10000 --draw-date 2026-11-03 \
  --deadline-jst 2026-11-03T18:30:00+09:00 --mode straight \
  --numbers 0007 0012 1234 5678 9012 \
  --model-version uniform-deterministic-reference-v1 --ack-advice-only

python -m numbers4_agent.cli evaluate
python -m numbers4_agent.cli backtest
python -m numbers4_agent.cli build-dashboard
```

**注意:** 書式例は未来の回号／実際の抽せんスケジュールを主張していません。公開ページのURLは、その回の当せん番号を本当に示しているか人間が確認してください。2サイトの手動一致だけで公式発表の自動検証済みと主張しないでください。

## GitHubの新規リポジトリ登録

1. [GitHubの新規作成画面](https://github.com/new)で `NUMBERS4_AI_AGENT` を作成してください。**READMEやライセンスの自動初期化をせず、空のリポジトリ**として作成します。最初は非公開が安全です。
2. ZIPを展開し、ファイル一式のあるフォルダーへ移動します。
3. 次を実行するとローカルの独立Git履歴を新リポジトリに送れます。

```bash
git remote add origin https://github.com/YOUR_ACCOUNT/NUMBERS4_AI_AGENT.git
git push -u origin main
```

ローカルリポジトリは最初のコミット済みです。GitHub Pagesを使う場合はリポジトリの **Settings → Pages → Build and deployment → Source: GitHub Actions** を設定してください。Pagesの動作は実際にGitHubへ登録してから確認が必要です。

## 技術仕様と注意点

[設計・権限分離](ARCHITECTURE.md) / [セキュリティと限界](SECURITY.md)

既存LOTO7の49ワークフローや学習済みモデルをそのままNumbers4へ移植したものではありません。**事故や旧認証情報の再流入を防ぐため、Numbers4専用に組み直した独立版 v0.2.0**です。公式結果の自動取得機能は実装済みですが、配信元の取得可能性に依存します。実際の購入、予測精度の優位性の事前登録済み証明は未実装・未確認です。
