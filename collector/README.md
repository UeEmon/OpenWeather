# 共通気象・海象データAPI

外部サービスの取得はこのコンテナが担当します。各システムは保存済みデータだけを読みます。HTTPリクエストを受けても外部サービスへ再取得しません。

現在の収集元はOpen-Meteo Weather / Marine（モデル予報）です。気象庁・NOWPHAS・Copernicus等は未接続で、今後別のアダプターとして追加する想定です。

## 動作

- 起動直後と以後30分ごとに、areas.jsonの8海域×気象・海象の16データセットを収集。並列数2、各通信20秒まで。失敗時は次周期に再試行します。
- SQLiteの名前付きボリュームへ正常なスナップショットを保存。不完全な応答・現在値が6時間以上ずれた応答は保存しません。
- 更新失敗時は最後の正常データを保持。初回未取得は503、古い保存値は200と `_meta.stale=true` を返します。UIは更新失敗・古いデータを表示します。
- APIキー不要。無料APIは非商用向け。再利用時はOpen-Meteo / CC BY 4.0の出典表示が必要です。商用利用のAPI条件は別途確認してください。

## API v1

同一Composeネットワーク内の各システムは `http://ocean-data:8080` を接続先にします。ホストへのポート公開はありません。ブラウザは既存Caddyの認証を通った同一オリジン `/api/v1/...` を使います。内部ネットワークを信頼境界とし、別VMへ公開する場合は認証・TLSを追加してください。

| パス | 内容 |
|---|---|
| `/api/v1/areas` | 海域ID、名称、緯度経度 |
| `/api/v1/weather?area=tokyo` | 気象の現在・時間別・日別 |
| `/api/v1/marine?area=tokyo` | 海象の現在・時間別 |
| `/api/v1/status` | 全データセットの収集状態（常に200、readyで判定） |
| `/health` | プロセス生存確認（200） |
| `/ready` | 全16データセットが取得済みかつ期限内なら200、それ以外503 |

既存のOpen-Meteo JSON構造を保持し、`_meta` に `provider`, `license`, `area`, `source_url`, `fetched_at`（UTC）, `age_seconds`, `stale`, `last_collection_failed` を付加します。データ内時刻は日本時間です。APIで受け付けるのは登録済み海域のみです。任意URLや任意座標の取得は行いません。

収集済みAPIの例:

```sh
curl --fail 'http://ocean-data:8080/api/v1/marine?area=tokyo'
```

別Composeプロジェクトからは、明示的に同じDockerネットワークへ参加させてください。APIの有無だけでなく、503・stale・収集時刻を処理してください。

## 設定・検証

- `DATA_PATH`（既定 `/data/ocean.sqlite3`）
- `PORT`（既定8080）
- `COLLECT_INTERVAL_SECONDS`（既定1800、最小300）
- stale判定は収集周期の2倍または3600秒の大きい方です。

```sh
python3 -m unittest discover -s collector/tests -v
```

TLS証明書検証は有効です。プロキシを使う環境では標準のHTTPS_PROXY・NO_PROXYと信頼CAをコンテナへ設定してください。CAや秘密の値をイメージへ焼き込まないでください。

Oracle配信側では `ocean-data` ボリュームも既存の日次バックアップ対象に追加しています。SQLite backup APIで一貫したコピーを作成します。復旧する場合は収集サービスを停止してDBをボリュームへ戻し、再起動後 `/ready` を確認してください。停止中に不足したデータは再収集されます。
