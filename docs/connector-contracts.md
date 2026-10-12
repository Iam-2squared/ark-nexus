# Connector planning contract（V2–V4の合成研究）

`src/nexus/connector_contracts.py`はメモリ内のmetadata確認とtask状態遷移の
**simulationだけ**を実装する。API endpoint・registry・credential・外部dispatch・
同期・provider task取消・DB migrationは追加しない。V1の6製品は引き続き
`not_connected / implemented=false / execution_enabled=false`。
`DisabledConnector`は履歴・status・新規task・resumeをすべて拒否する。

## sourceとcursorの分離

| contract | 確認する境界 |
|---|---|
| `SourceScope` | 6組のProvider/Product、ローカルopaque source/account/project参照 |
| `SourceObservation` | 元のstring ID、発生時刻と観測時刻の区別、kind、untrusted marker |
| `HistoryCursor` | source/account/project/Productとparser版への固定、bounded opaque cursor、観測時刻 |
| `HistoryBatch` | 最大1,000 event、同一page内ID重複0、event/cursorのscope一致、coverage分類 |
| `review_history_batch` | 期待scope/parser版一致、cursor停滞・後退と古い観測の拒否 |

Provider/ProductはConsumer ChatGPT、Consumer Claude、ChatGPT Work、Codex Local、
Codex Cloud、Claude Codeを混ぜない。scope参照の構文検査は承認や匿名化の証明ではない。
元IDがinteger等ならstringへ推測変換しない。元時刻のtimezoneと小数精度を
文字列のまま保持し、別の`observed_at`で観測する。未知の型は拒否する。

cursorとeventのscopeが違うpage、同じnext cursorの反復、観測時刻の後退、
cursorより新しい観測を含む矛盾、`complete=True`なのにnext cursor/coverage gapが
残るpageを拒否する。cursorがなくても欠損し得るsnapshotは`complete=False`のまま。
発生時刻を観測時刻以下に書き換える時計補正や、欠けたrecordの削除推測はしない。

これは一pageの純粋contractであり、pageをまたぐrevision判定・永続cursor・transaction
によるexactly-onceや同期鮮度の保証は未実装。未来の実adapterは別の証拠で検証する。
`complete`は入力宣言であり、実export全体の完全性を証明するものではない。

## taskのsimulation

`TaskIntent`はNexus対象repoを完全一致で固定し、bounded objective、taskとidempotency
参照、new/resumeの区別、resumeに必須のsession参照、最大1–3試行、費用上限0を要求する。
Consumer ChatGPT/Claude、Workのtask操作とCodex Cloud resumeは現catalogで未検証なので、
simulationのintentにも投入しない。公式機構の記載と実際の接続権限は別である。

`intent_fingerprint`はProduct、source/account/project、objective、operation、session、
repo、retry/cost制限をすべてbindする。`ReviewCheckpoint`は同じscope/task/hashと
review参照、有効期間を要求し、review/start/resume/retry時に再確認する。
宣言objectやhashは認証済みgrantではなく、偽造できる。実承認者の検証、取消、
所有者の同意の取得は未実装で、このcontractから外部実行へ進む入口はない。

| 状態 | 許されるsimulation操作 | 次状態 |
|---|---|---|
| `awaiting_review` | 期限内checkpointでreview | `reviewed` |
| `reviewed` | checkpoint再確認でstart | `simulation_running`、試行+1 |
| `simulation_running` | pause / succeed / fail | paused / complete / failed |
| `simulation_paused` | checkpoint再確認でresume | running、同じ試行を継続 |
| `simulation_failed` | checkpoint再確認でretry、上限未満 | running、試行+1 |
| 未完了状態 | cancel | `simulation_cancelled` |
| complete / cancelled | すべて拒否 | terminal状態を維持 |

`plan_task`は最大1,000件の合成ledger内でtask/idempotency参照の重複を拒否する。
objective・scope・session・budgetの途中差替えは既存state/checkpointとのhash不一致になる。
これは呼出側が渡すimmutable snapshotの検査であり、並行process間の重複dispatch防止や
DBの排他制御を実装したという意味ではない。未承認実行、無限retry、別project書込、
provider課金を行うcodeは存在しない。

`planning_summary`は`mode=simulation_only`、stage、試行数、Provider/Productだけを
返し、`connected=false / execution_enabled=false / provider_calls=0 / cost_microunits=0`
を固定する。objective、source/account/project/session ID、cursor、review参照、hashを
返さない。私的metadataは各contractの標準reprからも除く。imported textがtaskの目的を
装っていても、その文字列を命令・shell・network呼出として評価しない。

## 合成検証と未実装境界

`tests/test_connector_planning_contracts.py`で6名前空間、scope混同、Unicode/時刻、
cursor loop/staleness、page上限、synthetic metadata adapter、checkpoint期限・変更、
idempotency、retry/terminal状態、秘密を返さないsummaryを検証する。
DB・socket・subprocessを拒否するテストでもsimulationは完結し、架空のreview成功後も
V1の`DisabledConnector.dispatch_new`は拒否する。

既存の`connectors.SourceEvent` / `ApprovedTask`はfuture placeholderのまま。
新しいvalidated research typeへ置き換えたruntime経路はなく、placeholderをplanning
intentとしてそのまま渡しても拒否する。接続認証、実履歴取得、event監視、provider
status、外部dispatch/resume、承認authority、永続cursor/ledger、実課金制御は未実装。
V2/V3/V4/V5の公式状態をこの合成contractで昇格させない。
