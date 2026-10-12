# Windows実機検証：合成データ専用・非破壊

確認日: 2026-10-11。ユーザーWindows実機は **NOT RUN**。GitHub Windows runnerの成功はユーザーPCの成功を意味しない。実形式サンプルと実機Gateが揃うまでV1公式判定は **BLOCKED**。

短い実行・共有チェックリストは[所有者向けチェックリスト](windows-owner-checklist.md)。結果をWorkが仮入力することはない。

## 境界と事前準備

ARK Nexus専用checkoutで行う。管理者として起動しない。既存DB、通常のLOCALAPPDATA、他プロジェクト、他ユーザーの権限、ネットワーク設定は変更しない。外部AIや有料APIには接続しない。以下の依存取得はインターネットがある間に完了させる。Python 3.12または3.13、Node 22.12以上、Gitを事前に用意する。

```powershell
git remote get-url origin
# 完全に Iam-2squared/ark-nexus を指すことを自分でも確認
git switch feature/v1-unified-history-scaffold
git pull --ff-only
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Push-Location apps/web
npm ci --no-audit --no-fund
npm run build
Pop-Location
```

`git switch` / `git pull`の前に`git status --porcelain`が空であることを確認する。作業中の変更があるcheckoutを上書きしない。Python 3.13の場合は`py -3.13`に置き換える。GitHub上の最新HEADとローカル`git rev-parse HEAD`を照合する。checkout、tmp、.venv、node_modulesのリンク/junction経由で別プロジェクトを使用しない。

## 自動検証コマンド

Nexusの8788番サービスを自分で通常終了してから実行する。ポート使用中は検証を拒否し、他のプロセスを終了しない。

```powershell
powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\Test-NexusWindows.ps1 -Python .\.venv\Scripts\python.exe
```

`ExecutionPolicy Bypass`はこのプロセス内だけ。永続的な実行ポリシーやシステム権限は変更しない。実行前に4つのPowerShellスクリプトと`src/nexus/machine_check.py`をレビューできる。所有者実機では、変更中のcheckoutと昇格した管理者tokenをファイル作成前に拒否する。token確認は固定の真偽値だけを扱い、氏名やSIDを出力しない。Git metadata取得では継承したGIT_DIR等を除き、index更新を無効化する。外部Git directoryを参照するworktreeもこのprobeでは拒否する。

毎回、新しい`tmp/windows-evidence/<run-id>/`を排他的に作成する。ACLを設定するのは、その実行が作った空のテストディレクトリ1つだけ。継承を止め、実行ユーザー、SYSTEM、Administratorsのみを許可する。SYSTEM/管理者と同一OSユーザーのプロセスは保護境界外。symlink/junction/reparse pointを拒否する。既存DBの削除・上書きやテスト領域の自動削除は行わない。

rootのDACL検査後、profile/backup/restoredの新規空ディレクトリだけを保護済みrootから継承させて作る。Windows Pythonの`mkdir(0o700)`による別DACL生成でSYSTEM grantが落ちないようにするため。ファイル検査の必須grantを削除してPASSにする変更ではない。通常のアプリ保存先・既存ディレクトリの権限は変更しない。

標準出力は`Evidence: tmp/windows-evidence/<run-id>/report.json`のみ。結果は固定Gateと理由コードのJSON。ユーザー名、ホームパス、SID、端末名、PID、キー、本文、ファイル名、HTTP生レスポンス、例外の内容は保存しない。子サーバーの標準出力・エラー・アクセスログも収集しない。共有するのはレビューした **report.jsonだけ**。ディレクトリ全体、DB、key、ブラウザーのストレージ、ターミナル全文を送らない。

