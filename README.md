# NUMBERS4_AI_AGENT

**Numbers4（ナンバーズ4）専用の、独立したAI研究・予測台帳・照合監査プロジェクト**。LOTO7のコード・履歴・秘密情報は引き継ぎません。

> **状態（2026-11-02、v0.11.0）:** 銀行公式結果の自動取得と別の公開元照合、歴史的ウォークフォワード実行を追加しました。取得元サイトの形式によっては結果を取れず、その場合は正式照合済みとして登録しません。発行済みNumbers4予測は未登録で、予測精度改善は実証されていません。

## オンライン研究情報の総取得件数の固定上限撤廃（2026-11-02、v0.11.0）

**累積件数は無制限（アプリ固有の総件数上限なし）**です。従来の「検索語最大8件／1検索で5件／公開Webリスト最大50件」の制限を撤廃しました。ただし、**一度の実行・一度のHTTP応答は有限**とし、APIサービスの実際の制限と利用規約、プライバシー対策、計算時間・予算を無視するものではありません。

| 対象 | 現行の仕組み | 継続方法 |
|---|---|---|
| 研究検索語 | 入力可能な検索語の総数にプログラム独自の8件上限なし | 同じ調査テーマでも異なる検索語を追加可能。各検索語は250文字以内。 |
| Crossref | 20件/リクエストからページ分割（Crossrefの最大offsetは10,000） | `research/discovery_progress.json`に取得位置を保存し、次の実行で継続。検索が尽きた後は別日に再巡回。 |
| Brave Web Search | APIキーが設定されている場合に20件/ページ、最大offset=9の提供元仕様を守る | 検索語別に取得位置を保存。次の日は新しい更新を再探索。キーがなければBrave取得なし。 |
| 累積研究情報 | `research/discovery_sources.jsonl` に出典ID・URL・学習候補とSHA-256監査履歴を追加 | 重複した出典は新規保存しない。**通算の保管件数の上限なし**。 |
| 公開Web URLの手動指定 | `research-web --url-file` にURL数の固定50件上限なし | 1回25件など `--batch-size` で分割し、返ってきた `next_start_index` を次回の `--start-index` に渡して再開。 |

研究の自動循環は1回あたり**標準8件のAPIリクエスト**（設定変更は1〜100件）を処理し、日々の実行で累積します。データ量が膨大な場合はGitHub Actionsの実行時間・保存容量・外部サービスの料金や利用枠が制約になります。**文字どおりの無限通信やレート制限回避はできません。**

    # 毎世代8件の研究API取得＋第2回から全回を再計算
    python -m numbers4_agent.cli --root . evolve-research
    # 1世代の予算を100リクエストに変更。検索語の件数上限はなし
    python -m numbers4_agent.cli --root . evolve-research --search-requests 100
    # 多数の公開URLを1つのファイルに列挙し、任意の位置から25件ずつ読む
    python -m numbers4_agent.cli --root . research-web --url-file research_urls.txt --start-index 0 --batch-size 25

取得した情報は科学的仮説の素材にすぎません。新情報を見つけるたびに研究AIが第2回から全回を再計算しますが、**過去データでの改善は真正な将来予測力の証明になりません**。正式な本番昇格条件や購入禁止は変更しません。

