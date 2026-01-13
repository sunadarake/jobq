#!/usr/bin/env python3
"""
ジョブキューシステム - 登録した順にコマンドを排他実行
標準ライブラリのみで実装
"""

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


class JobQueue:
    def __init__(self, queue_dir="~/.jobq"):
        self.queue_dir = Path(queue_dir)
        self.queue_file = self.queue_dir / "jobq.json"
        self.lock_file = self.queue_dir / "jobq.lock"
        self.log_dir = self.queue_dir / "logs"

        # ディレクトリ作成
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)

        # キューファイルの初期化
        if not self.queue_file.exists():
            self._save_queue([])

    def _acquire_lock(self, fd, blocking=True):
        """ファイルロックを取得"""
        try:
            if blocking:
                fcntl.flock(fd, fcntl.LOCK_EX)
            else:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False

    def _release_lock(self, fd):
        """ファイルロックを解放"""
        fcntl.flock(fd, fcntl.LOCK_UN)

    def _load_queue(self):
        """キューを読み込む"""
        try:
            with open(self.queue_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_queue(self, queue):
        """キューを保存"""
        with open(self.queue_file, "w") as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)

    def add(self, command, args=None):
        """ジョブをキューに追加"""
        job = {
            "id": int(time.time() * 1000000),  # マイクロ秒でユニークID
            "command": command,
            "args": args or [],
            "status": "pending",
            "registered_at": datetime.now().isoformat(),
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
        }

        # ロックを取得してキューに追加
        with open(self.lock_file, "w") as lock_fd:
            self._acquire_lock(lock_fd.fileno())
            try:
                queue = self._load_queue()
                queue.append(job)
                self._save_queue(queue)
                print(f"ジョブを追加しました: ID={job['id']}")
                print(f"コマンド: {command} {' '.join(args or [])}")
                return job["id"]
            finally:
                self._release_lock(lock_fd.fileno())

    def list(self, show_all=False):
        """ジョブ一覧を表示"""
        queue = self._load_queue()

        if not queue:
            print("キューは空です")
            return

        # フィルタリング
        if not show_all:
            queue = [j for j in queue if j["status"] in ["pending", "running"]]

        if not queue:
            print("表示するジョブがありません（--all で全ジョブを表示）")
            return

        # ヘッダー
        print(f"{'ID':<16} {'ステータス':<10} {'登録日時':<20} {'コマンド'}")
        print("-" * 80)

        # ジョブ表示
        for job in queue:
            job_id = str(job["id"])
            status = job["status"]
            registered = job["registered_at"][:19]  # 秒まで
            command = job["command"]
            args_str = " ".join(job["args"])
            cmd_display = f"{command} {args_str}".strip()

            # 長いコマンドは省略
            if len(cmd_display) > 40:
                cmd_display = cmd_display[:37] + "..."

            print(f"{job_id:<16} {status:<10} {registered:<20} {cmd_display}")

    def detail(self, job_id):
        """ジョブの詳細を表示"""
        queue = self._load_queue()
        job = next((j for j in queue if j["id"] == job_id), None)

        if not job:
            print(f"ジョブ ID {job_id} が見つかりません")
            return

        print(f"ジョブID: {job['id']}")
        print(f"コマンド: {job['command']}")
        print(f"引数: {' '.join(job['args']) if job['args'] else '(なし)'}")
        print(f"ステータス: {job['status']}")
        print(f"登録日時: {job['registered_at']}")
        print(f"開始日時: {job['started_at'] or '(未実行)'}")
        print(f"終了日時: {job['finished_at'] or '(未完了)'}")
        print(
            f"終了コード: {job['exit_code'] if job['exit_code'] is not None else '(未完了)'}"
        )

        # ログファイルがあれば表示
        log_file = self.log_dir / f"{job['id']}.log"
        if log_file.exists():
            print(f"\nログファイル: {log_file}")

    def remove(self, job_id):
        """ジョブをキューから削除（pending のみ）"""
        with open(self.lock_file, "w") as lock_fd:
            self._acquire_lock(lock_fd.fileno())
            try:
                queue = self._load_queue()
                job = next((j for j in queue if j["id"] == job_id), None)

                if not job:
                    print(f"ジョブ ID {job_id} が見つかりません")
                    return False

                if job["status"] != "pending":
                    print(
                        f"ジョブ ID {job_id} は削除できません（ステータス: {job['status']}）"
                    )
                    return False

                queue = [j for j in queue if j["id"] != job_id]
                self._save_queue(queue)
                print(f"ジョブ ID {job_id} を削除しました")
                return True
            finally:
                self._release_lock(lock_fd.fileno())

    def run_next(self):
        """キューから次のジョブを実行"""
        with open(self.lock_file, "w") as lock_fd:
            # 非ブロッキングでロック取得を試みる
            if not self._acquire_lock(lock_fd.fileno(), blocking=False):
                print("別のジョブが実行中です")
                return False

            try:
                queue = self._load_queue()

                # pending状態の最初のジョブを取得
                job = next((j for j in queue if j["status"] == "pending"), None)

                if not job:
                    print("実行するジョブがありません")
                    return False

                # ステータスを更新
                job["status"] = "running"
                job["started_at"] = datetime.now().isoformat()
                self._save_queue(queue)

                # ジョブ実行
                job_id = job["id"]
                command = [job["command"]] + job["args"]
                log_file = self.log_dir / f"{job_id}.log"

                print(f"ジョブ ID {job_id} を実行中...")
                print(f"コマンド: {' '.join(command)}")
                print(f"ログ: {log_file}")

                # コマンド実行
                try:
                    with open(log_file, "w") as log_fd:
                        result = subprocess.run(
                            command, stdout=log_fd, stderr=subprocess.STDOUT, text=True
                        )
                    exit_code = result.returncode
                    status = "completed" if exit_code == 0 else "failed"
                except Exception as e:
                    exit_code = -1
                    status = "failed"
                    with open(log_file, "a") as log_fd:
                        log_fd.write(f"\nエラー: {str(e)}\n")

                # ステータス更新
                queue = self._load_queue()
                for j in queue:
                    if j["id"] == job_id:
                        j["status"] = status
                        j["finished_at"] = datetime.now().isoformat()
                        j["exit_code"] = exit_code
                        break
                self._save_queue(queue)

                print(f"ジョブ ID {job_id} が終了しました（終了コード: {exit_code}）")
                return True

            finally:
                self._release_lock(lock_fd.fileno())

    def worker(self):
        """ワーカーモード: キューが空になるまで実行し続ける"""
        print("ワーカーモード開始...")

        while True:
            result = self.run_next()
            if not result:
                # キューが空か、別のワーカーが実行中
                time.sleep(1)

                # キューが空か確認
                queue = self._load_queue()
                pending = [j for j in queue if j["status"] == "pending"]
                if not pending:
                    print("キューが空になりました")
                    break

    def clean(self, keep_days=7):
        """完了したジョブをクリーンアップ"""
        cutoff_time = time.time() - (keep_days * 86400)

        with open(self.lock_file, "w") as lock_fd:
            self._acquire_lock(lock_fd.fileno())
            try:
                queue = self._load_queue()

                # 古い完了ジョブを削除
                new_queue = []
                removed_count = 0

                for job in queue:
                    if job["status"] in ["completed", "failed"]:
                        finished_time = datetime.fromisoformat(
                            job["finished_at"]
                        ).timestamp()
                        if finished_time < cutoff_time:
                            # ログファイルも削除
                            log_file = self.log_dir / f"{job['id']}.log"
                            if log_file.exists():
                                log_file.unlink()
                            removed_count += 1
                            continue

                    new_queue.append(job)

                self._save_queue(new_queue)
                print(
                    f"{removed_count} 個のジョブを削除しました（{keep_days}日以上前の完了ジョブ）"
                )

            finally:
                self._release_lock(lock_fd.fileno())


