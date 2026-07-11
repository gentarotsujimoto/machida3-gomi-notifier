#!/usr/bin/env python3
"""
町田市 地区番号3 資源とごみ収集スケジュール生成スクリプト
出典: https://www.city.machida.tokyo.jp/kurashi/kankyo/gomi/gominowakekata/gomi-dashikata/syuusyuu/syusyu03.html
"""

import csv
import re
import sys
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

SCHEDULE_URL = "https://www.city.machida.tokyo.jp/kurashi/kankyo/gomi/gominowakekata/gomi-dashikata/syuusyuu/syusyu03.html"
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


def fetch_html(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return resp.text


def parse_specific_dates(soup: BeautifulSoup, label: str) -> set:
    """指定ラベルの収集日（特定土曜日）をページから抽出する"""
    for tag in soup.find_all(string=re.compile(re.escape(label))):
        container = tag.find_parent()
        for _ in range(6):
            if container is None:
                break
            text = container.get_text(separator="\n")
            if re.search(r"\d{4}年", text) and re.search(r"\d{1,2}月\d{1,2}日", text):
                return _extract_dates(text)
            container = container.find_parent()
    return set()


def _extract_dates(text: str) -> set:
    """'2025年\n9月6日･20日' 形式のテキストから日付のsetを生成する"""
    dates = set()
    current_year = None
    for line in text.splitlines():
        line = line.strip()
        m = re.fullmatch(r"(\d{4})年", line)
        if m:
            current_year = int(m.group(1))
            continue
        m = re.match(r"(\d{1,2})月(.+)", line)
        if m and current_year:
            month = int(m.group(1))
            for day in re.findall(r"(\d{1,2})日", m.group(2)):
                try:
                    dates.add(date(current_year, month, int(day)))
                except ValueError:
                    pass
    return dates


def get_schedule_period(dates: set) -> tuple:
    """スクレイプした日付群から収集期間（10月〜翌9月）を導出する。
    ページには前月（9月）のデータも含まれるため、最初の10月で開始年を判定する。"""
    october_dates = [d for d in dates if d.month == 10]
    if october_dates:
        start_year = min(october_dates).year
        return date(start_year, 10, 1), date(start_year + 1, 9, 30)
    # フォールバック: 今日の日付から推定
    today = date.today()
    year = today.year if today.month >= 10 else today.year - 1
    return date(year, 10, 1), date(year + 1, 9, 30)


def nth_weekday(year: int, month: int, weekday: int, n: int):
    """指定月のn番目の曜日を返す (weekday: 0=月,...,6=日)"""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    d = d + timedelta(days=offset + 7 * (n - 1))
    return d if d.month == month else None


def collect_types(d: date, moesenai: set, pet: set) -> list:
    wd = d.weekday()
    y, m = d.year, d.month
    types = []

    # 燃やせるごみ: 毎週月・木（元旦を除く）
    if wd in (0, 3) and not (d.month == 1 and d.day == 1):
        types.append("燃やせるごみ")

    # 燃やせないごみ: 特定土曜日
    if d in moesenai:
        types.append("燃やせないごみ")

    # 剪定枝: 第1・第3火曜日
    if wd == 1 and d in (nth_weekday(y, m, 1, 1), nth_weekday(y, m, 1, 3)):
        types.append("剪定枝")

    # ビン・カン・スプレー缶: 毎週金曜（1月2日を除く）
    if wd == 4 and not (d.month == 1 and d.day == 2):
        types.append("ビン・カン・スプレー缶")

    # 有害ごみ（電池・充電式小型家電）: 第2金曜日
    if wd == 4 and d == nth_weekday(y, m, 4, 2):
        types.append("有害ごみ（電池・充電式小型家電）")

    # 有害ごみ（蛍光管・水銀体温計・ライター）: 第4金曜日
    if wd == 4 and d == nth_weekday(y, m, 4, 4):
        types.append("有害ごみ（蛍光管・水銀体温計・ライター）")

    # 古紙・古着: 毎週水曜（12月31日を除く）
    if wd == 2 and not (d.month == 12 and d.day == 31):
        types.append("古紙・古着")

    # ペットボトル: 特定土曜日
    if d in pet:
        types.append("ペットボトル")

    # 容器包装プラスチック: 毎週火曜日
    if wd == 1:
        types.append("容器包装プラスチック")

    return types


def main():
    print(f"スケジュールページを取得中: {SCHEDULE_URL}")
    html = fetch_html(SCHEDULE_URL)
    soup = BeautifulSoup(html, "html.parser")

    print("燃やせないごみの収集日を解析中...")
    moesenai = parse_specific_dates(soup, "燃やせないごみ")
    print(f"  → {len(moesenai)} 件取得")

    print("ペットボトルの収集日を解析中...")
    pet = parse_specific_dates(soup, "ペットボトル")
    print(f"  → {len(pet)} 件取得")

    if len(moesenai) < 10 or len(pet) < 10:
        print("警告: 取得件数が少ない。ページ構造が変わった可能性があります。", file=sys.stderr)
        sys.exit(1)

    start, end = get_schedule_period(moesenai | pet)
    print(f"収集期間: {start} 〜 {end}")

    rows = []
    d = start
    while d <= end:
        types = collect_types(d, moesenai, pet)
        if types:
            rows.append({
                "日付": d.strftime("%Y-%m-%d"),
                "曜日": WEEKDAY_JP[d.weekday()],
                "ごみの種類": "、".join(types),
            })
        d += timedelta(days=1)

    output_file = "gomi_schedule.csv"
    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["日付", "曜日", "ごみの種類"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"スケジュールを {output_file} に出力しました。収集日数: {len(rows)} 日")


if __name__ == "__main__":
    main()
