# 海日和 / OpenWeather

Open-Meteo の公開気象・海象データを利用する洋上向け日本語サイト。APIキー不要。相模湾沖など8海域の有義波高・波周期・波向・海面水温、時間別の波予報、洋上気象の24時間／7日間予報に対応。外部フォント・ライブラリ不要。

## 起動

```sh
cd /workspace/OpenWeather
python3 -m http.server 3000 --bind 0.0.0.0
```

静的サイトのため依存関係のインストールやビルドは不要。通常の静的ホスティングにも配置可能。

## 検証

```sh
node --test tests/weather.test.mjs
```

ブラウザでは海域変更、更新、通信失敗時の再試行を確認してください。API通信先 `api.open-meteo.com` と `marine-api.open-meteo.com` へのHTTPSアクセスが必要です。

## データ

[Open-Meteo](https://open-meteo.com/) / [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。現在値は気象モデルによる推定で、現地観測値とは異なります。時刻は日本時間。非商用の無料APIを使用しており、商用利用前に提供元の利用条件を確認してください。航海・防災判断には使用せず、気象庁の海上警報や海上保安庁の航行情報を確認してください。潮汐・潮流・警報は提供していません。海域は代表座標であり、航路全域の状況を表しません。

## この環境での検証状況

ユニットテスト4件と、模擬API応答によるブラウザ操作（海象値、予報、海域変更、選択保存、モバイル幅、通信失敗・再試行）を検証。相模湾沖の実API（気象・海象）の取得も確認済み。実VMでのHTTPS配信確認は別途必要です。

## Oracle Cloudへの自動反映

配信設定は [oracle-cloud-deploy](https://github.com/UeEmon/oracle-cloud-deploy) で管理します。VMの既存更新タイマーが5分ごとにmainを取得し、`weather.<CHUCK_DOMAIN>` に配信します。認証には既存のCHUCK管理サイトのユーザー名・パスワードを使用します。
