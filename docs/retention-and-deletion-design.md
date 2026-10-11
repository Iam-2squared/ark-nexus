# 保持・削除・取消・再取り込み設計（未有効化）

2026-10-11。現在の保持期間は無期限。自動cleanup・DELETE endpoint・source削除の自動伝播・保存済みDBの置換はない。破壊的削除を実行できる新機能は、この変更では追加しない。

| 操作 | 現在の動作 | 将来の承認付き設計 |
|---|---|---|
| dry-run | 合成parser検証のみ、全保存0件 | 実形式ごとのcoverage/衝突を事前確認 |
| 不正/衝突import | batch全体rollback、source/receipt/event/auditも追加0 | 拒否理由を機密なしで任意保存する場合は別設計。成功と混在させない |
| import取消 | commit前の異常でrollback。保存成功後のundoなし | 影響ID、共有する既存record、FTS、audit、backupをpreviewして個別承認 |
| UI lock | keyと本文・件数・選択file・入力を画面/セッションから消す | DB削除とは別。既に送信済みのimportの成功を取り消さない |
| 保持期限 | 無期限、schedulerなし | ownerがsource/project別に指定。期限到来は削除候補提示のみ、承認なし自動削除しない |
| 会話/source削除 | 無効 | conversation/message/FTS/project参照/event/receiptの整合性を1transactionで処理 |
| 再取り込み | 同一内容は重複追加0、同一ID変更は409 | tombstoneと再取り込み許可をownerが明示。部分exportの不在から削除しない |
| 復旧 | SQLite backupから新規パスへcopyし件数/整合性検証 | 元DBを維持した切替preview、別途owner承認 |

取消の将来実装は、importで追加したrecordと、それ以前から存在する重複recordを区別する。既存recordのtitle/project更新を無条件で戻さない。複数batch/sourceが参照するrecordや決定事項を壊さない。Previewに本文や秘密を含めず、件数・scope・復旧可否を示す。承認のactor、対象scope、期限、現在HEAD/DB snapshotへのleaseを要求する。会話本文や取込された指示から承認を作らない。

削除後の再取り込み方針は、tombstoneを保持するか完全除去するかをownerが選ぶ必要がある。tombstoneのID/hashもprivate metadata。保存場所と保持期限を定めずに追加しない。SQLiteのDELETEだけで媒体上の完全消去を保証しない。WAL/journal、バックアップ、OS snapshot、SSDの特性も含める。実データのVACUUM、secure_delete、key破棄やバックアップ削除を自動で実行しない。

## 平文と暗号化

現在は **SQLite平文**。bearer keyはHTTP認証でありDB暗号化keyではない。POSIXの0700/0600やWindows DACLはOSユーザー間のアクセス制御。管理者/SYSTEM、同じOSユーザー、侵害された端末、持ち出された未暗号化backupからは守れない。フルディスク暗号化もログイン済みユーザーや管理者に対する分離の代替ではない。

将来の方式候補はSQLCipher等のDB暗号化、またはアプリ層のrecord暗号化。FTS・インデックス・タイトル・source metadata・WAL/shm/journal・backupに漏れる範囲、Windows/Linuxへの配布、migration、暗号keyのOS credential store保管、unlock/rotation/recovery、紛失時の復旧、暗号化前の残存ファイルを設計してから採用する。現時点では方式未選定・暗号化未実装。OS credential store接続や実データmigrationも別承認。

バックアップは常にprivate。現在のcopyは新規pathに限り、SQLite/FK/FTS/content hashを同じsnapshotで検査する。sourceが論理破損していたら「verified backup」として受け入れない。失敗後に取り除くのはその呼出しが作った同じinodeの新規destinationだけ。既存DB/sidecarや差し替えられたファイルは削除しない。
