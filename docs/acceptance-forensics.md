# 受入れ境界の合成監査（2026-10-12）

この監査はP3の純粋contractとowner検証producerに限定する。実形式のサンプル、
Windows所有者実機、private profile、外部AIにはアクセスしない。10k DB異常の
原因特定・修正証拠とは別の作業であり、その判定を変更しない。

## 再現と最小修正

開始source HEADは`18e61002a7f89bc065c296e100a574bf10ff1ac4`。
追加した`tests/test_forensic_acceptance.py`の修正前結果は**12 FAIL / 8 PASS**。
同じ20件は修正後**20 PASS**。既存の評価定義・fixture・manual Gateは変更しない。

| 合成で再現した境界 | 修正前 | 修正後 | 失敗再現数 |
|---|---|---|---:|
| `run_probe`のoffline宣言 | integer/string/null/collectionでもprobeの副作用へ進む | builtin bool以外は副作用・report変更前に固定診断で拒否 | 4 |
| 取消済みtaskの履歴 | review snapshotなしの正のattempt countを受理 | 先行attemptがあればreview参照とfingerprintを必須にする | 3 |
| Adapter/resultの標準repr | 本文・ID・hash・私的review参照を表示 | 正規化データと私的review参照を標準reprから除外 | 2 |
| PowerShell transport障害 | timeout/subprocess/OS例外がcommandやoutputを含み得る | `Windows inspection failed`へ固定し例外contextを抑制 | 3 |

取消は未reviewの0 attempt、review後の0 attempt、実行simulation後の1 attemptで
引き続き可能。既存のreview leaseとattempt countを保持し、terminalから再開しない。
KeyboardInterruptはtransport障害へ変換せず、中断Gateの分類へ渡す。
repr制限は値の削除・匿名化・Python sandboxではない。`asdict`、明示的属性参照、
payloadそのものは私的データのままであり、公開logへ渡してはいけない。

## 検証範囲

Linux Work / Python 3.12.14で、新規専用ignored test rootを使って実行した。
新規20件と既存Adapter・manifest・Connector・owner receipt・machine reportの
関連suiteは**317 PASS / 1 deselected**、対象RuffはPASS。
1 deselectedはlocalhostサーバーを起動する既存probeテストで、他ワーカーの同じ
ポートとの競合を避けるため、この独立contract実行からだけ除外したもの。
元テストは変更せず、統合検証とCIで従来どおり実行する。Windows実機GateのSKIPや
PASSへの変更ではない。

UIは`App.tsx`、`CosmicShell.tsx`、`style.css`、既存DOM/E2E定義を読み取りのみで
確認し、変更しない。白いN、6星ナビ、skip link、keyboard focus、reduced motion、
lock/session epochの既存構造を保持する。画面やChromiumの最終確認はsource HEADに
対応する統合CIで別に行う。この監査はpixel一致やSafari実測を主張しない。

## 維持する実運用Gate

| 対象 | 現行境界 |
|---|---|
| Owner report receipt | 既存10 field / 14 Gate、16 KiB、UTF-8、重複key拒否、別途選んだsource HEAD固定を維持 |
| Owner Windows | offline、browser、別OSユーザー、通常profile ACLの本人証拠は未受領 / NOT RUN |
| Consumer ChatGPT / Claude | 承認済み匿名化実サンプル未提供、両実形式AdapterはBLOCKED / disabled |
| Connector 6製品 | not_connected、implemented=false、execution_enabled=false |
| Task simulation | provider_calls=0、cost_microunits=0、認証・dispatch・resume・live sync経路なし |
| 公式Version | V1 BLOCKED、V2～V5 LOCKEDの判定をこの合成監査で昇格させない |

receipt受理はreport作成者の本人証明にならない。manual/real-format Gateの追加PASSを
JSONに書き込む経路はない。本人レビューされたreportと別メモのmanual結果だけを
既存の[所有者チェックリスト](windows-owner-checklist.md)に沿って受け入れる。
raw console、DB、key、SID、実パス、raw exportの収集は不要であり、行わない。
