# Private fixtureのmanifest事前レビュー

`src/nexus/adapter_preflight.py`は**構造と承認状態の宣言だけ**を検証する内部contract。
export・JSON・ZIP・秘密・原本pathを受け取らず、ファイルもDBも読まない。
Consumer ChatGPT / Consumer Claudeの実サンプルは引き続き未提供で、
real-format Gateは両方とも**BLOCKED / disabled**。
この追加は実形式parser、匿名化ツール、秘密検出の保証、V1/V2のPASSではない。
実サンプルの扱いは[既存の受入れ手順](real-format-acceptance.md)に従う。

## レビューする宣言

| 分類 | manifestの確認事項 | 未確認時の扱い |
|---|---|---|
| Namespace | Provider / Consumer Product / parser版 / 私的review参照の完全一致 | 拒否し再レビュー |
| 使用承認 | この最小匿名化サンプルの利用を所有者が承認 | `owner_approval_required` |
| 匿名化 | 本文・metadataを確認。動的JSON keyも別に確認 | 匿名化・動的keyのreview code |
| 添付 | sampleからbinary・画像・音声等を除外したこと | `attachment_exclusion_required` |
| 元ID | 実際に確認した元のstring/integer型を宣言。一律string変換をしない | 型reviewまたはprovenance拡張が必要 |
| 時刻 | 実際の表現・timezone・精度を宣言 | 未確認はBLOCKED。epoch/mixedはprovenance拡張が必要 |
| 参照 | 匿名IDの一貫性・graphの参照構造を確認 | `reference_validation_required` |
| branch / revision | 未確認、実際に不在、原表現を保持、を区別 | 未確認はBLOCKED。保持には新しい保存contractが必要 |
| 部分export | `missing_records_possible=True`を既定とする | 不在から削除を推定しない |
| 未知field | 保存対象に影響する未知field/型をfail closed | `unknown_field_policy_required` |
| 実行境界 | 純粋parserのコードreviewと、本文を実行しないpipelineのreview | parser/inert pipeline review code |

文字列IDとtimezone-aware ISO表現以外を、現行の正規化保存modelへ損失変換して
押し込まない。integer ID、epoch/mixed時刻、分岐・修正の原表現を保持する場合は、
元の型・参照・精度を保持できる新contractとprivate fixtureによる検証が必要。
このmanifestは架空のChatGPT/Claude field名やJSON構造を指定しない。

## 結果の意味

`review_private_fixture_manifest(manifest, expected_identity)`は固定code、
Provider/Product、`missing_records_possible`、次のGate名だけを返す。
path、account/source ID、parser版、review参照、本文、hashは返さない。
真偽値は実際の`bool`だけ、分類語は固定の選択肢だけ、元ID型は最大2種で重複なし。
期待するProduct・parser版・review参照が変わると拒否する。

`review_ready=True`は**宣言の不足がない**という意味だけ。
承認書の真正性、実sampleの存在、匿名化の完了をこの関数が証明することはない。
すべての宣言を架空の合成値で満たしても、出力は必ず次の状態を維持する。

| 出力 | 固定値 |
|---|---|
| `mode` | `manifest_only` |
| `gate_state` | `BLOCKED` |
| `enabled` / `real_format_verified` | `false` / `false` |
| `files_read` / `stored_records` | `0` / `0` |

別途必要なのは、承認済みprivate fixtureそのもののレビュー、parser回帰、保存面の
privacy確認、所有者Windows実機証拠、source HEADとCIの一致、有効化の個別review。
manifest結果をHTTP registryやConnectorの有効化判定に使う入口は追加していない。

## 正規化dry-runの追加防御

`adapter_contracts.py`はparserを呼ぶ**前**に期待identityとparser identityを再検証し、
正しい`AdapterIdentity`以外の等値objectを拒否する。正規化文字列・contract/trust
markerはbuiltin `str`だけ、content hashは小文字64桁hexと内容のSHA-256の一致を
要求する。文字列subclassがencode/hash/等値を上書きして検査を迂回する形も拒否する。

追加の合成再現は`tests/test_adapter_contract_hardening.py`。初回の修正前は18件のうち
13件がFAILし、identity spoof、hash spoof、parse前のidentity不正、marker/文字型の
曖昧さを検出した。さらに別の1件で、parserが共有identityを変更すると期待review版まで
変わる問題を再現した。検査前のreview値を独立copyに固定し、parse後も照合する。
既存の契約・1,000-message再取込・固定検索Gateを変更していない。
この型検査は任意Python parserをsandboxするものではなく、parserのコードreviewは必要。

## 合成確認

`tests/test_adapter_preflight.py`は実際のvendor schemaも私的ファイルも使わない。
虚偽宣言で実Gateを昇格できないこと、型/参照/精度の未確認、損失変換に必要な
provenance contract、secretを返さないsummary、ファイル/DB/通信/command不実行を検証する。

```text
python -m pytest tests/test_adapter_contract_hardening.py tests/test_adapter_preflight.py \
  --basetemp=tmp/pytest-private-contract-review -p no:cacheprovider
```

このcommandは専用の合成作業環境で実行する。既存の通常profile、DB、原本、key、
private sampleを入れない。GitHub/CIへ追加できるのは合成fixtureと匿名化された件数・
固定codeだけで、実sampleやmanifest内の私的review参照はcommitしない。
