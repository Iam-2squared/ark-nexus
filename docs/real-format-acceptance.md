# 実形式Adapterの安全な受入れ手順

確認日: 2026-10-11。Consumer ChatGPT / Consumer Claudeの承認済み匿名化実サンプルは未提供。両Adapterは **BLOCKED / disabled**。この文書とcontractテストは実形式対応の証拠ではない。

## 公式資料で確認できた範囲

| Provider / Product | 公開資料から確認した取得手段 | 未確認・制限 | Nexus状態 |
|---|---|---|---|
| OpenAI / Consumer ChatGPT | 設定またはPrivacy PortalでZIP export。チャット・アカウント情報を含む [1] | 完全なバージョン付きmessage schemaなし。Business/Enterprise等のself-service export制限。Workとは別製品 | synthetic-v1のみ。実形式BLOCKED |
| Anthropic / Consumer Claude | Web/desktopのexport。組織ではPrimary Ownerの条件 [2] | 完全なmessage schemaなし。添付、分岐、編集、部分exportの意味は未検証 | synthetic-v1のみ。実形式BLOCKED |
| OpenAI / ChatGPT Work | 公式UIにタスク・結果 [3] | 外部からの履歴取得・イベント監視・投入・再開contractを未確認 | 未接続、実行無効 |
| OpenAI / Codex Local | App Serverのthread/turn読取・通知・作成・再開 [4] | 承認したlocal session scopeが必要。Nexusで同期遅延未測定 | contractのみ |
| OpenAI / Codex Cloud | CLIのcloud listによるタスクmetadata/status、cloud exec [5] | metadataは全会話本文ではない。イベント監視・既存task再開を未確認 | contractのみ |
| Anthropic / Claude Code | SDK session一覧・message読取、接続したrunのstream-json、resume [6][7] | local snapshotとattached eventは別。推論には別の認証・利用承認が必要 | contractのみ |

取得手段の公開は、このユーザーのアカウント接続の許可ではない。Consumerのexportと実行型AIの操作は別Capability。詳細は[Capability Matrix](capability-matrix.md)。公式export案内から架空のJSON構造を補完しない。

## 最小入力と匿名化

1. 所有者が対象Product・export日・公開資料での対象plan/workspaceを確認する。**raw exportをWork、GitHub、Issue、PR、CI、外部AIへ送らない**。ローカル私的環境で開くための承認と、最終の匿名化サンプルを共有するための承認を区別する。
2. 原本を維持し、別の私的な新規作業コピーで構造を確認する。ファイル名、ZIP内の名前、JSONのキーにも個人情報が入り得る。値だけの置換では安全と判定しない。zip展開をNexusに委ねず、不明なコード・リンク・添付を実行しない。
3. 最小会話1つを選ぶ。rootの実際の型、必要なcollection/graph構造、field型、null/emptyの意味を維持する。ChatGPTのmapping等の形やClaudeのフィールド名を、未確認の時点で指定しない。実際のサンプルから確かめる。
4. 本文・タイトル・参加者・アカウント・メール・電話・URL・ファイル・tool結果・秘密・hidden metadataを固定の合成内容へ置換する。日本語の例は「匿名化した合成本文」。独自のdynamic keyもレビューする。画像、音声、添付、binary/base64は除去し、未検証の範囲として記録する。
5. IDは元の型・形式を維持する匿名IDへ一貫して置換する。IDをキーに持つobject、親子参照、thread/message参照も同じ対応表で置換する。対応表は共有しない。曖昧なIDの生成や壊れたgraphの修復を推測でしない。複数元IDが同じ匿名IDになっていないか確認する。
6. 時刻は実際の型・timezone・精度を維持して一貫してずらす。順序・等時刻・nullの区別を保つ。単に全値を同時刻に置換してrevisionや順序の検証を失わない。文字列から数値へ変換しない。
7. 2人目のレビュー、または所有者自身の別のレビューで、全キー・値・ZIP名・添付・URL・トークン様文字列を確認する。正規表現のsecret scanだけで安全保証しない。サンプル全文をログへ出す検査を使わない。安全な構造維持が難しければ、そのサンプルは提出せずBLOCKEDを維持する。
8. 最終サンプルはprivateかつGit対象外に保持する。共有前に「この最小サンプルは匿名化・機密除去済みで、このNexus適合検証に使用してよい」という明示承認を付ける。raw export、SQLite DB、key、Cookieは提出対象外。

