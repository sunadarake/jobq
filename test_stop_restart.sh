#!/bin/bash

# テスト用の一時ディレクトリ
TEST_DIR="/tmp/jobq_test_stop"
export JOB_QUEUE_DIR="$TEST_DIR"

# クリーンアップ
cleanup() {
    rm -rf "$TEST_DIR"
}

trap cleanup EXIT
mkdir -p "$TEST_DIR"

echo "=== stop/restart テスト開始 ==="

# 1. ジョブ追加
echo -e "\n[1] テストジョブを追加"
./jobq.py add echo "テスト1"
./jobq.py add echo "テスト2"
./jobq.py add echo "テスト3"

# 2. 一覧表示
echo -e "\n[2] ジョブ一覧"
./jobq.py list

# 3. キューを停止
echo -e "\n[3] キューを停止"
./jobq.py stop

# 4. 停止中に実行を試みる
echo -e "\n[4] 停止中にrunを試みる（実行されないはず）"
./jobq.py run

# 5. 停止中の一覧表示
echo -e "\n[5] 停止中のジョブ一覧"
./jobq.py list

# 6. キューを再開
echo -e "\n[6] キューを再開"
./jobq.py restart

# 7. 再開後に実行
echo -e "\n[7] 再開後にrunを実行（正常に実行されるはず）"
./jobq.py run
sleep 1

# 8. 実行後の一覧表示
echo -e "\n[8] 実行後のジョブ一覧"
./jobq.py list --all

# 9. 残りのジョブも実行
echo -e "\n[9] 残りのジョブを実行"
./jobq.py run
sleep 1
./jobq.py run
sleep 1

# 10. 最終結果
echo -e "\n[10] 最終結果（全ジョブ）"
./jobq.py list --all

echo -e "\n=== テスト完了 ==="
