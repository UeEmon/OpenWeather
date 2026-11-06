# 共通気象・海象データAPI

外部サービスの取得はこのコンテナが担当します。各システムは保存済みデータだけを読みます。HTTPリクエストを受けても外部サービスへ再取得しません。

収集元はOpen-Meteo Weather / Marine（モデル予報）、気象庁の海上図・台風電文の索引、NOAA OISST v2.1 Final（日別確定解析）です。未確認のNOWPHAS等は無効のままです。[条件確認台帳](LEGAL_REVIEW.md)と[データ別取得時刻](SCHEDULES.md)を参照してください。

## 動作

- データごとの予定に従って収集。既定8海域に加え、ユーザーが最大24海域を保存可能。並列数2、各通信最大25秒。失敗時は指数バックオフ。予定をSQLiteへ保存し、再起動でも継続します。
- SQLiteの名前付きボリュームへ正常なスナップショットを保存。不完全な応答・現在値が6時間以上ずれた応答は保存しません。
- 更新失敗時は最後の正常データを保持。初回未取得は503、古い保存値は200と `_meta.stale=true` を返します。UIは更新失敗・古いデータを表示します。
- APIキー不要。無料APIは非商用向け。再利用時はOpen-Meteo / CC BY 4.0の出典表示が必要です。商用利用のAPI条件は別途確認してください。

## API v1

同一Composeネットワーク内の各システムは `http://ocean-data:8080` を接続先にします。ホストへのポート公開はありません。ブラウザは既存Caddyの認証を通った同一オリジン `/api/v1/...` を使います。内部ネットワークを信頼境界とし、別VMへ公開する場合は認証・TLSを追加してください。

| パス | 内容 |
|---|---|
| `/api/v1/areas` | GET: 海域一覧。POST: nameとbounds（south/west/north/east）で共有海域を追加 |
| `/api/v1/areas/{id}` | DELETE: ユーザー追加海域を削除（既定海域は削除不可） |
| `/api/v1/sources` | データ源の再利用条件・更新周期・有効化状態 |
| `/api/v1/sst-analysis?area=tokyo` | NOAAの約2週間遅れの日別確定海面水温解析 |
| `/api/v1/jma-marine-bulletins` | 気象庁の海上図電文索引（警報の有効性は判定しない） |
| `/api/v1/jma-typhoon-bulletins` | 気象庁の台風関連電文索引 |
| `/api/v1/weather?area=tokyo` | 気象の現在・時間別・日別 |
| `/api/v1/marine?area=tokyo` | 海象の現在・時間別 |
| `/api/v1/status` | 全データセットの収集状態（常に200、readyで判定） |
| `/health` | プロセス生存確認（200） |
| `/ready` | 全有効データセットが取得済みかつ期限内なら200、それ以外503 |

既存のOpen-Meteo JSON構造を保持し、`_meta` に `provider`, `license`, `area`, `source_url`, `fetched_at`（UTC）, `age_seconds`, `stale`, `last_collection_failed` を付加します。データ内時刻は日本時間です。APIで受け付けるのは登録済み海域のみです。任意URLや任意座標の取得は行いません。

収集済みAPIの例:

```sh
curl --fail 'http://ocean-data:8080/api/v1/marine?area=tokyo'
```

別Composeプロジェクトからは、明示的に同じDockerネットワークへ参加させてください。APIの有無だけでなく、503・stale・収集時刻を処理してください。

## 設定・検証

- `DATA_PATH`（既定 `/data/ocean.sqlite3`）
- `PORT`（既定8080）
- 取得周期・時刻はsources.jsonでデータ別に設定（SCHEDULES.md参照）
- stale判定は収集周期の2倍または3600秒の大きい方です。

```sh
python3 -m unittest discover -s collector/tests -v
```

TLS証明書検証は有効です。プロキシを使う環境では標準のHTTPS_PROXY・NO_PROXYと信頼CAをコンテナへ設定してください。CAや秘密の値をイメージへ焼き込まないでください。

Oracle配信側では `ocean-data` ボリュームも既存の日次バックアップ対象に追加しています。SQLite backup APIで一貫したコピーを作成します。復旧する場合は収集サービスを停止してDBをボリュームへ戻し、再起動後 `/ready` を確認してください。停止中に不足したデータは再収集されます。

共有海域は同じ認証を持つ利用者全員から参照・削除できます。個人別の所有権・権限管理はまだありません。範囲中心点の代表値を収集し、範囲全体の格子データは取得しません。日付変更線をまたぐ海域は分割し、1海域の東西幅は180度以内にしてください。

## 時間窓

`GET /api/v1/weather?area=tokyo&window=history`（またはmarine）で過去12時間〜現在の毎時モデル値、`window=24` / `window=36` で現在から先の24/36時間の毎時予報を返します。時間窓はhourlyに適用し、currentとdailyは既存構造を保持します。`_window` に対象期間・サンプル数・モデル値である旨を付加します。欠測は補間・ゼロ埋めしません。取得元にはpast_hours=12を指定し、要求条件の変更時はスケジュールを待たず再取得します。

過去12時間分は観測された実況ではなくモデル値です。観測値を提供するデータ源を追加した際も別の出典・種別として扱い、モデル値を実測と表記しません。
