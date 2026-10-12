# White Space / White Singularity — UI base

2026-10-12。対象はARK Nexusだけ。これはUI方向性を確認するためのアプリシェルで、V1公式完了・実形式対応・ユーザーWindows実機の証拠ではない。

## デザインと構造

- 背景は所有者の追加指定に合わせた単色の白。ごく薄い22個のSVG星と軌道線だけを残し、以前の霧・背景gradientは廃止。画像、外部font、Canvas/WebGL、3D library、追加packageは使わない。
- Overview中央のWhite Singularityは、黒い空洞、厚い重力レンズ、白/銀/薄い青の降着円盤を主役にする。現在の構成は32本の曲がる光、38本の前景disk線、12本の中心へ巻き込む軌道、42個の固定粒子、広いradial halo。2個の静的SVG filter（blurと弱めた2-octave grain）で光の厚みと質感を作る。`useId`でgradient/mask/filterをHubごとに分離する。参考画像自体はpublic repoに保存しない。ARK Nexusの知性の中心を示す象徴で、物理simulationや実行中AIの表示ではない。
- 固定左sidebarを廃止。6個のラベル付き星ノードを中心の周囲に置く。他5画面では同じDOMのナビをコンパクトな星座帯として維持し、選択後もkeyboard focusが失われない。
- 4 metricは半透明のOrbit panel。APIから取得した保存済み件数だけを表示する。取得前/lock後は「—」、API unavailable時は既存の取得時刻付きsnapshotとして扱う。デモ用の架空件数は追加しない。
- 現在のAPI状態はheaderに表示。synthetic-only / live sync off / V1 BLOCKEDを明示し、実アカウント接続や自動タスク実行を示唆する操作を置かない。

`components/CosmicShell.tsx`のAppShell / CosmicBackground / StarNav / SingularityHub / StatusConstellation / MetricCard / OrbitPanelを再利用する。ページの認証、CSRF header、session epoch、late-response rejection、import/search/project/paging handlersは変更しない。

## 操作・レスポンシブ

Desktopは周辺に星ノード、mobileはコアの下に3列×2行のラベル付きノード。狭い画面でも6導線を隠さない。native button、aria-current、navigation landmark、skip-to-main、focus-visibleを使用し、装飾SVGを操作対象から除く。主要buttonは44px以上。静的表示を基本にし、prefers-reduced-motionでhover transitionも無効化する。forced-colorsでは装飾より境界・focusを優先する。

現在は所有者の「壮大・全てを飲み込むオーラ」に合わせ、Hubを画面幅に近い最大1320px・高さ600px、星ナビ領域を600pxに拡大する。中心はSVG内r=310の黒、photon haloはr=338。画面を横断する円盤と周辺から中心へ曲がる軌道を重ね、見出しは短くして主役へ視線を集める。mobileは390pxの描画領域と466pxのナビ開始位置。SVGを固定枠内に収めて横overflowを防ぎ、光の両端はsoft maskで消す。星ナビには白い半透明の背景を付け、光や黒い領域の前でもラベルとfocusを読めるようにする。

英字の小さな座標/番号は装飾。本文・運用ラベル・警告は可読性を優先する。セキュリティ/機能の未検証状態をグローや成功色だけで判定させない。

## 評価と証跡

既存DOM20件、Chromium2シナリオ、backend/Linux/Windows Gateは保持。追加DOM8件は中心核・未知件数・6導線・focus・未認証のprivate requestゼロ・装飾の非操作性、未focusのskip linkのclip、光の両端のsoft mask、重力fieldの2軸fade/captionのscene内配置を確認する。形状・背景の追加2件は修正前に失敗を確認し、空洞/曲がる光/前景disk、文字・raster画像なし、複数HubのSVG ID非衝突、単色白背景/霧なしを固定する。中心色の期待値は所有者の指定により白から黒へ変更し、既存の機能評価は変更しない。

追加Chromium3シナリオで、locked状態の6導線/keyboard focus、320/390/768/1024/1440px全ページの横overflowとclick、reduced-motion/skip link、実際の合成API取得/lockを検証する。さらに、5幅でSVGの画面内収まり・単色白背景・黒い中心、文字/画像なし・装飾による操作遮断なしをassertする。最終HEADのCIと画像確認が終わるまで実ブラウザーPASS/参考画像への適合確認済みとはしない。

