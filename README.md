# ジョブキューシステム

登録した順にコマンドを排他実行するシンプルなジョブキューシステム。
Python標準ライブラリのみで実装。

## 特徴

- 登録順にジョブを実行
- 同時に1つのジョブのみ実行（排他制御）
- ジョブの状態管理（pending, running, completed, failed）
- 実行ログの保存
- シャットダウン・再起動に対応

## セットアップ

```bash
# スクリプトをインストール
sudo cp job_queue.py /usr/local/bin/jobq
sudo chmod +x /usr/local/bin/jobq

# キューディレクトリを作成（オプション）
sudo mkdir -p /var/lib/jobq
sudo chown $USER:$USER /var/lib/jobq
```

## 基本的な使い方

### 1. ジョブを追加

```bash
# 引数なし
jobq add /opt/scripts/backup.sh

# 引数あり
jobq add python3 /opt/scripts/process.py --input data.csv --output result.txt

# 複数追加
jobq add /opt/scripts/script_a.sh
jobq add /opt/scripts/script_b.sh arg1 arg2
jobq add sleep 30
```

### 2. ジョブ一覧を表示

```bash
# 実行待ち・実行中のジョブを表示
jobq list

# 完了したジョブも含めて全て表示
jobq list --all
```

出力例：
```
ID               ステータス     登録日時              コマンド
--------------------------------------------------------------------------------
1736754123456789 pending      2026-01-13 10:15:23  /opt/scripts/backup.sh
1736754234567890 running      2026-01-13 10:17:14  python3 /opt/scripts/proces...
1736754345678901 pending      2026-01-13 10:19:05  sleep 30
```

### 3. ジョブの詳細を表示

```bash
jobq detail 1736754123456789
```

出力例：
```
ジョブID: 1736754123456789
コマンド: /opt/scripts/backup.sh
引数: (なし)
ステータス: completed
登録日時: 2026-01-13T10:15:23.456789
開始日時: 2026-01-13T10:15:24.567890
終了日時: 2026-01-13T10:18:45.678901
終了コード: 0

ログファイル: /var/lib/jobq/logs/1736754123456789.log
```

### 4. ジョブを実行

```bash
# 次のジョブを1つ実行
jobq run

# キューが空になるまで実行し続ける
jobq worker
```

### 5. ジョブを削除

```bash
# pending状態のジョブのみ削除可能
jobq remove 1736754123456789
```

### 6. 古いジョブをクリーンアップ

```bash
# 7日以上前の完了ジョブを削除
jobq clean

# 保持日数を指定
jobq clean --keep-days 30
```

### 7. キューの停止と再開

```bash
# キューを停止（runしても実行されない）
jobq stop

# キューを再開
jobq restart
```

## cronでの使用例

### 基本パターン: 毎分チェック＆実行

```cron
# 1分ごとにキューをチェックして1つ実行
* * * * * /usr/local/bin/jobq run
```

ジョブ追加例:
```bash
# 手動またはスクリプトからジョブを追加
jobq add /opt/scripts/backup.sh
jobq add python3 /opt/scripts/process.py
```

### パターン2: cron でジョブ追加＋自動実行

```cron
# ジョブを追加（実行はされない）
0 * * * * /usr/local/bin/jobq add /opt/scripts/backup.sh
30 2 * * * /usr/local/bin/jobq add /opt/scripts/daily_task.sh

# 毎分キューをチェックして実行
* * * * * /usr/local/bin/jobq run
```

### パターン3: systemdでワーカーを常駐

```ini
# /etc/systemd/system/jobq-worker.service
[Unit]
Description=Job Queue Worker
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/jobq worker
Restart=always
RestartSec=10
User=your-user

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable jobq-worker
sudo systemctl start jobq-worker
```

## ディレクトリ構造

```
/var/lib/jobq/
├── queue.json          # ジョブキューデータ
├── queue.lock          # 排他制御用ロックファイル
└── logs/               # 実行ログディレクトリ
    ├── 1736754123456789.log
    ├── 1736754234567890.log
    └── ...
```

## ジョブのステータス

- `pending`: 実行待ち
- `running`: 実行中
- `completed`: 正常終了（終了コード0）
- `failed`: エラー終了（終了コード非0）

## シャットダウン時の動作

- 実行中のジョブは`SIGTERM`で中断される
- ジョブのステータスは`running`のまま残る
- 再起動後、`run`または`worker`コマンドで次のpendingジョブが実行される
- 中断されたジョブは手動で削除するか、再度追加する

## トラブルシューティング

### 権限エラー

```bash
# キューディレクトリの所有者を確認
ls -ld /var/lib/jobq

# 所有者を変更
sudo chown -R $USER:$USER /var/lib/jobq
```

### ロックファイルが残っている

```bash
# プロセスが存在しない場合は安全に削除可能
rm /var/lib/jobq/queue.lock
```

### ログを確認

```bash
# 特定のジョブのログを表示
cat /var/lib/jobq/logs/1736754123456789.log

# 最新のログを表示
ls -lt /var/lib/jobq/logs/ | head -5
```

## カスタマイズ

### キューディレクトリを変更

```bash
jobq --queue-dir /home/user/my-queue add /opt/scripts/test.sh
```

環境変数で設定することも可能：

```bash
# ~/.bashrc
export JOB_QUEUE_DIR=/home/user/my-queue
```

スクリプト内で環境変数を読み込むように修正：

```python
queue_dir = os.getenv('JOB_QUEUE_DIR', '/var/lib/jobq')
```

## 高度な使用例

### 依存関係のあるジョブ

```bash
# スクリプトA実行後、スクリプトBを実行
jobq add bash -c "/opt/scripts/script_a.sh && /usr/local/bin/jobq add /opt/scripts/script_b.sh"
```

### 失敗時のリトライ

```bash
# リトライ用のラッパースクリプト
#!/bin/bash
# /opt/scripts/retry_wrapper.sh
MAX_RETRY=3
COUNT=0

while [ $COUNT -lt $MAX_RETRY ]; do
    if "$@"; then
        exit 0
    fi
    COUNT=$((COUNT + 1))
    echo "リトライ $COUNT/$MAX_RETRY..."
    sleep 10
done

exit 1
```

```bash
jobq add /opt/scripts/retry_wrapper.sh /opt/scripts/unstable_script.sh
```
