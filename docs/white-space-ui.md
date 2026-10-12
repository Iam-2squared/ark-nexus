# White Space / White Singularity — UI base

2026-10-12。対象はARK Nexusだけ。これはUI方向性を確認するためのアプリシェルで、V1公式完了・実形式対応・ユーザーWindows実機の証拠ではない。

## デザインと構造

- 背景はoff-white / silver / pale blueの静的gradient、薄い霧、22個のSVG星と軌道線。画像、外部font、Canvas/WebGL、3D library、追加packageは使わない。
- Overview中央のWhite Singularityは白い発光核、薄いhalo、前後の傾いたring、光のlensing line。ARK Nexusの知性の中心を示す象徴で、物理simulationや実行中AIの表示ではない。
- 固定左sidebarを廃止。6個のラベル付き星ノードを中心の周囲に置く。他5画面では同じDOMのナビをコンパクトな星座帯として維持し、選択後もkeyboard focusが失われない。
- 4 metricは半透明のOrbit panel。APIから取得した保存済み件数だけを表示する。取得前/lock後は「—」、API unavailable時は既存の取得時刻付きsnapshotとして扱う。デモ用の架空件数は追加しない。
- 現在のAPI状態はheaderに表示。synthetic-only / live sync off / V1 BLOCKEDを明示し、実アカウント接続や自動タスク実行を示唆する操作を置かない。

`components/CosmicShell.tsx`のAppShell / CosmicBackground / StarNav / SingularityHub / StatusConstellation / MetricCard / OrbitPanelを再利用する。2026-10-12 mega-batch指示に基づき、見た目を維持してAppのguard/session/race/pagingを改善する。認証/CSRF契約・既存評価とstyle.css/CosmicShellは維持する。

## 2026-10-12 操作品質

既存24 DOMに23件、既存5 Chromiumに2シナリオを追加。二重submit同期guard、abort/session、別reload失敗後の遅い401、検索条件変更時クリア、会話source/project、cursor停滞/重複ID、明示retry/aria-live/空状態を検証する。URL/historyに保存するのはpage名のみ。query/alias/本文/keyは保存しない。page移動のdraftはmemory保持、Lock/401で消去する。

白いN/ring/6星/見出し/CSSは保持。baseline画像を実際に確認し、新source画像/Chromiumは対応HEADのCIで別検証する。[一括検証](megabatch-2026-10-12.md)。実形式・owner Windows・私的データGateは昇格しない。

## 操作・レスポンシブ

Desktopは周辺に星ノード、mobileはコアの下に3列×2行のラベル付きノード。狭い画面でも6導線を隠さない。native button、aria-current、navigation landmark、skip-to-main、focus-visibleを使用し、装飾SVGを操作対象から除く。主要buttonは44px以上。静的表示を基本にし、prefers-reduced-motionでhover transitionも無効化する。forced-colorsでは装飾より境界・focusを優先する。

英字の小さな座標/番号は装飾。本文・運用ラベル・警告は可読性を優先する。セキュリティ/機能の未検証状態をグローや成功色だけで判定させない。

## 評価と証跡

既存DOM20件、Chromium2シナリオ、backend/Linux/Windows Gateは保持。追加DOM4件は中心核・未知件数・6導線・focus・未認証のprivate requestゼロ・装飾の非操作性、未focusのskip linkのclipを確認する。

追加Chromium3シナリオで、locked状態の6導線/keyboard focus、320/390/768/1024/1440px全ページの横overflowとclick、reduced-motion/skip link、実際の合成API取得/lockを検証する。最終HEADのCIを確認するまで実ブラウザーPASSとはしない。

CI artifactは明示した4枚の合成PNGだけを1日保存する：overview-mobile.png / connections-desktop.png（既存）、overview-desktop.png / overview-locked.png（追加）。private profile、DB、key、trace、raw exportはartifactに含めない。Desktop PNGは1440×1000のviewport、mobile PNGは既存390pxのfull page。実機WindowsやSafariの結果ではない。

今後のUI課題：所有者による世界観レビュー、中央核/文字量のバランス、mobileの情報優先順位、全ページの密度調整、実機ブラウザー/assistive technologyの追加確認。機能追加や未検証Gate解除とは別の作業として扱う。

## 2026-10-12 初期UIへ復元

所有者の「一番最初に戻して」により、最初のWhite Space UIの表示修正版 c2d488b6ffb7b31decf2be056300629b00c3d136 の見た目へ復元する。白いNの中心核、淡いbackground/nebula、細いring、星ナビ、初期の見出しと余白を戻す。skip linkのclipと画像先頭の補正は維持する。