最初の協力事項は **各Providerの最小の匿名化会話サンプル1つ、Product/export日、匿名化範囲、使用承認**。分岐・編集・tool等を含む追加サンプルがなければ、そのCapabilityは引き続き未検証にする。最小サンプル1つだけでV1全GateをPASSにしない。

schema確認の共有用メモには、レビュー済みの構造キー、型、cardinality、参照関係、parser case IDだけを含める。未知のキーや値を自動で全部書き出さない。元アカウントID、元export名、元hash、元時刻、ローカル絶対パスは公開証跡に含めない。構造fingerprintは安全確認後のschemaだけから作成し、完全性や匿名性の証明とは扱わない。

## Adapter contractとversioning

`src/nexus/adapter_contracts.py`に`history-adapter-contract-1`を定義した。Provider/Productとparser versionを分離し、private review reference、Conversation/Message、coverage、untrusted markerを受け渡す。Protocolはboundedな純粋parser。network、subprocess、account認証、DB書込、AI実行は責務に含めない。

`UnverifiedRealAdapter`は常に拒否する。実サンプル、承認文字列、schema_evidence_idを渡しただけで有効化できない。実装をレビューして別のparser versionとして登録するまで、APIはreal-format gatesをBLOCKEDと返す。合成の`synthetic-fixture-1`・fixture群・initial migrationを流用しない。

| 契約項目 | 受入れ条件 |
|---|---|
| Provider / Product | Consumer 2製品を区別。Work/Codex/Claude Codeをconsumer exportとして混ぜない |
| Source identity | source/account namespace + 元conversation/message IDを保持。存在しないIDを内容hashで適当に補完しない |
| Revision | 同一IDの編集・再生成・分岐の意味を実サンプルで確認。現行V1は内容/role/time変更でbatch全体409 |
| Timestamp | 元の型・表現・timezoneとobservation timeを区別。曖昧な値は拒否か明示した未検証扱い |
| Coverage | complete/attachments/branches/revisionsは初期false、missing_records_possibleはtrue |
| Missing/deleted records | 後続部分exportの不在を削除と解釈しない。破壊的削除は別承認 |
| Version change | 新parser版でdry-run、正規化差分・ID衝突・件数・coverageをレビュー。保存済みIDの自動書換えなし |
| Unknown fields | 無視する範囲を明示し、保存対象に影響する新fieldや曖昧な型でfail closed |

単体テスト雛形は`tests/test_adapter_contracts.py`。現状はdisabled・coverage・製品/Capability分離の検証であり、実形式parserの検証ではない。実装時はprivate承認fixtureごとの入力→正規化ID/role/時刻/件数、incremental/reimport、revision/branch、malformed rollback、非text欠損、Prompt Injection不実行を追加する。既存1,000-message、固定30+30 search、123 baseline、DOM16、Chromium2は維持する。

## 有効化Gate

承認済み実サンプル適合、provenance/ID collision、incremental/reimport、Unicode/long history、異常入力全rollback、privacy/ACL/backup、ユーザーWindows実機、正確なHEADのCIを別々に評価する。サンプルの未検証scopeを消さず、対応Productとparser versionを明示する。両consumer製品と実機Gateが完了するまで **V1公式判定BLOCKED**。

## 公式参照（2026-10-11確認）

1. [ChatGPT export](https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data)
2. [Claude export](https://support.claude.com/en/articles/9450526-export-your-claude-data)
3. [ChatGPT Work](https://learn.chatgpt.com/docs/use-chatgpt)
4. [Codex App Server](https://learn.chatgpt.com/docs/app-server)
5. [Codex commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
6. [Claude Code sessions](https://code.claude.com/docs/en/agent-sdk/sessions)
7. [Claude Code headless](https://code.claude.com/docs/en/headless)
