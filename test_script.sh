#!/bin/bash

# テスト用の一時ディレクトリ
TEST_DIR="/tmp/jobq_test"
export JOB_QUEUE_DIR="$TEST_DIR"

# クリーンアップ関数
cleanup() {
    rm -rf "$TEST_DIR"
}

# 初期化
trap cleanup EXIT
mkdir -p "$TEST_DIR"

echo "=== jobq テスト開始 ==="

# 1. ジョブ追加テスト
echo -e "\n[1] ジョブ追加"
./jobq.py add echo "テスト1"
./jobq.py add sleep 2
./jobq.py add echo "テスト2"

# 2. 一覧表示
echo -e "\n[2] ジョブ一覧"
./jobq.py list

# 3. ジョブ実行
echo -e "\n[3] ジョブ実行"
./jobq.py run
sleep 3

# 4. 詳細表示（最初のジョブ）
echo -e "\n[4] ジョブ詳細"
JOB_ID=$(./jobq.py list --all | grep "completed" | head -1 | awk '{print $1}')
if [ -n "$JOB_ID" ]; then
    ./jobq.py detail "$JOB_ID"
fi

# 5. 全ジョブ実行
echo -e "\n[5] 残りのジョブを実行"
./jobq.py run
sleep 1
./jobq.py run

# 6. 全ジョブ表示
echo -e "\n[6] 全ジョブ（完了含む）"
./jobq.py list --all

# 7. クリーンアップテスト
echo -e "\n[7] クリーンアップ"
./jobq.py clean --keep-days 0

echo -e "\n=== テスト完了 ==="
