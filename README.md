# NUMBERS4_AI_AGENT

**Numbers4（ナンバーズ4）専用の、独立したAI研究・予測台帳・照合監査プロジェクト**。LOTO7のコード・履歴・秘密情報は引き継ぎません。

> **状態（2026-11-02）:** Numbers4実抽せんの観測データ・発行済み予測は**未登録**。GitHub Pagesも未設定です。既存のLOTO7実績をNumbers4へ転用したり、Numbers4の勝率改善を宣言したりしません。

## 公式ルール

- 4桁の数字を選択。`0000`、`0012`など先頭0も意味を持つため、**数値型ではなく4文字の文字列**で保存します。
- 申込タイプ: `straight`（順序まで完全一致）、`box`（順不同）、`set`（ストレートとボックスの組合せ）。ボックス／セットでは4桁同一数字（例: `1111`）は申込不可です。
- 1口200円。原則月曜日〜金曜日に抽せん（年末年始等の例外あり）。当せん金は回ごとに変動します。
- 参考: [宝くじ公式サイト・ナンバーズ4](https://www.takarakuji-official.jp/kuji/numbers/numbers4/howto.html) / [当せん条件と確率](https://www.takarakuji-official.jp/brand/suji/lineup-numbers4/) / [みずほ銀行結果一覧](https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html)。

## 機能

- 4桁入力の厳密な型検査（先頭0を保持、数字が重複するボックス・セットは組合せ数を正しく計算）。
- 2系統の公式情報を**人間が別々に確認し入力**する証拠台帳。互いに一致した回だけを研究・採点へ利用。自動的なスクレイピングや真正性の独立確認は**未実装**。
- 最低30回の一致履歴がある場合のみ、桁別度数＋Dirichlet平滑化を研究候補に使用。履歴未登録なら一様参考候補。いずれも**予測力は未実証**。
- 記録を追記する5口分の明示的事前発行。抽せん当日18:30 JSTを超える後付けは拒否。**実際の購入はしません**。
- 事前発行台帳と2ソース手入力一致結果に限定した採点。真正な将来検証と過去のウォークフォワード研究を分離。
- 読取り専用の日本語ダッシュボード、CI、定期監査、GitHub Pages用の生成ワークフロー。

## 初期設定・検証

Python 3.12以上、Node.js 22（ブラウザの純粋関数テストのみ）。外部Pythonパッケージ不要。

```bash
python -m unittest discover -s tests -v
node --test tests/*.test.mjs
python -m numbers4_agent.cli audit
python -m numbers4_agent.cli build-dashboard
python -m http.server 8000 --directory docs
```

`http://localhost:8000`を開くと、未登録であることを明示したダッシュボードを表示します。

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

既存LOTO7の49ワークフローや学習済みモデルをそのままNumbers4へ移植したものではありません。**事故や旧認証情報の再流入を防ぐため、Numbers4専用に組み直した独立版 v0.1.0**です。公式当せん番号の自動取得、実際の購入、予測精度の優位性の事前登録済み証明は今後の個別開発対象です。
