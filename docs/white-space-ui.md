# White Space / White Singularity — UI base

2026-10-12。対象はARK Nexusだけ。これはUI方向性を確認するためのアプリシェルで、V1公式完了・実形式対応・ユーザーWindows実機の証拠ではない。

## デザインと構造

- 背景は所有者の追加指定に合わせた単色の白。ごく薄い22個のSVG星と軌道線だけを残し、以前の霧・背景gradientは廃止。画像、外部font、Canvas/WebGL、3D library、追加packageは使わない。
- Overview中央のWhite Singularityは、参考画像の重力レンズ状の弧と斜めに横切る発光diskを白/銀/薄い青で表現する。球体の陰影と中央のNを廃止し、黒い空洞（所有者の追加指定）、18本の曲がる光、24本の前景disk線、薄いphoton edgeに置き換える。有限個の静的SVGと1個の小さなblur filterのみ。`useId`でgradient/mask/filterをHubごとに分離する。参考画像自体はpublic repoに保存しない。ARK Nexusの知性の中心を示す象徴で、物理simulationや実行中AIの表示ではない。
- 固定左sidebarを廃止。6個のラベル付き星ノードを中心の周囲に置く。他5画面では同じDOMのナビをコンパクトな星座帯として維持し、選択後もkeyboard focusが失われない。
- 4 metricは半透明のOrbit panel。APIから取得した保存済み件数だけを表示する。取得前/lock後は「—」、API unavailable時は既存の取得時刻付きsnapshotとして扱う。デモ用の架空件数は追加しない。
- 現在のAPI状態はheaderに表示。synthetic-only / live sync off / V1 BLOCKEDを明示し、実アカウント接続や自動タスク実行を示唆する操作を置かない。

`components/CosmicShell.tsx`のAppShell / CosmicBackground / StarNav / SingularityHub / StatusConstellation / MetricCard / OrbitPanelを再利用する。ページの認証、CSRF header、session epoch、late-response rejection、import/search/project/paging handlersは変更しない。

## 操作・レスポンシブ

Desktopは周辺に星ノード、mobileはコアの下に3列×2行のラベル付きノード。狭い画面でも6導線を隠さない。native button、aria-current、navigation landmark、skip-to-main、focus-visibleを使用し、装飾SVGを操作対象から除く。主要buttonは44px以上。静的表示を基本にし、prefers-reduced-motionでhover transitionも無効化する。forced-colorsでは装飾より境界・focusを優先する。

英字の小さな座標/番号は装飾。本文・運用ラベル・警告は可読性を優先する。セキュリティ/機能の未検証状態をグローや成功色だけで判定させない。

## 評価と証跡

既存DOM20件、Chromium2シナリオ、backend/Linux/Windows Gateは保持。追加DOM6件は中心核・未知件数・6導線・focus・未認証のprivate requestゼロ・装飾の非操作性、未focusのskip linkのclipを確認する。形状・背景の追加2件は修正前に失敗を確認し、空洞/曲がる光/前景disk、文字・raster画像なし、複数HubのSVG ID非衝突、単色白背景/霧なしを固定する。中心色の期待値は所有者の指定により白から黒へ変更し、既存の機能評価は変更しない。

追加Chromium3シナリオで、locked状態の6導線/keyboard focus、320/390/768/1024/1440px全ページの横overflowとclick、reduced-motion/skip link、実際の合成API取得/lockを検証する。さらに、5幅でSVGの画面内収まり・単色白背景・黒い中心、文字/画像なし・装飾による操作遮断なしをassertする。最終HEADのCIと画像確認が終わるまで実ブラウザーPASS/参考画像への適合確認済みとはしない。

CI artifactは明示した4枚の合成PNGだけを1日保存する：overview-mobile.png / connections-desktop.png（既存）、overview-desktop.png / overview-locked.png（追加）。private profile、DB、key、trace、raw exportはartifactに含めない。Desktop PNGは1440×1000のviewport、mobile PNGは既存390pxのfull page。実機WindowsやSafariの結果ではない。

今後のUI課題：所有者による世界観レビュー、中央核/文字量のバランス、mobileの情報優先順位、全ページの密度調整、実機ブラウザー/assistive technologyの追加確認。機能追加や未検証Gate解除とは別の作業として扱う。

最初のUI source 2e5e82c27bcf79a900cab231820459ccea3bee9cのrun38199394107は5/5 PASS（DOM23/build/Chromium5、backend既存件数）。画像確認で、unlock後のscroll位置によるdesktop画像先頭切れと、負のtopによる未focus skip linkのfull-page画像写り込みを確認した。追加DOM回帰を失敗再現してclip方式に修正し、focused link表示・画像先頭位置を追加Chromiumでassertする。既存評価を緩めず、仕上げHEADには別のCI証拠を要求する。

参考画像に合わせたsource 089463f023fea79ad3656a22ffc935c080d01ba3のrun38201611814は5/5 PASS（DOM26/build/Chromium5、backend既存件数）。画像確認で、既存の放射状ナビ補助線が白い空洞と発光diskを横切ることを確認した。追加のDOM条件を失敗再現し、放射線だけを廃止して周囲の点線軌道と6星ノードは保持した。5幅のChromium検証にも中心を横切る補助線ゼロを追加。仕上げHEADのCI/画像結果はDraft PRに記録し、前HEADのPASSを流用しない。

source a477117d69b31932b8599a3cac08e3c00773e978のrun38201877782は5/5 PASS（DOM26/build/Chromium5、backend既存件数）。その後、所有者が中心を黒にするよう指定したため、SVGの中心fillのみ#000へ変更した。DOMの黒い中心条件を修正前に失敗確認し、Chromiumでも5幅すべてで黒をassertする。白背景、発光disk、形状、操作、安全境界の条件は維持。今回HEADのCI/画像は別に検証してDraft PRに記録する。