公式API文書：[Crossref REST APIのページ分割](https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/)、[Brave Searchのページ分割と取得可能数](https://api-dashboard.search.brave.com/app/documentation/web-search)、[Braveのレート制限](https://api-dashboard.search.brave.com/documentation/guides/rate-limiting)。
## 論文・公開Webのオンライン検索 → 研究AI自己進化 → 第2回から全回を再予測（2026-11-02、v0.11.0）

研究AIは毎世代、公開論文やWebから予測手法を発見し、安全な手法の候補生成・全履歴再予測・結果による次世代の研究方針更新を繰り返します。実際の当せん予測力や本番モデル昇格を意味しません。

| 工程 | 実装された自動処理 | 安全性・解釈 |
|---|---|---|
| 1. 情報発見 | Crossref論文メタデータ、設定済みBrave Web Searchで研究手法を探索 | 出典・検索日時・URLを保持。本文の科学的妥当性は別途確認が必要 |
| 2. 候補生成 | ローリング桁別Dirichlet、指数減衰付き学習、1段階桁別マルコフの安全なPythonモデルからパラメータを自動提案 | 外部論文のコードを無審査で実行しない。未知の手法は実装済みと偽らない |
| 3. 第2回から学習 | 第1回の結果だけから第2回を予測し、その回の実結果を見た後で重みを更新 | 各回の予測では当該回・未来回の当せん番号を使わない |
| 4. 全履歴再計算 | 新世代ごとに全回のストレート1口、平均log-score・Brier差、旧1口リプレイと仮想収支を再計算 | 第5001回以降を何度も使うため独立した未知のテストにはならない |
| 5. 次世代へフィードバック | 第2〜5000回の開発区間の評価からパラメータを変化させ、次の検索語を変更 | 過去履歴を参考に改良するだけで、予測優位性の証拠とはしない |
| 6. 運用記録 | 世代番号・モデル設定・出典・回別CSVハッシュを改ざん検知付きジャーナルへ追記 | 公式結果・事前発行・真正な本番昇格台帳を変更しない |

使い方：

    # オンライン検索 → 研究モデル更新 → 第2回からの全回再予測
    python -m numbers4_agent.cli --root . evolve-research
    # CI用：検索なしで同じ全再計算を検査
    python -m numbers4_agent.cli --root . evolve-research --offline
    # 興味のある手法をオンライン検索して新研究世代を生成
    python -m numbers4_agent.cli --root . evolve-research --query "Markov transition lottery prediction"

運用：[予測研究・自己進化ワークフロー](.github/workflows/predictive-research.yml)を平日11:15 JSTに実行し、[過去データ更新](.github/workflows/online-learning.yml)が成功した際にも再実行します。GitHubの定期実行は遅延する場合があります。結果は研究用の `research/evolution_report.json`、全回CSV `research/evolution_round_predictions.csv`、世代ジャーナル `research/evolution_journal.jsonl` に保存し、[ダッシュボード](https://joker7822.github.io/NUMBERS4_AI_AGENT/)にも表示します。

**注意：** 検索で発見した手法を再実験できるようになることと、当せん確率が本当に改善したことは別です。同じ履歴を使って自己改良を繰り返すと選択バイアスが大きくなります。論文のメタデータは研究仮説のヒントであって、科学的な再現検証や予測能力の証明ではありません。正式な本番昇格には別の事前公開・一次結果による将来検証が必要です。

方法論の参考：[Model Assessment and Selection under Temporal Distribution Shift (ICML 2024)](https://proceedings.mlr.press/v235/han24b.html)、[Valid sequential inference on probability forecast performance (Biometrika)](https://doi.org/10.1093/biomet/asab047)。論文内容をそのまま再実装したとの主張ではありません。
## 予測精度のための自動学習と条件付き本番昇格（2026-11-02、v0.11.0）

オンライン検索ではCrossrefおよび設定済みBrave Searchから、予測モデル・確率校正・過学習検出の研究情報を収集し、出典と方法論を検証候補に登録します。外部検索の本文やコードを直接本番AIに取り込みません。

- 一次照合済みの過去Numbers4結果だけで3つの固定桁別Dirichlet研究モデルを逐次再学習し、各回ストレート1口の予測と確率分布を抽せん前に固定します。
- GitHubサーバーのCI実行時刻で、予測が締切前に公開されていたことを照合します。GitHubが証明できない履歴は昇格判定から除外します。
- 500回以上の真正な将来予測について、固定した3候補に対する家族内0.01のe-process逐次検定（e-value 300以上）と、一様1口予測より多い的中回数を同時に満たした場合のみ、モデルの本番ポインタを自動変更します。
- 実測不足や、出典不一致・未公開・履歴欠落の場合は**自動昇格しません**。通常は一様基準モデルが有効です。購入・事前発行の自動化は行いません。
- 運用ワークフローは平日16:05/22:45 JSTと翌10:15 JSTに試行します。祝日判定のため [承認済み日付一覧](research/approved_draw_schedule.json) が必要です。現状は未登録なので将来予測の自動凍結は停止しています。

実装条件・制約・操作方法は **[AUTO_LEARNING.md](AUTO_LEARNING.md)** を参照してください。現時点で銀行の自動照合は0件、正式な将来予測の事前発行0件、予測優位性未確認です。検索・学習・昇格の機能追加を、予測精度が向上した事実と混同しないでください。
## 1口予測への移行と第2回からの再計算（2026-11-02）

**新方針：抽せん1回につき予測1番号、仮想購入はストレート最大1口、ボックス最大1口。** 自動購入ではありません。公開された5口研究から単純に当せん候補を事後抽出するのではなく、**第1回の結果だけを入力に第2回を予測**して、以後の7,103回についてモデル選択・候補・評価を時系列順にすべて再計算します。

- ストレート：1回200円×7,103回＝仮想費用1,420,600円。理論一致率は1/10,000（0.01%）。
- ボックス：同じ1番号を順序不問で再評価。1111など4桁同一のBOX申込不可の回は**仮想購入0口・費用0円**とし、結果を見て番号を交換しません。ストレート・ボックスを同時に購入した仮定ではありません。
- 予測履歴の1行には1番号と、その回より前の最終利用回号を保存。出典は銀行全件照合済みではないため、**あくまで探索的な過去再現**です。実購入記録・本番採点・将来予測力の実証ではありません。
- [旧5口サマリーの固定保存](research/legacy_five_ticket_summary.json) と [旧5口回別CSV（変更前のコミット）](https://github.com/Joker7822/NUMBERS4_AI_AGENT/blob/18ed3196e2b388c19d87a5c76f9b6494013b3e54/research/online_round_predictions.csv) は後から比較できるよう保持します。旧5口の成績・収支を新1口の数値と合算しません。
- 新規の事前発行は1口固定。**旧5口の事前発行台帳が存在しても改変せず**、旧スキーマとして読み取りのみ継続します。

```bash
python -m numbers4_agent.cli --root . replay-history
python -m numbers4_agent.cli --root . benchmark-straight
python -m numbers4_agent.cli --root . build-dashboard
```

## 予測精度向上のためのオンライン研究検索・実験運用（2026-11-02）

公式結果の監視とは別に、科学文献・公開Webから**予測手法、確率校正、無作為性検定、過学習検出、逐次評価**を探します。Crossrefの論文メタデータ検索はAPIキー不要、BRAVE_SEARCH_API_KEYを設定した場合に限りBrave検索で公開Webも調べます。**検索情報は仮説候補であり、検索だけでは精度向上が確認されたことになりません。**

```bash
# 論文検索と、既存の1口ストレートモデルの過去比較
python -m numbers4_agent.cli --root . research-cycle
# 追加の具体的な探索キーワードを指定
python -m numbers4_agent.cli --root . research-cycle \
  --query "lottery machine learning out of sample validation"
```

運用： [予測手法の研究検索ワークフロー](.github/workflows/predictive-research.yml) を平日11:15 JSTにベストエフォートで実行し、検索候補と比較結果を30日保存のJSONアーティファクトにします。予測に有利そうな論文が見つかっても外部コード・学習済みモデルを自動実行・投入せず、実装候補は必ず方法・出典をレビューします。**真正な前向きFuture-OOSの優位性が確認できるまで本番予測モデルの自動昇格を禁止**します。

## 任意の公開Web情報取得（2026-11-02追加、v0.11.0）

既存の固定5ページは**公式ルール監視用の承認済み参照先**として維持したまま、研究担当者が指定した任意の**公開HTTPS URL**を閲覧する独立コマンドを追加しました。新しい情報源を監視用の固定リストに登録する必要はありません。**情報源の種類・ドメイン数に固定の上限は設けません**が、各実行の通信は有限です。

```bash
# 任意の公開Webページを読み取り専用で取得
python -m numbers4_agent.cli --root . research-web \
  --url https://www.mizuhobank.co.jp/takarakuji/products/numbers/index.html \
  --url https://www.takarakuji-official.jp/brand/suji/lineup-numbers4/

# 多数のページを指定する場合：1行1URLのUTF-8ファイル
python -m numbers4_agent.cli --root . research-web --url-file /tmp/research-urls.txt

# 標準出力の監査JSONを別ファイルに保存（既存台帳の変更なし）
python -m numbers4_agent.cli --root . research-web \
  --url https://www.mizuhobank.co.jp/takarakuji/products/numbers/index.html \
  > /tmp/numbers4-public-research.json
```

GitHub上で手動実行する場合は [Actions → Numbers4 Opt-in Public Web Research](https://github.com/Joker7822/NUMBERS4_AI_AGENT/actions/workflows/public-web-research.yml) の「Run workflow」を選び、公開HTTPS URLを1行ずつ入力してください。実行結果は7日間保存される **`numbers4-untrusted-public-web-research`** のJSONアーティファクトとして確認できます。公式ソースとの照合は行いません。

- **通算URL件数の固定上限は撤廃**。1回の処理は初期値25件（`--batch-size`で調整）とし、`next_start_index`から次回再開します。各URL最大**4MB**、接続タイムアウト**10秒**、リダイレクト拒否。**無制限トラフィック・レート制限回避・無限クロールには非対応**です。
- HTTPS・公開DNSのみに接続し、DNSがローカル/プライベートIPを返したら拒否。名前解決済みの公開IPに接続先を固定し、元ホスト名でTLS証明書を検証します。IP直指定・認証URL・リダイレクト・スクリプト実行は禁止します。
- 返却するJSONにはURL（クエリ部分を除く）、取得時刻、本文SHA-256、サイズ、HTMLから抽出した先頭テキスト、失敗理由の種類を記録します。**取得元の本文は未検証の外部情報**です。誤情報・サイト停止・著作権・robots.txt・利用規約に注意してください。
- **自動収集スケジューラではありません**。担当者の指定したURLに対して明示的に実行します。既存の公式銀行結果の照合、発行済み予測台帳、モデル学習、Production自動昇格を変更しません。外部ページの内容を「モデルへの指示」として実行しません。

## ストレート予測の比較研究（2026-11-02追加、v0.11.0）

過去7,104回について、独立一様1口（固定した決定的シード）と、ローリング窓の桁別Dirichletモデル（60・250・1,000回）、過去250回のスコアのみで採用を判断する保守的な研究用モデルを比較します。履歴を**対象回の予測・採点後にのみ**更新するため、同じ回の結果を学習に混ぜません。窓ごとの桁別出現数は逐次更新し、毎回の全履歴再集計を避けています。

```bash
python -m numbers4_agent.cli --root . benchmark-straight --split-round 5000
python -m unittest discover -s tests -v
```

- 開発区間：第2〜第5000回。比較用時系列後半：第5001回〜最新収録回。各方式の1口ストレート一致、確率予測のlog-score・Brier差、対応のある差の探索的検定、偶然の一致確率をまとめます。
- **重要：** この研究モデル群と5000回の分割点は既知の過去履歴に接した後で選んでいるため、後半区間も未観測の独立Future-OOSではありません。優位性の「実証」や本番モデルの昇格は許可しません。多重検定・後付けモデル選択のリスクが残ります。
- 報告書：`research/straight_challenger_report.json`（CLIで生成）。CIの`straight-research-python-*`アーティファクトからも研究結果を取得できます。データは第三者の公開履歴であり、みずほ銀行による全件一次確認ではありません。
- 目的は**根拠なく複雑化せず、ランダム基準を超えたかを同じ回で比較し、改善がなければ一様モデルを保持すること**です。「AI」という名称だけで予測精度は向上しません。将来の正式評価基準は [PROSPECTIVE_PROTOCOL.md](PROSPECTIVE_PROTOCOL.md) を参照してください。

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

- 再現した1口と照合結果： [research/online_round_predictions.csv](research/online_round_predictions.csv)
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

**評価上の追加監査（2026-11-02）：** `research/online_replay.json` の `research_statistical_audit` に、独立・公平な抽せんでの1口ストレート的中回数の二項分布による右裾確率、統計モデルが採用された回数、一様1口基準と異なる的中回数を記載します。いずれも**探索的な過去研究の記述統計**であり、有意差や将来の予測力を実証するものではありません。新しい本番運用の条件と未解決事項は [将来予測の検証・公開品質ゲート](PROSPECTIVE_PROTOCOL.md) を参照してください。

**誤認防止：7,103回の数字は過去に実際に事前発行した予測ではなく、厳密に過去データのみで再構成した研究です。** 自動重み更新は研究モデルに限定し、公式銀行照合済み結果・事前発行台帳・Productionモデルを書き換えません。予測改善を証明するための新規Future-OOS実測は別途必要です。オンライン公開元の独立性も保証されていません。


## ダッシュボード：ボックス購入の過去的中・仮想収支（2026-11-02）

[Numbers4ダッシュボード](https://joker7822.github.io/NUMBERS4_AI_AGENT/)の過去的中・仮想収支を**ストレートからボックスへ切り替え**ました。

- **最新の研究用1口**：第7104回までの履歴を使った元の候補1口をボックス購入と解釈して表示。ボックス専用に予測し直したものではありません。事前発行・実購入実績ではありません。
- **的中回数と口数を区別**：4桁の並び順を無視して判定。1回につき最大1口を仮想購入し、一致した場合だけ配当を計算。ハズレは一覧に表示しません。
- **申込不可の候補は費用から除外**：`0000`、`1111`など4桁同一は、公式ルールでボックス申込不可のため **仮想購入0口・費用0円**。事後的に代替番号を選ばず、購入不可の候補数を別表示。
- **ボックス配当は回別実績**：第1〜第7104回の`data/secondary_box_payouts.csv`を使用。4桁同一の当せん番号だった8回は配当が空欄で、購入できるボックス当せんは存在しません。`data/secondary_box_payouts_provenance.json`に固定コミット・ハッシュ・権限制約を保存。
- **仮想収支**：第2回からの逐次研究予測（1回最大1口）をそのままボックス申込とした場合の費用は「購入可能な候補総数×200円」。仮想当せん金は「当せんした仮想口数×その回のボックス当せん金」。差引収支は両者の差。
- **実購入の収支**：購入・換金証明がないため**未確認**。過去研究の照合を、実際に購入して当てた実績や真の将来予測能力の証明として扱いません。

ボックスの公的ルール・購入制限：[みずほ銀行](https://www.mizuhobank.co.jp/takarakuji/products/numbers/index.html)、[宝くじ公式](https://www.takarakuji-official.jp/brand/suji/lineup-numbers4/)。
回別配当データの公開元：[numbers4-api二次公開CSV](https://github.com/hazimekom/numbers4-api/blob/bc99c64c6ddd8e3183a257dfd36ab3fefe62212e/data/numbers4_results_v2.csv)。
当せん番号は別のGitHub公開元と全件照合していますが、**当せん金額の銀行一次ソースでの全件照合は未実施**です。

## ダッシュボード：ストレート／ボックスの両方を別々に表示（2026-11-02）

[公開ダッシュボード](https://joker7822.github.io/NUMBERS4_AI_AGENT/)では、**同じ逐次研究候補1口**を用いて、ストレート・ボックスそれぞれの反実仮想シミュレーションを**独立した2組の収支表と当せん一覧**に表示します。

- **ストレート：** 順序まで完全一致した回だけを記録。第2回からの各回1口を購入したという仮定で、全口数×200円の費用、当該回のストレート配当、仮想損益を計算。
- **ボックス：** 順不同の4桁組合せ一致を記録。各回1番号のみをボックスとして仮想購入。4桁全同一の候補は購入できないので費用にも計上せず、後付けの代替番号は選びません。ボックス配当が空欄の抽せん（全同一）は当せん金0円ではなく **購入不可・配当対象外** と記録。
- それぞれ **的中回数（回数）・的中口数（ボックス）・当せん番号・候補番号・回別当せん金・仮想費用・仮想当せん金合計・差引・収益率** を表示。両方式を同時に買ったのではなく、**選択肢ごとの別シナリオ**です。
- 配当根拠：[ストレート回別配当](data/secondary_straight_payouts.csv)・[ボックス回別配当](data/secondary_box_payouts.csv)。両方とも第三者の公開データに基づき、みずほ銀行の全回配当と一次照合したものではありません。
- **当時の予測の事前発行、実際の購入、換金、モデル優位性は確認できません。** 実購入損益は2方式とも「未確認」です。本番の発行済み・照合済み件数とも分離しています。

## 本番のオンライン検索・検証・運用監視（2026-11-02）

[公開ダッシュボード](https://joker7822.github.io/NUMBERS4_AI_AGENT/)の「ONLINE SOURCES / PRODUCTION MONITORING」欄に監視状態、公式ルール3公開元の条件一致数、公開データ巡回結果、最終チェック日時を表示します。

- 信頼できる5つの承認済みWebページ（宝くじ公式2、みずほ銀行2、統計研究1）を対象に、公式ルールの必須文言の有無を自動チェック。銀行の当せん案内ページは**閲覧可能でも番号の取得・真正性の検証に成功したとはみなさない**。
- 異常（ルール変更の疑い／主要取得元ダウン／監査96時間超の遅延）は状態へ反映し、GitHub Issueを重複防止付きで作成。GitHub Actionsは平日23:25 JST・翌朝10:10 JSTのベストエフォート監査を実行。
- 二次公開履歴が一致した回のみ研究データに追記し、過去の予測の再現とストレート／ボックス別の仮想収支を更新。公式銀行の一元照合・事前発行の正式採点・自動購入・学習モデルの自動昇格は実施しません。
- Web全域からの自律検索・ソースの無審査追加ではなく、[承認済みURLレジストリと運用監査](ONLINE_LEARNING.md)です。予測能力の改善が実証されたという意味ではありません。

## 公式ルール

- 4桁の数字を選択。`0000`、`0012`など先頭0も意味を持つため、**数値型ではなく4文字の文字列**で保存します。
- 申込タイプ: `straight`（順序まで完全一致）、`box`（順不同）、`set`（ストレートとボックスの組合せ）。ボックス／セットでは4桁同一数字（例: `1111`）は申込不可です。
- 1口200円。原則月曜日〜金曜日に抽せん（年末年始等の例外あり）。当せん金は回ごとに変動します。
- 参考: [宝くじ公式サイト・ナンバーズ4](https://www.takarakuji-official.jp/kuji/numbers/numbers4/howto.html) / [当せん条件と確率](https://www.takarakuji-official.jp/brand/suji/lineup-numbers4/) / [みずほ銀行結果一覧](https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html)。

## 機能

- 4桁入力の厳密な型検査（先頭0を保持、数字が重複するボックス・セットは組合せ数を正しく計算）。
- **みずほ銀行公式結果＋楽天宝くじ公開結果**を同じ回号・日付・4桁で機械照合。銀行側の結果を読めない場合は `blocked_no_bank_verified_results` として、楽天側の記録は**未照合の研究用履歴**に限ります。手動2系統入力も従来どおり使用可能です。双方とも抽せん受託主体から独立した2回の抽せんではないため、「独立した公式2ソース」とは呼びません。
- 最低30回の一致履歴がある場合のみ、桁別度数＋Dirichlet平滑化を研究候補に使用。履歴未登録なら一様参考候補。いずれも**予測力は未実証**。
- 記録を追記する1口分の明示的事前発行。抽せん当日18:30 JSTを超える後付けは拒否。**実際の購入はしません**。
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
Brier差、1口ストレート一致回数、探索的移動ブロックbootstrap 95%区間です。
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

**公開ライセンス：** 2026-11-02現在、LICENSEファイル未追加です。著作権者がライセンス条件を選択するまでは無断でMIT等を設定しません。バージョンv0.11.0はソース上の統一表記であり、タグ付きGitHub Releaseの存在を意味しません。

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

既存LOTO7の49ワークフローや学習済みモデルをそのままNumbers4へ移植したものではありません。**事故や旧認証情報の再流入を防ぐため、Numbers4専用に組み直した独立版 v0.11.0**です。公式結果の自動取得機能は実装済みですが、配信元の取得可能性に依存します。実際の購入、予測精度の優位性の事前登録済み証明は未実装・未確認です。
