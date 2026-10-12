# NEXT batch: review leaseとclockの合成契約

対象は`connector_contracts.py`の純粋simulation。HTTP endpoint、外部認証、provider
call、DB/persisted ledger、実形式parserを追加していない。6 Connectorは未接続・
実行無効、Consumer ChatGPT/Claudeの実形式GateはBLOCKED/disabled、V2–V5はLOCKED。

## 合成再現と修正

`tests/test_next_contract_boundaries.py`は合成objectだけを使う。修正前は24件中
14 FAIL / 10 PASS。次の2つの不足を区別する。

| 再現 | 修正前の観測 | 修正 |
|---|---|---|
| 同一review参照のlease差替え・延長 | start/resume/retryで、approval/expiryを変更したcheckpointも受入れ。9件FAIL | review時にcheckpoint全体のdigestをstateへ固定し、以後のcheckpointと照合 |
| 制御clockの7桁小数秒 | observation/cursor/approval/expiry/nowで、microsecondを超える精度を受入れ。5件FAIL | 比較前にNexus制御clockの表現と精度を検証し、丸め・切捨てを拒否 |

これらは未実行Connectorの**simulation契約の不足**であり、実providerへの
無承認dispatchを再現したものではない。runtimeは引き続き`DisabledConnector`。
合成の有効checkpointがあっても`connected=false / execution_enabled=false /
provider_calls=0 / cost_microunits=0`を維持する。

## review済leaseへの固定

`TaskPlanState.review_sha256`はProvider/Product、source/account/project、task/review
参照、intent hash、approved_at/expires_atをbindする。標準reprとsummaryには含めない。
review後のstart/resume/retryは同じ値を持つcheckpointのcopyだけ受け付け、同じ
review_refの期限延長やin-place変更も拒否する。期限判定は従来の
`approved_at <= now < expires_at`を維持する。

digestは認証済みgrantではない。架空のmetadataからも作成でき、任意Python codeを
sandboxせず、承認者の真正性や取消を証明しない。変更したleaseを既存planへ
差し替える入口はなく、別のreview済simulation planが必要。外部実行に必要な
本人同意、承認authority、永続性、並行processのidempotencyは未実装のまま。

## 原時刻とNexus clockの区別

| field | 現行の受入れ |
|---|---|
| 原sourceの`occurred_at` | builtin stringのtimezone-aware ISO。元表現を無変換で保持し、7/9桁小数秒の合成例も保持 |
| Nexusの`observed_at`、reviewの`approved_at` / `expires_at`、simulationの`now` | `YYYY-MM-DDTHH:MM:SS[.1–6桁]Z`または`…±HH:MM`。日時/offset自体も検証 |

Nexus制御clockにはmicrosecondより細かい値、offsetの小数秒、compact/曖昧な表現を
投入しない。精度を落として通す変換は行わない。この制限を原provider時刻の
schemaとして扱わない。実exportの数値ID、epoch時刻、branch/revision等は別の
provenance契約と承認済みsampleが必要で、今回それを推測していない。

Python datetimeの表現範囲は[Python 3.12公式資料](https://docs.python.org/3.12/library/datetime.html#datetime.datetime.resolution)
も参照した。7桁小数秒の受入れと比較時の切捨ては、このcheckoutのPython3.12.14で
合成回帰として再現した。timestamp stringの保持とinstant比較を混同しない。

## 検証

修正後の新24件はPASS。既存adapter/connectorの6テストファイルを含めた計226件も
PASS、変更対象のRuffと`git diff --check`はPASS。これはローカル合成検証であり、
Windows/Linux各CI・最新source HEADとの一致はbatch全体のCI証拠で別に確認する。
既存のテスト、fixture、scorer、timeout、Gateの条件を変更していない。

```text
python -m pytest tests/test_next_contract_boundaries.py \
  tests/test_connector_planning_contracts.py tests/test_adapter_contracts.py \
  tests/test_adapter_contract_hardening.py tests/test_adapter_validation.py \
  tests/test_adapter_preflight.py tests/test_connectors.py \
  --basetemp=tmp/pytest-next-contract-review -p no:cacheprovider
```

実sample・本文・原ID・review参照・keyを公開ログへ出す運用は追加していない。
承認済み匿名化実sample、保存privacy、owner Windows証拠の不足は今回の
simulation PASSで満たされず、V1公式判定はBLOCKEDを維持する。
