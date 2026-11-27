# GT-1000CORE Tone Agent — ローカルAI音作りエディタ（試作）

GT-1000COREをUSB MIDIでPCに接続し、現在の一時パッチを読み取り、自然文から変更案を作って**人間が承認したときだけ**反映するローカルWebアプリです。

> **実機未検証のプロトタイプ**です。PC上のデモ・ユニットテストのみ実施。BOSS/Rolandの公式アプリではありません。

## 主な機能

- MIDI入力・出力ポートを明示的に選択し、ユニバーサルIdentity ReplyでGT-1000/COREを検出
- Roland RQ1/DT1 SysExで一時パッチの名前・許可された12パラメーター・5エフェクトのON/OFFを取得
- 自然文からローカルOllamaモデルで、変更幅が小さい差分を提案（Ollamaなしなら説明付きデモルール）
- 人間の確認後に**一時パッチだけ**更新し、読み戻しを検証。競合を検出したら更新を拒否
- 直前の変更をUndo（本体側の値が変わっていない場合）。値域外の変更は拒否
- デモモードで機材なしにUIを確認可能。クラウドAPIキーは不要

## すぐに試す（Windows / macOS）

Python 3.11以降が必要です。Windowsではリポジトリにある `scripts/start-windows.bat`、macOSでは `scripts/start-macos.command` を使うと、仮想環境を作成して起動できます。

macOSで `.command` の実行が拒否される場合は、ターミナルから下記のコマンドで起動してください。Windowsで `.bat` が利用できない場合も同様にターミナル操作が可能です。

リポジトリをcloneする場合：

```bash
git clone https://github.com/codetea-ping999/GT-1000CORE-Tone-Agent-MVP.git
cd GT-1000CORE-Tone-Agent-MVP
```

手動起動（展開済みプロジェクトのルートから）：

```bash
python3 -m pip install -r requirements.txt
python3 -m gtcore_agent.server
```

ブラウザで **http://127.0.0.1:8765** を開く → 「パッチを読み込む」→ 「変更案を生成」→ 差分を確認できます。

デモモードでは「確認して反映」を押しても**実機には一切送信されません**。詳細な実機検証項目は [Windows / macOS 実機検証計画](docs/PLATFORM_VERIFICATION.md) を参照してください。

## GT-1000COREの実機につなぐ

1. BOSS公式サポートから使用OS向けの **GT-1000ドライバー**を導入する。GT-1000CORE本体をUSB接続する。
2. **BOSS TONE STUDIO**で現在の設定・パッチをバックアップする。必要なら終了してMIDIポートの競合を避ける。
3. PCの出力音量、アンプの音量を低くする。演奏中・録音中には試さない。
4. 依存ライブラリをインストールする。

   ```bash
   python3 -m pip install -r requirements.txt
   python3 -m gtcore_agent.server
   ```

5. UIでGT-1000COREに対応するMIDI入力・出力ポートを両方選び「接続切り替え」。Identity Replyに失敗したら、ポート・ケーブル・ドライバー・他アプリのポート利用状況を確認する。
6. 「パッチを読み込む」→ Ollamaモデルまたはデモルールを選ぶ → 音の目標を入力 → 提案を確認 → チェックを入れて反映。
7. 音を聴いて比較する。保存が必要なら、本体のWRITE機能またはBOSS TONE STUDIOで明示的に保存する。

※ Mac/Windows両対応を意図したPythonコードですが、OS別ドライバー挙動、実機のMIDI応答、最新ファームウェアでの動作は未確認です。

## Ollama連携

インストール済みの[Ollama](https://ollama.com/)を起動し、モデルを事前にpullしてください。
ローカルの `http://127.0.0.1:11434/api/tags` を読み取り、インストール済みのモデルを画面に表示します。

```bash
ollama list
```

「Ollamaモデルを再検索」→ モデルを選択 → 「変更案を生成」。AIは候補のJSONを返すだけで、MIDIへの書き込み権限は持ちません。任意コード実行・ファイル削除・Web検索などのツールも与えていません。

## 仕様と制約

- 制御は **DIST1/2、AMP A、EQ1、Delay1** の12項目。モデル別アンプタイプ、FX系、エフェクト順序、ルーティング、音量マスター、ユーザーパッチの書き込みは対象外。
- 自然文の意味理解や音の良し悪しはAIモデルに依存します。録音入力、FFT/音量計測、音響特徴量・自動A/B比較は未実装。**本ツールは実際の音を聴いて判断していません**。
- 1回の提案は最大8項目で、パラメーター別の変更幅を制限。パッチの変更や別アプリからの書き込みが競合した場合、確実な復元はできません。常にパッチをバックアップしてください。
- BOSS TONE STUDIOを外部操作したり、非公開APIを使ったりはしません。USB MIDIポートへ直接SysExを送ります。
- 対応機種はUniversal Identity Replyのファミリーコードと、公開仕様にあるGT-1000CORE識別バイトの両方で確認します。他機種は拒否します。
- ネットワーク受信は127.0.0.1:8765だけ。Ollama通信も127.0.0.1のみ。外部公開用途には未対応。

## テスト

```bash
python3 -m unittest discover -s tests -v
```

## BOSS公式資料

- [GT-1000COREサポート・ドライバー・BOSS TONE STUDIO](https://www.boss.info/jp/support/by_product/gt-1000core/)
- [GT-1000/GT-1000CORE MIDI Implementation (2026-03-01)](https://static.roland.com/assets/media/pdf/GT-1000_GT-1000CORE_MIDI_Imple_eng12_W.pdf)

## 今後の拡張

1. 実機から読めるパラメーター全体とエフェクトチェーンの可視化
2. USB Audio/オーディオインターフェースで録音したA/B音源の音量を揃えて比較
3. 曲・アーティスト・ギターごとの音作りナレッジとパッチ履歴の保存
4. ES-5とPC/DAW連携、セットリスト別の制御
5. 自律反復は変更量・音量・回数を制限して、最終適用は手動承認
