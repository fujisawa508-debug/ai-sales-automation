"""
見込み先リスト自動収集スクリプト
・東北DX大賞 受賞企業
・ふくいDX推進宣言企業
をスクレイピングして prospects.csv に追記する
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "prospects.csv")


def scrape_tohoku_dx() -> list[dict]:
    """東北DX大賞 受賞企業を取得"""
    url = "https://www.tohoku.meti.go.jp/s_joho/dx_taisyo/dx_tai.html"
    results = []

    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")

        # ページ内の企業名・都道府県を抽出（サイト構造に応じて調整）
        for tag in soup.find_all(["td", "li", "p"]):
            text = tag.get_text(strip=True)
            if "株式会社" in text or "有限会社" in text or "合同会社" in text:
                results.append({
                    "会社名": text[:50],
                    "都道府県": _guess_prefecture(text),
                    "市区町村": "",
                    "業種": "製造業・建設業・その他",
                    "担当者名": "",
                    "役職": "",
                    "メールアドレス": "",
                    "電話番号": "",
                    "課題メモ": "東北DX大賞関連企業",
                    "優先度": "A",
                })

        print(f"  東北DX大賞: {len(results)}件 取得")

    except Exception as e:
        print(f"  [警告] 東北DX大賞スクレイピング失敗: {e}")

    return results


def scrape_fukui_dx() -> list[dict]:
    """ふくいDX推進宣言企業を取得"""
    url = "https://www.fisc.jp/itdx/sengen_touroku/"
    results = []

    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")

        for tag in soup.find_all(["td", "li", "p"]):
            text = tag.get_text(strip=True)
            if "株式会社" in text or "有限会社" in text or "合同会社" in text:
                results.append({
                    "会社名": text[:50],
                    "都道府県": "福井県",
                    "市区町村": "",
                    "業種": "製造業・その他",
                    "担当者名": "",
                    "役職": "",
                    "メールアドレス": "",
                    "電話番号": "",
                    "課題メモ": "ふくいDX推進宣言企業（DX意欲あり）",
                    "優先度": "A",
                })

        print(f"  ふくいDX推進宣言: {len(results)}件 取得")

    except Exception as e:
        print(f"  [警告] ふくいDXスクレイピング失敗: {e}")

    return results


def _guess_prefecture(text: str) -> str:
    """テキストから都道府県を推定"""
    prefs = [
        "青森", "岩手", "宮城", "秋田", "山形", "福島",
        "新潟", "富山", "石川", "福井",
    ]
    for p in prefs:
        if p in text:
            return p + "県"
    return "東北・北陸"


def run_scraping():
    """スクレイピングを実行して prospects.csv に追記"""
    print("\n=== Webスクレイピング開始 ===")

    all_results = []
    all_results += scrape_tohoku_dx()
    time.sleep(1)
    all_results += scrape_fukui_dx()

    if not all_results:
        print("  取得件数: 0件（サイト構造変更の可能性あり）")
        return

    # 既存CSVに追記
    new_df = pd.DataFrame(all_results)
    if os.path.exists(OUTPUT_CSV):
        existing_df = pd.read_csv(OUTPUT_CSV, encoding="utf-8-sig")
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["会社名"])
    else:
        combined = new_df

    combined.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"  → prospects.csv に {len(new_df)}件 追加（合計: {len(combined)}件）")


if __name__ == "__main__":
    run_scraping()