| 自動Gate | 期待結果 | 実際に確認するもの |
|---|---|---|
| cold_start | PASS | 空の合成profileからAPIを起動、health ready |
| owned_loopback_listener | PASS / Windowsのみ | 8788のlistenerが自分の子PIDの127.0.0.1のみ |
| owner_auth | PASS | 認証なし401、専用キーで200 |
| host_origin_csrf | PASS | 外部Host/Origin、不足した書込ヘッダーを403 |
| synthetic_import_search | PASS | 日本語合成1件の取込・検索・再取込追加0件 |
| restart_persistence | PASS | 子プロセス停止・再起動後にキー、件数、整合性維持 |
| backup_restore_new_path | PASS | 新規backupと新規restore、復元先でAPIを起動して件数・整合性確認 |
| owned_test_acl | PASS / Windowsのみ | 専用root、DB、key、backup、restoreのDACL許可先と所有者を検査 |
| offline_cold_start | NOT RUNが初期値 | 下記の実機での操作者確認が必要 |
| owner_browser_ui / other_os_user_denied / private_profile_acl | NOT RUN | 自動検証では判定しない |
| real_chatgpt_format / real_claude_format | NOT RUN | 承認済み匿名化実サンプルが必要 |

どれかの自動GateがFAILなら終了コード1。未実行Gateが残っていても自動検証成功は終了コード0になるため、終了コード0をV1公式PASSと解釈しない。失敗時の残存テスト領域は保持する。システムACLを修正して再試行しない。Ctrl+Cは1回押して後始末を待つ。起動待ち中も自分の子サーバーを停止し、実施中GateにFAIL/interruptedを記録する。事前検査・証跡保存の中断ではJSONがない場合がある。強制終了・OS停止の後始末は保証できず、その試行をPASS扱いしない。

## 外部ネットワーク切断時のcold start

依存導入後、自分の判断でWi-Fi/LAN等を切断し、外部接続がないことを確認した状態で次を実行する。スクリプトはネットワークを操作・推測しない。

```powershell
powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\Test-NexusWindows.ps1 -Python .\.venv\Scripts\python.exe -OfflineAttested
```

`offline_cold_start=PASS, reason=operator_attested`は「操作者が切断を確認した状態でAPIがcold startできた」証拠。OSの通信遮断を自動測定した証拠ではない。GitHub runnerではこの引数があってもNOT RUNのまま。オフラインUIは次の別Gate。

## ユーザーPCだけで行う手動Gate

自動結果JSONとは別に、下表のGate名、PASS/FAIL/SKIP/NOT RUN、固定の短い理由を記録する。PC名・アカウント名・パス・キー・画面の個人情報を含めない。任意の結果をスクリプトに投入して自動PASSへ変換する機能はない。

1. **owner_browser_ui**: 外部ネットワーク切断中、別の新しいPowerShellウィンドウでテストprofileを指定して起動する。`<run-id>`は自動検証の出力で置き換える。通常profileは使用しない。

   ```powershell
   $env:NEXUS_DATA_DIR = (Resolve-Path '.\tmp\windows-evidence\<run-id>\profile').Path
   Remove-Item Env:NEXUS_API_TOKEN -ErrorAction SilentlyContinue
   & .\.venv\Scripts\python.exe -m uvicorn nexus.api:app --host 127.0.0.1 --port 8788 --workers 1 --no-access-log --no-proxy-headers --log-level critical
   ```

   さらに別ウィンドウで`cd apps/web; npm run dev -- --host 127.0.0.1 --port 5173`。ブラウザーで`http://127.0.0.1:5173`を開く。テストkeyをローカルのエディターで確認してpassword欄に入力する。キーをコマンド・ログ・スクリーンショットへ含めない。Overviewのmessage=1、Conversationsの日本語1件、Universal Searchの「日本語」1件、Sourcesの合成/手動/外部未接続、Import Historyの2成功/重複追加0件を確認。ロックで件数・本文・フォーム・キーが消え、再開で保存済み件数が戻ることを確認する。停止は各自分のウィンドウでCtrl+C。UIの実機PASSにはこの実測が必要。
