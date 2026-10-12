# White Space / White Singularity — UI base

2026-10-12。対象はARK Nexusだけ。UIの方向性を確認するアプリシェルで、V1公式完了・実形式対応・ユーザーWindows実機の証拠ではない。

## 現在の描画

所有者の追加指定「線の模様をなくし、写真のような質感にする」に合わせ、32/38本のSVG帯、12本のinflow線、固定粒子を廃止。Overviewの主役はローカルのWebGL2 fragment shaderに変更した。黒い中心、傾いた白い降着円盤、重力レンズ、ガスの濃淡を3D座標から描く。背景は単色白を維持する。

`singularity.frag.glsl`は200回を上限とする近似光線追跡、有限のガス体積、4段階の決定的noiseを用いる。光線の曲がりと体積内の吸収/発光が明暗と奥行きを作る。世界観を表現するartistic approximationであり、天体物理の計算証拠やAIの実行状態ではない。参考写真・poster・文字はpublic repoに追加しない。生成AIサービス、外部画像、外部font、追加package、3D libraryは使用しない。コードと描画検証用成果物はNexus workspace内に限定する。

`BlackHoleScene` / `singularityRenderer`を共通Hubから呼ぶ。通常は一度だけ描画し、animation loopは動かさない。サイズが変わった時だけ100ms debounceで再描画し、同じbufferサイズなら描画しない。最大900,000 pixels、DPR 1.25、1600×900以下。Overviewを離れた時に所有するshader/program/context、observer/listener/timerを解放する。

WebGL2未対応、compile/link/uniform/draw失敗、context lossでは簡素な黒いSVGとgas volumeへ戻す。これは写真相当の描画とは区別し、`data-renderer`がfallbackのままなら実shader PASSにしない。診断にGPU/driverの情報や例外本文を出さない。forced-colorsでは装飾を隠す。全体は静止画として成立し、reduced-motionでも使用できる。

## 操作・レイアウト

画面幅に近い最大1320px、高さ600pxのHubを6個の星ノードが囲む。mobileは390pxの描画領域の下に3列×2行の導線を表示する。黒い中心の拡大、縦横soft mask、captionのscene内配置を維持し、光でラベルを読めなくしない。GPU描画は画面の縦横比に応じてcamera focal lengthを調整し、狭い幅で核全体が切れないようにする。

他5画面では同じDOMのナビをコンパクトに表示する。native button、aria-current、navigation landmark、skip-to-main、focus-visible、44px以上のtargetを保持する。装飾SVG/canvasはaria-hidden・非focusable・pointer-events none。認証、CSRF header、session epoch、late-response rejection、import/search/project/paging handlersは変更しない。

4 metricは実際のAPI件数だけを表示し、取得前/lock後は「—」。API unavailable時は既存の取得時刻付きsnapshotとして扱う。synthetic-only / live sync off / V1 BLOCKEDを明示し、未接続の実アカウントやWorkタスクを取得済みと表示しない。

## 評価と証跡

既存のApp DOM20件、Chromium2シナリオ、backend/Linux/Windows Gateは保持。追加UI DOM8件は背景・soft mask・caption・黒いfallback・6導線・focus・未認証requestゼロ・未知件数を確認する。旧SVGのpath本数条件は、所有者が拒否した線を廃止するために変更した。写真の見え方をSVG path数でPASSにせず、実描画のpixel検証に置き換える。

新たなrenderer単体8件は、context拒否、compile/link/uniform失敗、buffer上限、idle中の重複描画なし、リソース解放、非有限寸法、context loss/draw失敗を確認する。uniform欠損、NaN/Infinity寸法、StrictModeのeffect再実行前にcontextを失う問題は追加テストで失敗を再現してから修正した。shader/programは毎回解放し、context自体はcanvasがDOMから外れた時だけ解放する。Vitest合計36件（DOM28 + renderer8）。

追加Chromium4シナリオで、locked状態の6導線/keyboard focus、320/390/768/1024/1440pxの全ページ操作とoverflow、実際の合成API/lock、実WebGL context lossとWebGL拒否時の操作を検証する。shaderが実際に動いたことを必須とし、framebufferの黒い領域/明るい光の割合とbuffer上限を検査する。黒い核の実pixel幅は5幅で120/150/220/275/275px以上（以前の輪の最低直径をそのまま維持し、枠やhidden SVGから計測しない）。fallbackはこれとは別に検証する。初回/resize後の実shader確認には20秒の上限を設け、既存の機能期待値/timeoutを緩めない。