def main():
    parser = argparse.ArgumentParser(
        description="ジョブキューシステム - コマンドを登録順に排他実行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブを追加
  %(prog)s add /opt/scripts/backup.sh
  %(prog)s add python3 /opt/scripts/process.py --input data.csv

  # 一覧表示
  %(prog)s list
  %(prog)s list --all  # 全ジョブ（完了済み含む）

  # 次のジョブを実行
  %(prog)s run

  # ワーカーモード（キューが空になるまで実行）
  %(prog)s worker

  # ジョブ詳細
  %(prog)s detail <job_id>

  # ジョブ削除（pending のみ）
  %(prog)s remove <job_id>

  # クリーンアップ（7日以上前の完了ジョブを削除）
  %(prog)s clean
        """,
    )

    parser.add_argument(
        "--queue-dir",
        default="/var/lib/job-queue",
        help="キューディレクトリ（デフォルト: /var/lib/job-queue）",
    )

    subparsers = parser.add_subparsers(dest="command", help="サブコマンド")

    # add サブコマンド
    add_parser = subparsers.add_parser("add", help="ジョブを追加")
    add_parser.add_argument("script", help="実行するコマンド/スクリプト")
    add_parser.add_argument("args", nargs="*", help="コマンドの引数")

    # list サブコマンド
    list_parser = subparsers.add_parser("list", help="ジョブ一覧を表示")
    list_parser.add_argument(
        "--all", action="store_true", help="全ジョブを表示（完了済み含む）"
    )

    # detail サブコマンド
    detail_parser = subparsers.add_parser("detail", help="ジョブの詳細を表示")
    detail_parser.add_argument("job_id", type=int, help="ジョブID")

    # remove サブコマンド
    remove_parser = subparsers.add_parser("remove", help="ジョブを削除（pending のみ）")
    remove_parser.add_argument("job_id", type=int, help="ジョブID")

    # run サブコマンド
    run_parser = subparsers.add_parser("run", help="次のジョブを実行")

    # worker サブコマンド
    worker_parser = subparsers.add_parser(
        "worker", help="ワーカーモード（キューが空になるまで実行）"
    )

    # clean サブコマンド
    clean_parser = subparsers.add_parser("clean", help="古い完了ジョブを削除")
    clean_parser.add_argument(
        "--keep-days", type=int, default=7, help="保持する日数（デフォルト: 7）"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # JobQueueインスタンス作成
    queue = JobQueue(args.queue_dir)

    # コマンド実行
    if args.command == "add":
        queue.add(args.script, args.args)
    elif args.command == "list":
        queue.list(show_all=args.all)
    elif args.command == "detail":
        queue.detail(args.job_id)
    elif args.command == "remove":
        queue.remove(args.job_id)
    elif args.command == "run":
        queue.run_next()
    elif args.command == "worker":
        queue.worker()
    elif args.command == "clean":
        queue.clean(args.keep_days)


if __name__ == "__main__":
    main()