UI関連7ファイルをそのsourceの内容へ戻し、後から追加したWebGL scene/renderer/GLSL/type/renderer testsの5ファイルを削除する。原本App DOM20、Chromium2、backend/tests/fixtures/migrations/固定30+30検索/1,000件取り込みは変更しない。実装しない黒い空洞・巨大disk・WebGL専用の視覚/描画テストは、当該featureの撤回として元のUI suiteへ戻す。評価を通すための安全/機能条件変更ではない。DOM24/build/Chromium5とWindows/Linuxの新しいHEADのCIを改めて確認する。

Git履歴を書き換えず、現在の開発branchに復元commitを追加する。以前の失敗/PASSは以下とDraft PRに履歴として保持し、新しいHEADへ流用しない。実形式Adapter BLOCKED、owner Windows NOT RUN、V1公式BLOCKEDは継続。

直前のphoto-like source 828ed31702c671c186f07718391441c224fdc359 はrun38210325009で5/5 PASS（Vitest37/build/実Chromium6、Linux193+3 skip各/Windows194+2 skip各）。これは所有者が取り消したUIの履歴証拠であり、復元HEADの証拠ではない。

## 以前の検証履歴（現在HEADのPASSには流用しない）

photo-like source abc6488e91e56aebc06d8756cf76b6f59489a687 / run38209674708は4/5 PASS。Linux193+3 skip各/Windows194+2 skip各、Vitest36/buildと追加実Chromium5シナリオはPASS。既存の1,000件シナリオは最後のLock操作で30秒上限に達した。繰り返すOverview mountとStrictMode replayで重い同一画面を再計算していたため、同じcanvas/framebufferを保持する失敗回帰2件を先に追加して修正した。既存30秒timeout、原本Chromium2、1,000件/検索/lock条件は変更しない。見た目の4枚・artifact digestとrunner報告は確認できても、このHEADの総合CIはFAILでありPASS証拠に流用しない。追従HEADの別CIを必須とする。


最初のUI source 2e5e82c27bcf79a900cab231820459ccea3bee9cのrun38199394107は5/5 PASS（DOM23/build/Chromium5、backend既存件数）。画像確認で、unlock後のscroll位置によるdesktop画像先頭切れと、負のtopによる未focus skip linkのfull-page画像写り込みを確認した。追加DOM回帰を失敗再現してclip方式に修正し、focused link表示・画像先頭位置を追加Chromiumでassertする。既存評価を緩めず、仕上げHEADには別のCI証拠を要求する。

参考画像に合わせたsource 089463f023fea79ad3656a22ffc935c080d01ba3のrun38201611814は5/5 PASS（DOM26/build/Chromium5、backend既存件数）。画像確認で、既存の放射状ナビ補助線が白い空洞と発光diskを横切ることを確認した。追加のDOM条件を失敗再現し、放射線だけを廃止して周囲の点線軌道と6星ノードは保持した。5幅のChromium検証にも中心を横切る補助線ゼロを追加。仕上げHEADのCI/画像結果はDraft PRに記録し、前HEADのPASSを流用しない。

source a477117d69b31932b8599a3cac08e3c00773e978のrun38201877782は5/5 PASS（DOM26/build/Chromium5、backend既存件数）。その後、所有者が中心を黒にするよう指定したため、SVGの中心fillのみ#000へ変更した。DOMの黒い中心条件を修正前に失敗確認し、Chromiumでも5幅すべてで黒をassertする。白背景、発光disk、形状、操作、安全境界の条件は維持。今回HEADのCI/画像は別に検証してDraft PRに記録する。

円を拡大したsource 9eb83d42a8c9631ce3859c4816472e2a652c0dbdのrun38204909543は5/5 PASS（DOM26/build/Chromium5、輪の実直径/既存backend件数）。画像で発光disk両端の切断を確認したため、追加DOM回帰を失敗確認して両端10%のsoft maskを追加した。5幅の実ブラウザーでもsoft maskを要求し、輪の最低直径と既存操作条件は維持。仕上げHEADのCI/画像を別に検証する。

巨大なgravity fieldを導入したsource a119995642cd8c4dfa85e1d26ea716203e0197e2のrun38207186867は5/5 PASS（DOM27/build/Chromium5、backend既存件数）。画像でfield上下の切断、captionとmetricへの接近、黒い中心を横断する点線を確認した。追加DOM回帰を失敗確認して縦横fadeのintersectとscene内caption配置を固定し、点線nav ellipseは表示せず独自のinflow軌道を使用する。5幅のブラウザー検証にも同条件を追加。既存の直径/操作/機能Gateは維持し、仕上げHEADのCI/画像を別に検証する。

最後のnavigation reviewでは空hashへのBackをOverviewとして扱う1行修正を追加。unknown/skip anchorは現在pageを保持する。初期hashのdeep-link対応は未追加。元のDOM24/Chromium5と30秒timeoutは保持し、最終HEADのCIを別確認する。