実ブラウザー合計6シナリオ。Playwrightのsynthetic localhostテストだけは、GPUのないrunnerで[Chromium公式のSwiftShader flags](https://chromium.googlesource.com/chromium/src/+/main/docs/gpu/swiftshader.md)を指定する（確認日2026-10-12）。ownerのprivate browserへのflag設定は実装・推奨しない。最終HEADのCIと画像確認が終わるまでChromium PASSや参考画像への適合確認済みとはしない。ソフトウェアMesaによるworkspace内のoffscreen shader確認はコードの描画確認であり、ブラウザー/ユーザーWindows実機の結果ではない。ユーザーWindows/Safari/低性能GPUの性能は未検証。

CI artifactはallowlistの4枚の合成PNGだけを1日保存：overview-mobile.png / connections-desktop.png / overview-desktop.png / overview-locked.png。実shaderの完了後にdesktop1440×1000とmobile390px full-pageを保存する。DB/key/private profile/trace/raw exportはartifactに含めない。現在HEADのCI URL・結果はDraft PR #1に記録する。

次のUI課題は所有者による質感レビュー、実機GPUの初回描画時間、mobileの余白と情報密度、他5ページのデザイン細部。実形式AdapterとWindows owner Gateは引き続きBLOCKED/NOT RUN。

## 以前の検証履歴（現在HEADのPASSには流用しない）

最初のUI source 2e5e82c27bcf79a900cab231820459ccea3bee9cのrun38199394107は5/5 PASS（DOM23/build/Chromium5、backend既存件数）。画像確認で、unlock後のscroll位置によるdesktop画像先頭切れと、負のtopによる未focus skip linkのfull-page画像写り込みを確認した。追加DOM回帰を失敗再現してclip方式に修正し、focused link表示・画像先頭位置を追加Chromiumでassertする。既存評価を緩めず、仕上げHEADには別のCI証拠を要求する。

参考画像に合わせたsource 089463f023fea79ad3656a22ffc935c080d01ba3のrun38201611814は5/5 PASS（DOM26/build/Chromium5、backend既存件数）。画像確認で、既存の放射状ナビ補助線が白い空洞と発光diskを横切ることを確認した。追加のDOM条件を失敗再現し、放射線だけを廃止して周囲の点線軌道と6星ノードは保持した。5幅のChromium検証にも中心を横切る補助線ゼロを追加。仕上げHEADのCI/画像結果はDraft PRに記録し、前HEADのPASSを流用しない。

source a477117d69b31932b8599a3cac08e3c00773e978のrun38201877782は5/5 PASS（DOM26/build/Chromium5、backend既存件数）。その後、所有者が中心を黒にするよう指定したため、SVGの中心fillのみ#000へ変更した。DOMの黒い中心条件を修正前に失敗確認し、Chromiumでも5幅すべてで黒をassertする。白背景、発光disk、形状、操作、安全境界の条件は維持。今回HEADのCI/画像は別に検証してDraft PRに記録する。

円を拡大したsource 9eb83d42a8c9631ce3859c4816472e2a652c0dbdのrun38204909543は5/5 PASS（DOM26/build/Chromium5、輪の実直径/既存backend件数）。画像で発光disk両端の切断を確認したため、追加DOM回帰を失敗確認して両端10%のsoft maskを追加した。5幅の実ブラウザーでもsoft maskを要求し、輪の最低直径と既存操作条件は維持。仕上げHEADのCI/画像を別に検証する。

巨大なgravity fieldを導入したsource a119995642cd8c4dfa85e1d26ea716203e0197e2のrun38207186867は5/5 PASS（DOM27/build/Chromium5、backend既存件数）。画像でfield上下の切断、captionとmetricへの接近、黒い中心を横断する点線を確認した。追加DOM回帰を失敗確認して縦横fadeのintersectとscene内caption配置を固定し、点線nav ellipseは表示せず独自のinflow軌道を使用する。5幅のブラウザー検証にも同条件を追加。既存の直径/操作/機能Gateは維持し、仕上げHEADのCI/画像を別に検証する。
