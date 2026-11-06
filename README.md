# 海日和 / OpenWeather

Open-Meteo の公開気象・海象データを利用する洋上向け日本語サイト。APIキー不要。相模湾沖など8海域の有義波高・波周期・波向・海面水温、時間別の波予報、洋上気象の24時間／7日間予報に対応。外部フォント・ライブラリ不要。

## 起動

```sh
cd /workspace/OpenWeather
docker compose up -d --build
```

ローカルの3000番ポートで、Webと共通収集APIを同時起動します。収集コンテナは外部データを取得しSQLiteへ保存します。初回取得の完了まではAPIが503を返すため、少し待って更新してください。Pythonの静的HTTPサーバー単独ではAPIがないため予報を表示できません。

API仕様・各システムからの接続方法は [collector/README.md](collector/README.md) を参照してください。

## 検証

```sh
node --test tests/weather.test.mjs
python3 -m unittest discover -s collector/tests -v
```

ブラウザでは海域変更、更新、通信失敗時の再試行を確認してください。収集コンテナから `api.open-meteo.com` と `marine-api.open-meteo.com` へのHTTPSアクセスが必要です。ブラウザは同一オリジンの共通APIだけに接続します。

## データ

[Open-Meteo](https://open-meteo.com/) / [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。現在値は気象モデルによる推定で、現地観測値とは異なります。時刻は日本時間。非商用の無料APIを使用しており、商用利用前に提供元の利用条件を確認してください。航海・防災判断には使用せず、気象庁の海上警報や海上保安庁の航行情報を確認してください。潮汐・潮流・警報は提供していません。海域は代表座標であり、航路全域の状況を表しません。

## この環境での検証状況

Webのテスト5件・収集APIのテスト4件と、模擬API応答によるブラウザ操作（海象値、予報、海域変更、選択保存、モバイル幅、通信失敗・再試行）を検証。相模湾沖の実API（気象・海象）の取得も確認済み。実VMでのHTTPS配信確認は別途必要です。

## Oracle Cloudへの自動反映

配信設定は [oracle-cloud-deploy](https://github.com/UeEmon/oracle-cloud-deploy) で管理します。VMの既存更新タイマーが5分ごとにmainを取得し、`weather.<CHUCK_DOMAIN>` に配信します。認証には既存のCHUCK管理サイトのユーザー名・パスワードを使用します。
