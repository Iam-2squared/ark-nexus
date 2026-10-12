# White Space / White Singularity — UI base

2026-10-12。対象はARK Nexusだけ。これはUI方向性を確認するためのアプリシェルで、V1公式完了・実形式対応・ユーザーWindows実機の証拠ではない。

## デザインと構造

- 背景はoff-white / silver / pale blueの静的gradient、薄い霧、22個のSVG星と軌道線。画像、外部font、Canvas/WebGL、3D library、追加packageは使わない。
- Overview中央のWhite Singularityは白い発光核、薄いhalo、前後の傾いたring、光のlensing line。ARK Nexusの知性の中心を示す象徴で、物理simulationや実行中AIの表示ではない。
- 固定左sidebarを廃止。6個のラベル付き星ノードを中心の周囲に置く。他5画面では同じDOMのナビをコンパクトな星座帯として維持し、選択後もkeyboard focusが失われない。
- 4 metricは半透明のOrbit panel。APIから取得した保存済み件数だけを表示する。取得前/lock後は「—」、API unavailable時は既存の取得時刻付きsnapshotとして扱う。デモ用の架空件数は追加しない。
- 現在のAPI状態はheaderに表示。synthetic-only / live sync off / V1 BLOCKEDを明示し、実アカウント接続や自動タスク実行を示唆する操作を置かない。

`components/CosmicShell.tsx`のAppShell / CosmicBackground / StarNav / SingularityHub / StatusConstellation / MetricCard / OrbitPanelを再利用する。ページの認証、CSRF header、session epoch、late-response rejection、import/search/project/paging handlersは変更しない。

## 操作・レスポンシブ

Desktopは周辺に星ノード、mobileはコアの下に3列×2行のラベル付きノード。狭い画面でも6導線を隠さない。native button、aria-current、navigation landmark、skip-to-main、focus-visibleを使用し、装飾SVGを操作対象から除く。主要buttonは44px以上。静的表示を基本にし、prefers-reduced-motionでhover transitionも無効化する。forced-colorsでは装飾より境界・focusを優先する。

英字の小さな座標/番号は装飾。本文・運用ラベル・警告は可読性を優先する。セキュリティ/機能の未検証状態をグローや成功色だけで判定させない。

## 評価と証跡

既存DOM20件、Chromium2シナリオ、backend/Linux/Windows Gateは保持。追加DOM4件は中心核・未知件数・6導線・focus・未認証のprivate requestゼロ・装飾の非操作性、未focusのskip linkのclipを確認する。

追加Chromium3シナリオで、locked状態の6導線/keyboard focus、320/390/768/1024/1440px全ページの横overflowとclick、reduced-motion/skip link、実際の合成API取得/lockを検証する。最終HEADのCIを確認するまで実ブラウザーPASSとはしない。

CI artifactは明示した4枚の合成PNGだけを1日保存する：overview-mobile.png / connections-desktop.png（既存）、overview-desktop.png / overview-locked.png（追加）。private profile、DB、key、trace、raw exportはartifactに含めない。Desktop PNGは1440×1000のviewport、mobile PNGは既存390pxのfull page。実機WindowsやSafariの結果ではない。

今後のUI課題：所有者による世界観レビュー、中央核/文字量のバランス、mobileの情報優先順位、全ページの密度調整、実機ブラウザー/assistive technologyの追加確認。機能追加や未検証Gate解除とは別の作業として扱う。

最初のUI source 2e5e82c27bcf79a900cab231820459ccea3bee9cのrun38199394107は5/5 PASS（DOM23/build/Chromium5、backend既存件数）。画像確認で、unlock後のscroll位置によるdesktop画像先頭切れと、負のtopによる未focus skip linkのfull-page画像写り込みを確認した。追加DOM回帰を失敗再現してclip方式に修正し、focused link表示・画像先頭位置を追加Chromiumでassertする。既存評価を緩めず、仕上げHEADには別のCI証拠を要求する。
