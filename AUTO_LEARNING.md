# 予測精度研究のオンライン検索・自動学習・条件付き本番昇格

2026-11-02（JST）策定、v0.11.0。実購入・自動購入は一切しません。

## 1. オンライン情報の探索と検証

- 検索元はCrossrefの論文メタデータおよびAPIキー設定時のBrave Web検索。研究対象は確率予測、無作為性、過学習検出、逐次評価、機械学習です。公式当せん番号の検索とは別です。
- 研究レポートのscientific_hypothesis_review_queueは、検索した出典・書誌情報、出典確認と研究の限界、既存モデルの過去比較を関連付けます。
- 検索結果や論文メタデータは予測優位性の証明ではありません。未知の外部コードを自動でダウンロード・実行・学習に投入しません。新しいアルゴリズムの追加にはソースレビューと試験の再登録が必要です。

## 2. 一次照合による自動学習

- GitHub Actionsのverified-autolearn.ymlを平日16:05、22:45 JSTおよび翌朝10:15 JSTに試行します。GitHubのcronは遅延し得ます。
- 学習入力は銀行＋楽天宝くじの番号・日付・回号が一致したauto_verified_draws.jsonlのみです。二次リポジトリの過去履歴は自動昇格に使いません。
- 固定候補モデルは桁別Dirichlet（直近60回/α10、250回/α5、1000回/α20）の3つと一様モデル。各回の結果を予測に先取りしません。
- 抽せん前の確率分布と各モデルの1口候補をshadow_forecasts.jsonlに固定し、GitHubコミットに公開します。実際の購入や発行済み予測とは異なります。

## 3. 客観的な事前公開証拠

- フリーズ時刻は抽せん当日18:00 JSTより前。前回の照合済み結果と承認済みの次回日付が必要です。
- ワークフローは予測コミットをpushした後、Numbers4 CIをworkflow_dispatchで明示的に起動し、GitHub側run.created_atが締切前か検証します。GitHub ActionsのGITHUB_TOKENでpushした場合、通常のpushイベントは新しいワークフローを起動しないためです。
- GitHub runのhead_shaと、Git履歴上で初めて予測SHA行が現れたコミットが一致することを確かめます。単なるローカル時刻・コミット作者時刻は根拠にしません。
- GitHubのイベント記録も電子署名ではなく、API停止やログ保持期限の制約があります。検証できなければ昇格対象外です。

## 4. 本番昇格の固定ゲート

| 条件 | 基準 |
|---|---|
| 評価する口数 | 各回ストレート1口 |
| 最低実測回数 | 500回の真正な前向き予測 |
| 結果照合 | 銀行一次結果＋販売元一致のみ |
| 公開時刻 | GitHubサーバーのイベント開始時刻が抽せん前 |
| 統計検定 | 条件付き一様・独立な1万通りの帰無に対する尤度比e-process |
| 多重検定 | 3候補、家族全体の誤検出水準0.01 |
| 数値閾値 | e-value 300以上（log-eがln(300)以上） |
| ストレート予測 | 同じ回の一様1口基準より多く的中 |
| 整合性エラー | 新規昇格停止・自動購入なし |
| 本番予測の切替対象 | production_champion.jsonのモデルポインタのみ |

e-processの尤度比は各回の予測した分布qと結果xについてq(x)/(1/10000)を積算します。独立・公平な一様抽せんの帰無と、各回の事前確率分布が正しい予測時刻に固定されている条件で、逐次検定の誤検出を制御します。モデルの恒久的な予測力、利益、当せん確実性は保証しません。

出典：[Safe Testing, JRSS B](https://academic.oup.com/jrsssb/article/86/5/1091/7623686)、[GitHub Actions workflow runs REST API](https://docs.github.com/en/rest/actions/workflow-runs)、[GITHUB_TOKENとworkflow_dispatch](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)。

## 5. 承認済み抽せん日付が必要

曜日だけでは祝日・年末年始の抽せん休止を判定できません。research/approved_draw_schedule.jsonに、公式発表で日付と対象回号を確認した対象だけ登録します。初期状態のrounds配列は空です。

登録する1件の例（以下は入力形式の説明であり、実際の抽せん日付ではありません）：

    {"round": 7200, "draw_date": "2027-03-22", "human_reviewed": true,
     "source_url": "https://www.mizuhobank.co.jp/takarakuji/products/numbers/index.html"}

その日が本当の抽せん日であることを独立に確認してから登録してください。承認日付がない場合はシャドー予測を生成しません。

## 6. 操作コマンド

    python -m numbers4_agent.cli --root . assess-challengers
    python -m numbers4_agent.cli --root . freeze-shadow --target-round CONFIRMED_ROUND --draw-date YYYY-MM-DD
    python -m numbers4_agent.cli --root . witness-shadow
    python -m numbers4_agent.cli --root . auto-promote
    python -m numbers4_agent.cli --root . recommend --method champion --target-round NEXT_ROUND

証拠と判定はresearch/prospective_auto_learning_status.json、モデルの現役ポインタはdata/production_champion.json、シャドー候補はdata/shadow_forecasts.jsonlにあります。issued_forecasts.jsonlや過去の発行済み記録は書き換えません。

2026-11-02現在：銀行自動照合0件、正式な将来予測0件、実購入0件。自動学習・昇格の機能は準備されていますが、予測優位性および現実の本番昇格は確認できません。
