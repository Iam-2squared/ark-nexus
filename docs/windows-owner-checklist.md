# Windows所有者向け：最短の検証・共有チェックリスト

2026-10-11。まだ実行していない欄は **NOT RUN**。現在、ユーザー実機の証拠は未受領。詳しい依存準備・UI操作は[実機検証ガイド](windows-machine-validation.md)。以下をWorkが代行・仮入力することはない。

1. **通常権限のPowerShell**をARK Nexus専用checkoutで開く。管理者ウィンドウを使わない。checkout、tmp、.venv、node_modulesに外部パスを指すリンク/junctionがある環境を使わない。
2. Gitのoriginが`Iam-2squared/ark-nexus`、branchが`feature/v1-unified-history-scaffold`であることを確認。`git status --porcelain`が空でなければここで停止し、作業中の変更を保護する。通常profile、DB、key、システムACLを変更しない。詳細ガイドの依存導入とUI buildをオンライン時に済ませる。
3. 自分が起動した8788番Nexusだけを自分のウィンドウでCtrl+C終了。ポートを使っている他プロセスは終了しない。4つの`Inspect/Test` PowerShellスクリプトと`machine_check.py`をレビューする。
4. 外部ネットワークの切断を**本人が確認した場合だけ**、次を実行する。未確認なら`-OfflineAttested`を省き、offline GateをNOT RUNに保つ。ツールは通信設定を変更しない。

   ```powershell
   powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\Test-NexusWindows.ps1 -Python .\.venv\Scripts\python.exe -OfflineAttested
   ```

5. 出力された相対パスの`report.json`だけをローカルで開く。自動8 GateがPASS、`context=owner_windows`、`working_tree_clean=true`を確認する。`official_v1=BLOCKED`は正常。終了0は「実施できた合成probeにFAILなし」であり、V1完了ではない。FAILは実施失敗、SKIPはその環境で対象外、NOT RUNは未実施。`interrupted`は中断、`check_failed`は機密を含まない汎用理由で、詳細な原因を推測しない。
6. 手動UIと別OSユーザー検査は詳細ガイドに従い、下表を別メモで記録する。通常保存先ACL、実形式は別の承認と証拠が必要。新アカウント作成、管理者昇格、権限変更で条件を満たそうとしない。
7. 自分で除秘を確認した**report.jsonと手動Gate結果のみ**共有する。tmp全体、DB、key、SID、氏名、端末名、パス、トークン、raw console dump、画面内の個人情報は共有しない。実形式のサンプルは[別の受入れ手順](real-format-acceptance.md)による。

| Gate | 今の実機判定 | 共有できる固定理由／必要条件 |
|---|---|---|
| offline_cold_start | NOT RUN | operator_required。本人の切断確認＋その実行のJSONがあればoperator_attested |
| owner_browser_ui | NOT RUN | operator_required。合成profileのAPI/UI/検索/lock/再開を確認 |
| other_os_user_denied | NOT RUN | operator_required。既に承認済み標準OSユーザーでDB/keyの両方が拒否。該当ユーザーが無ければSKIP / available_test_user_absent |
| private_profile_acl | NOT RUN | operator_required。通常保存先はこのprobeの対象外。別途承認されたレビューが必要 |
| real_chatgpt_format | NOT RUN | approved_sample_required。AdapterはBLOCKED / disabled |
| real_claude_format | NOT RUN | approved_sample_required。AdapterはBLOCKED / disabled |

## 停止・失敗したとき

Ctrl+Cを1回押し、後始末と終了を待つ。通常の中断では自分の子サーバーだけを止め、試行中GateをFAIL/interruptedとして残す。事前検査や証跡保存時の中断・権限不足ではJSONが作れない場合があり、その結果は未取得。強制的なウィンドウ終了・OS停止で後始末が完了する保証はない。次回に8788番が使用中なら停止して、自分の起動したプロセスかを本人が確認する。他PIDを自動終了する機能はない。

既存のテスト領域を再利用・上書き・自動削除しない。再試行は新しいrun-idになる。新規テスト領域への書込権限がない、checkout変更中、外部Git directory、junction等がある場合は固定診断で拒否する。システムACLや通常profileを修正して再試行しない。

GitHub runnerのreportには`context=github_runner`とPR merge checkoutのHEADが記録される。Actionsのsource HEADと区別する。runnerで`-OfflineAttested`を指定しても所有者offline GateはNOT RUN。ユーザー実機の代用にはならない。
