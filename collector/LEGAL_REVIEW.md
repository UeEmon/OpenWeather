# 取得・加工・再配布条件の確認台帳

確認日：2026-11-07（日本時間）。これは当該実装のための公式利用条件の照合記録です。第三者データの条件を提供元全体へ一般化しません。原文・対象製品・利用形態が変わった場合は再確認します。機械可読台帳は `sources.json`、利用者向けAPIは `/api/v1/sources` です。

## 有効にしたデータ

### Open-Meteo Weather / Marine

根拠：公式README（https://github.com/open-meteo/open-meteo#readme）、利用条件（https://open-meteo.com/en/terms）。今回、公式Web規約ページは403でしたが、公式リポジトリでCC BY 4.0および無料APIの非商用条件を確認しました。無料APIの最新の詳細上限・商用契約条件まで確認できたとは扱いません。

- データの複製・加工・再配布：CC BY 4.0の表示条件付き。
- 商用取得：無料APIの非商用条件とは別。商用運用前に契約・接続先・クォータを確認すること。
- 本実装では既存の非商用向け無料接続を継続。外部APIキーは埋め込まない。
- 出典：`Weather data by Open-Meteo / CC BY 4.0`。元データのJSON構造を保持し、追加メタデータを明示。

### 気象庁の長期Atomフィード（海上図・台風電文索引）

根拠：
- https://www.jma.go.jp/jma/kishou/info/coment.html
- https://www.digital.go.jp/resources/open_data/public_data_license_v1.0
- https://xml.kishou.go.jp/xmlpull.html
- https://xml.kishou.go.jp/considerationforxml.pdf

PDL1.0は商用利用・複製・公衆送信・加工を原則許可。出典、加工の主体・内容を明示し、第三者権利・個別法令・別規約を除外します。XMLの第三者提供は気象業務法の趣旨に反しない限り原則制限なしと明記。ただし、警報の本質を損なう編集、値を変更した独自予報は行いません。

本実装は原文のタイトル・概要・発表時刻・原文リンクを抽出してJSON化します。現在有効な警報の一覧や「警報なし」の判定は提供しません。本文電文・予報数値を再計算しません。出典・加工責任をレスポンスと画面に表示します。台風関連索引にも解除・過去電文が含まれ得ます。

### NOAA OISST v2.1 Final（特定のERDDAPデータセット）

根拠：
- https://coastwatch.pfeg.noaa.gov/erddap/info/ncdcOisst21Agg_LonPM180/index.json
- https://coastwatch.pfeg.noaa.gov/erddap/legal.html#dataLicenses

当該 `NC_GLOBAL.license` には `The data may be used and redistributed for free` と明記。一般的なERDDAPの可否ではなく、この製品の条件で判断しました。出典・対象時刻・抽出者を表示し、公式の保証や推薦を示唆しません。最終解析はNRT版から約2週間遅れです。「現在の水温」「実測値」には変換せず、遅延した日別確定解析として別APIで提供します。

## 無効のまま残すデータ

| データ | 現時点の条件確認・有効化前の残件 |
|---|---|
| NOWPHAS | 利用上の注意 https://nowphas.mlit.go.jp/info/ が503。個別データの再配布・自動取得条件を確認できていない |
| 海上保安庁 海洋速報 | https://www1.kaiho.mlit.go.jp/copyright.html では一般に商用・加工・再配布可。第三者権利・別規約・水路業務法25条を除外。個別GISデータの権利、休止状況、配布仕様確認待ち |
| Copernicus Marine | https://marine.copernicus.eu/user-corner/service-commitments-and-licence の2.2で加工物・原形の再配布を許可。対象製品の指定、製品別クレジット、アカウント・認証の確認待ち。認証情報は転送・再配布しない |
| NOAA NOMADS GFS Wave | https://www.weather.gov/disclaimer の一般条件は原則public domain（例外あり）。対象GRIB2製品の第三者表示、取得仕様、デコード検証が残る |
| JCOPE | https://www.jamstec.go.jp/jcope/ は試験公開と参照時クレジットを明記。生データの商用・自動取得・再配布の包括許諾を確認できていない |
| JODC | https://www.jodc.go.jp/ が503。データセットと個別条件の確認待ち |

未確認ソースを自動で有効化しません。収集コードは `enabled=true` と `approved_with_conditions` の両方を要求します。新規追加時は製品、権利主体、規約URL、商用／再配布／加工の可否、出典、更新周期とクォータ、確認日、必要な許諾を台帳に記載し、アダプターと失敗時のテストを加えます。

## GISの表示データとソフトウェア

- CesiumJS 1.133.0：Apache-2.0。npmレジストリの配布integrityを照合して同梱し、元のLICENSE・第三者ライセンス関連ファイルを保持。Cesium ionの地形・海底製品のライセンスとは別です。ionアカウント・トークン・World Terrain・World Bathymetryは現状使いません。
- OpenStreetMap：ODbL、https://www.openstreetmap.org/copyright 。タイル利用方針 https://operations.osmfoundation.org/policies/tiles/ を確認。画面に出典を表示し、ブラウザで閲覧中のタイルだけを通常キャッシュで取得。事前一括取得・オフラインパックを作りません。Referrer-Policyをstrict-origin-when-cross-originとし、外部タイルへRefererのoriginを送信します。タイルには稼働保証がなく、負荷増大時は独自・契約プロバイダーへ切り替えます。
- 国土地理院 DEM10B PNG： https://maps.gsi.go.jp/development/ichiran.html と https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html を確認。タイルのリアルタイム読み込みは出典表示で申請不要と明記。PDL1.0、出典と3D変換した主体を表示。DEMの提供範囲のみを使用し、他機関の全球DEMや海底データを混用しません。テキストDEMは2024年10月から更新停止のため、PNGを使います。
- 日本のDEM提供範囲外・欠測・海面は平坦な代替表示。海底地形を取得したとは表示しません。
- Mapzen Terrain Tilesは複数の権利主体・個別条件があるため、包括許諾と推定せず未採用です。

地図タイルは対話表示に必要なものをブラウザが直接取得します。定期的に収集・保存する気象・海象データAPIとは用途を分け、禁止されている地図タイルの定期一括収集は行いません。
