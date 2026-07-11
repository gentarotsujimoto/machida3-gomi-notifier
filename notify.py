#!/usr/bin/env python3
"""
町田市ごみ収集 LINE通知スクリプト
毎朝7時（JST）にその日の収集品目をLINEで通知する
"""

import csv
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

LINE_API_URL = "https://api.line.me/v2/bot/message/push"
SCHEDULE_CSV = Path(__file__).parent / "gomi_schedule.csv"
JST = timezone(timedelta(hours=9))


def today_jst():
    return datetime.now(JST).date()


def get_pdf_url() -> str:
    """収集期間の開始年（10月スタート）からPDF URLを生成する"""
    today = today_jst()
    year = today.year if today.month >= 10 else today.year - 1
    base = "https://www.city.machida.tokyo.jp/kurashi/kankyo/gomi/gominowakekata/gomi-dashikata/syuusyuu/syusyu03.files"
    return f"{base}/{year}ippan03.pdf"


def load_today_types() -> list:
    today = today_jst().strftime("%Y-%m-%d")
    if not SCHEDULE_CSV.exists():
        print(f"エラー: {SCHEDULE_CSV} が見つかりません。", file=sys.stderr)
        return []
    with open(SCHEDULE_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["日付"] == today:
                return [t.strip() for t in row["ごみの種類"].split("、")]
    return []


def send_line_message(text: str) -> None:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id:
        print("エラー: LINE_CHANNEL_ACCESS_TOKEN または LINE_USER_ID が設定されていません。", file=sys.stderr)
        sys.exit(1)

    resp = requests.post(
        LINE_API_URL,
        json={"to": user_id, "messages": [{"type": "text", "text": text}]},
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        timeout=10,
    )
    resp.raise_for_status()


def main():
    types = load_today_types()
    if not types:
        print("本日は収集なし。通知をスキップします。")
        return

    items = "\n".join(f"・{t}" for t in types)
    pdf_url = get_pdf_url()
    message = f"今日のごみ収集\n{items}\n\n年間収集カレンダー:\n{pdf_url}"

    print(f"送信メッセージ:\n{message}")
    send_line_message(message)
    print("LINE通知を送信しました。")


if __name__ == "__main__":
    main()