2. **other_os_user_denied**: 既に承認済みの別の標準OSユーザーがある場合のみ、そのユーザーでテストDBとkeyを開けないことを確認する。アカウント新規作成、資格情報入力、管理者昇格、他ユーザーACL変更はしない。読み取り試行の例は`try { $s=[IO.File]::OpenRead('<合成テストファイルのローカルパス>'); $s.Dispose(); 'FAIL' } catch [UnauthorizedAccessException] { 'PASS' } catch { 'NOT RUN' }`。パスはローカルだけで扱い、両ファイルを検証する。該当する承認済みユーザーがなければSKIP（理由: available_test_user_absent）。ACL allowlistの自動PASSだけでこのGateをPASSにしない。
3. **private_profile_acl**: 通常の実データ保存先は、このツールでは検査も権限変更もしない。私的データ導入前に、所有者・親ディレクトリ・継承・共有・バックアップ先を別途レビューする。未承認の実データを使わず、現時点はNOT RUN。新規の専用private profileを設計・作成する場合は別途確認する。

| 手動Gate | 未実行時 | PASSに必要な証拠 |
|---|---|---|
| オフラインcold start | NOT RUN | 切断の操作者確認＋その時点のreport.json |
| owner_browser_ui | NOT RUN | 上記API/UI項目を実機ブラウザーで確認した結果 |
| other_os_user_denied | NOT RUN / 条件不成立ならSKIP | 承認済み標準OSユーザーでDB/key両方が権限拒否 |
| private_profile_acl | NOT RUN | 保存先の別途承認されたACLレビュー |

GitHub ActionsはPython 3.12/3.13のWindowsで同じ合成probeを実行し、匿名化report.jsonのみを1日保存する。LinuxではWindows ACL/listenerをSKIP。既存のNTFS junction/POSIX modeテストのSKIPも別に数える。ユーザーPC・実エクスポートの結果は生成しない。

## 共有されたreport.jsonの受入れ

`nexus.owner_receipt.validate_owner_receipt`は、本人がレビューしたJSONのUTF-8 bytesと、受領側が別途照合したsource HEADを受け取る純粋な検証関数。ファイル、プロセス、ネットワーク、ACLへアクセスしない。既存の10 field・14 Gateを変更せず、16 KiB上限、重複/未知field、型、UTC日時、固定status/reason、完全一致するrepository/HEAD、`context=owner_windows`、clean checkoutを検証する。GitHub runner/test harnessのreportやPR merge checkoutのSHAは所有者source HEADの代用にならない。

自動8 GateのFAIL/interruptedと未実施NOT RUNはそのまま件数化する。offline PASSは`operator_attested`とcold_start PASSの組だけを受理する。残りの手動3 Gateと実形式2 Gateはreport内ではNOT RUNを維持し、別メモの実測結果を自動reportへ混ぜない。余分なconsole/path/key欄や手動Gateの書換えがあるJSONは固定codeで拒否する。PowerShell検査のbool JSONも重複keyを拒否し、falseが後続のtrueに置換されてPASSになる曖昧さを防ぐ。

受入れsummaryは`origin=owner_declared_not_authenticated`、`official_v1=BLOCKED`。JSONの構造とrevisionの整合確認であり、作成者・実機・実行内容を独立に認証するものではない。所有者の本人確認、ローカル除秘レビュー、手動Gateの実測確認が別途必要。現在は所有者report未受領で **NOT RUN**。共有する物は引き続き本人レビュー済みreport.jsonと短い手動Gateメモだけ。

## 公式参照

- [Get-Acl](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/get-acl)
- [Set-Acl](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/set-acl)
- [Get-NetTCPConnection](https://learn.microsoft.com/en-us/powershell/module/nettcpip/get-nettcpconnection)
- [WindowsPrincipal.IsInRole](https://learn.microsoft.com/en-us/dotnet/api/system.security.principal.windowsprincipal.isinrole): 現在のtokenを確認。UACの非昇格tokenと管理者としての実行を区別する。

確認日: 2026-10-11。参照はACL/socket検査手段の説明であり、ユーザー実機の結果ではない。
