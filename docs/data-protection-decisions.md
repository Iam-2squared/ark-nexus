# データ保護：比較・復旧・移行の意思決定メモ

確認日: 2026-10-11。**方式未選定、SQLite平文、暗号化・保持期限cleanup・破壊的削除は未有効化**。この文書は設計であり、本番移行、OS設定変更、credential storeへの接続、key作成/破棄の承認ではない。通常の実データ保存先は操作・スキャンしていない。

## 保存面と現在の残存リスク

| 保存面 | 現在確認した境界 | 残存リスク／私的データ導入前のGate |
|---|---|---|
| 通常profileのDB/FTS/metadata | owner bearer、transaction、POSIX owner-only、link/reparse/hardlink検査 | 平文。Windows通常保存先のowner/継承/共有/親ACLはNOT RUN。合成rootのDACL PASSを流用しない |
| -journal / -wal / -shm | 各Store connection前のpath検査。backupのsource snapshot | journal/WALはデータpage、SHMは共有状態。crash後残存・OS snapshot・同期folderは別問題 [1] |
| backup / restore | 検証済みの新規pathへのcopy、既存destinationは上書きしない | 平文copy。新規private destinationのOS保護と復旧後のACLを所有者が別途確認 |
| HTTP access key / 将来DB key | 現在のkeyは認証用、Git除外、固定診断。probeは専用合成key | DB keyではない。同一OSユーザー/管理者/SYSTEMは保護境界外。API_TOKEN環境変数も共有・dumpしない |
| multipart / SQLite temp | 入力上限＋15秒/同時2import。memory-only multipart、SQLite build確認＋接続毎MEMORY | Disk spool不使用の合成回帰追加。MEMORYはstatement journal隔離の保証ではない [1]。native観測/Windows owner/swap/crash未完了。[Temp詳細](temp-containment.md)。private exportは禁止 |
| browser memory / session storage | HTTP no-store、tab session key、lockでsnapshotと入力を消し旧responseを破棄 | session storageは暗号化vaultではない。拡張機能・devtools・crash/session復旧・同一ユーザーの侵害は未防御。共有端末で私的データを使わない |
| console / CI artifacts | probe固定JSON/理由のみ、子ログ破棄。CIは匿名reportとallowlisted4枚の合成PNGだけ | 私的fixtureや通常profileをCIへ投入しない。stdout/trace/error-contextはartifact化しない。証跡は1日で失効、private dataの保持方針とは別 |

合成probeは新しい`tmp/windows-evidence/<run-id>`だけを保護する。通常のLOCALAPPDATAやLinux profileを自動でchmod/Set-Aclするツールではない。dirが共有・同期・network・link経由なら私的データ利用を停止する。OS別の実測を必要とする。

## 暗号化候補（未実装・未選定）

次表の運用条件はNexus向けの設計上の評価。公式資料から、その方式をこのユーザーの端末で利用可能・復旧可能と推定しない。

| 候補 | Windows / Linuxの運用条件 | 保護範囲・検索 | key復旧・rotation・失敗時 |
|---|---|---|---|
| 1. OS user保護＋key wrapping | Windows user-scope DPAPI、Linux login-session Secret Service等。実OS/key store利用は別承認 [2][3] | wrapped keyの保存保護。DBはこれだけで暗号化されない。DPAPI machine scopeは全ユーザー復号が可能なのでuser分離の代替に選ばない | OS profile/端末変更、password reset、locked/unavailable storeを想定。別のowner管理の回復手段が必要。取得失敗は起動拒否、平文keyへfallbackしない |
| 2. volume暗号化 | Windows BitLocker、Linux dm-crypt等。OS設定・回復key取扱いは別承認 [4][5] | 盗難/停止中媒体向け。ログイン済み同一ユーザーや管理者を分離しない。外部backup先は別の保護が必要 | volume/device回復をownerが管理。Workは自動設定せず、未保護媒体へbackupを出さない |
| 3. backup単位の暗号化container | Windows/Linux共通のレビュー済みAEAD実装とkey保管を選定。現在のbackup commandは平文 | 持ち出しbackupを保護。通常DB/FTSを保護しない。復号時の平文scratchを作る方式は停止条件 | 認証タグ、版、key ID、private metadataをcontainer内で保護。別端末での復旧・新旧key識別・tamper拒否を合成検証する |
| 4. DB単位 SQLCipher | stdlib sqlite3とは別build。Python3.12/3.13 × Windows/Linux、FTS、配布/ライセンスを評価 [6] | DB pageとjournal/WAL pageの暗号化。file tempの構成も確認。単にPRAGMA keyを標準driverへ渡して暗号化済みと扱わない | 新規DBへversioned変換、key wrap/回復、copy/restore/integrityを検証。key/版不一致や中断は元DBを維持して停止。backup APIのdriver差を再評価 |
| 5. record単位 AEAD | 共通暗号library、field/version/AAD/nonce設計と追加migrationが必要 | 現在のtitle/body/FTS/source metadataはそのままでは漏れる。暗号化本文＋平文FTSを全体暗号化と表示しない | 検索方式、部分rotation、old record復号、欠損keyを設計。自作暗号やsilent record skipを採用しない |

Linux Secret Serviceのlookup attributeはsecretとして扱われない [3]。account alias、元IDやhashをkey lookup attributeへ埋めない。HTTP bearer keyとDB暗号keyは用途・保管・rotationを分ける。いずれの方式も、既に読める同一ユーザーの悪意あるprocessから復号中データを完全に保護するという設計にはしない。

## 後方互換・移行・復旧の停止条件

1. 脅威モデル、OS両方の配布、private temp、FTS/metadata、key recovery/rotation、backup形式/版が決まるまで実データ移行を開始しない。所有者の個別承認を必要とする。
2. 既存平文DBは上書きせず、privateな新規pathへの一貫snapshot変換を設計する。元schema/version、件数、source ID、hash、FK/FTS、backup復旧を照合する。原本の通常場所をツールが探索しない。
3. 磁気/SSD/OS snapshot上に平文が残り得る。新規暗号DBができても原本・journal・backup・tempの完全消去を宣言しない。原本削除/VACUUM/secure_delete/key破棄は別承認、現在は無効。
4. key store locked/unavailable、key紛失、異版driver、復号/tamper失敗、disk full、中断、保存先ACL不一致、links、件数/整合性不一致なら停止。平文fallback、既存DB交換、rawログ出力、失敗recordの黙示skipをしない。
5. 合成データだけでcold/offline startup、両OS復旧、old/new keyのbackup、rotation途中停止、wrong-key/tamper、再取込/search回帰を検証する。その後に新規保存先への切替案をreviewし、実データへの切替は別の明示承認を待つ。

保持・取消・再取込の非破壊previewは[既存設計](retention-and-deletion-design.md)。無期限保持が現在の実装。将来の期限到来は候補提示のみで、本文や取り込まれた指示から削除承認を作らない。

## 公式参照（2026-10-11確認）

1. [SQLite temporary files](https://www.sqlite.org/tempfiles.html)
2. [Windows CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)
3. [Secret Service API](https://specifications.freedesktop.org/secret-service/latest-single/)
4. [BitLocker overview](https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/)
5. [Linux dm-crypt](https://docs.kernel.org/admin-guide/device-mapper/dm-crypt.html)
6. [SQLCipher design](https://www.zetetic.net/sqlcipher/design/)