円の拡大はSVG枠の寸法だけでなく、実際の光の輪の直径をscreen CTMから計測する。5幅の最低直径は順に120/150/220/275/275px。既存のクリック・focus・overflow・認証/合成取り込み条件は緩めない。最終画像で輪の見え方とナビの可読性も確認する。

現在の直径計測は`.photon-halo`を対象にする。広い背景auraや粒子のcircleが追加されても、装飾全体を輪の大きさと誤認しないための対象明示であり、最低直径は変更しない。grainは固定seed・2 octaves・弱いcontrastで静的に描く。animation loop、Canvas/WebGL、画像/フォント取得、追加package、AI実行は使用しない。実ブラウザーで描画時間・スクロール・見た目を確認し、所有者Windows/Safariの動作は別Gateのまま。

CI artifactは明示した4枚の合成PNGだけを1日保存する：overview-mobile.png / connections-desktop.png（既存）、overview-desktop.png / overview-locked.png（追加）。private profile、DB、key、trace、raw exportはartifactに含めない。Desktop PNGは1440×1000のviewport、mobile PNGは既存390pxのfull page。実機WindowsやSafariの結果ではない。

今後のUI課題：所有者による世界観レビュー、中央核/文字量のバランス、mobileの情報優先順位、全ページの密度調整、実機ブラウザー/assistive technologyの追加確認。機能追加や未検証Gate解除とは別の作業として扱う。

最初のUI source 2e5e82c27bcf79a900cab231820459ccea3bee9cのrun38199394107は5/5 PASS（DOM23/build/Chromium5、backend既存件数）。画像確認で、unlock後のscroll位置によるdesktop画像先頭切れと、負のtopによる未focus skip linkのfull-page画像写り込みを確認した。追加DOM回帰を失敗再現してclip方式に修正し、focused link表示・画像先頭位置を追加Chromiumでassertする。既存評価を緩めず、仕上げHEADには別のCI証拠を要求する。

参考画像に合わせたsource 089463f023fea79ad3656a22ffc935c080d01ba3のrun38201611814は5/5 PASS（DOM26/build/Chromium5、backend既存件数）。画像確認で、既存の放射状ナビ補助線が白い空洞と発光diskを横切ることを確認した。追加のDOM条件を失敗再現し、放射線だけを廃止して周囲の点線軌道と6星ノードは保持した。5幅のChromium検証にも中心を横切る補助線ゼロを追加。仕上げHEADのCI/画像結果はDraft PRに記録し、前HEADのPASSを流用しない。

source a477117d69b31932b8599a3cac08e3c00773e978のrun38201877782は5/5 PASS（DOM26/build/Chromium5、backend既存件数）。その後、所有者が中心を黒にするよう指定したため、SVGの中心fillのみ#000へ変更した。DOMの黒い中心条件を修正前に失敗確認し、Chromiumでも5幅すべてで黒をassertする。白背景、発光disk、形状、操作、安全境界の条件は維持。今回HEADのCI/画像は別に検証してDraft PRに記録する。

円を拡大したsource 9eb83d42a8c9631ce3859c4816472e2a652c0dbdのrun38204909543は5/5 PASS（DOM26/build/Chromium5、輪の実直径/既存backend件数）。画像で発光disk両端の切断を確認したため、追加DOM回帰を失敗確認して両端10%のsoft maskを追加した。5幅の実ブラウザーでもsoft maskを要求し、輪の最低直径と既存操作条件は維持。仕上げHEADのCI/画像を別に検証する。

巨大なgravity fieldを導入したsource a119995642cd8c4dfa85e1d26ea716203e0197e2のrun38207186867は5/5 PASS（DOM27/build/Chromium5、backend既存件数）。画像でfield上下の切断、captionとmetricへの接近、黒い中心を横断する点線を確認した。追加DOM回帰を失敗確認して縦横fadeのintersectとscene内caption配置を固定し、点線nav ellipseは表示せず独自のinflow軌道を使用する。5幅のブラウザー検証にも同条件を追加。既存の直径/操作/機能Gateは維持し、仕上げHEADのCI/画像を別に検証する。
