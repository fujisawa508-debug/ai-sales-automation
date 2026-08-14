"""
企業調査エージェント
- DuckDuckGo で企業の公式サイトを検索
- サイト本文を取得してテキスト化
- Claude API（Haiku）で AI・業務自動化の観点から課題を分析
- prospects.csv の「課題メモ」列を自動補完する
"""

import os
import time
import requests
from urllib.parse import quote, urlparse, parse_qs, unquote
from bs4 import BeautifulSoup
import anthropic

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# -------------------------------------------------------
# 内部ユーティリティ
# -------------------------------------------------------

def _fetch_page_text(url: str, max_chars: int = 3000) -> str:
    """URLのページ本文をプレーンテキストで返す（失敗時は空文字）"""
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:max_chars]
    except Exception:
        return ""


def _search_website(company_name: str, prefecture: str) -> str:
    """DuckDuckGo HTML で企業公式サイトを検索し URL を返す（見つからなければ空文字）"""
    query = f"{company_name} {prefecture} 公式サイト"
    search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    try:
        res = requests.get(search_url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(res.text, "html.parser")
        for link in soup.find_all("a", class_="result__a"):
            href = link.get("href", "")
            # DuckDuckGo は /l/?uddg=<encoded_url> 形式でラップする
            if "uddg=" in href:
                params = parse_qs(urlparse(href).query)
                candidates = params.get("uddg", [])
                if candidates:
                    href = unquote(candidates[0])
            if href.startswith("http") and (".co.jp" in href or ".jp/" in href):
                return href
    except Exception:
        pass
    return ""


def _analyze_with_claude(
    company_name: str, prefecture: str, industry: str, website_text: str
) -> str:
    """Claude Haiku で企業課題を 3 点分析して返す"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "[エラー] 環境変数 ANTHROPIC_API_KEY が設定されていません"

    web_section = (
        f"\nWebサイト本文（抜粋）:\n{website_text}"
        if website_text
        else "\n（Webサイト情報なし。業種・所在地のみで推測してください）"
    )

    prompt = f"""あなたはAI業務自動化の営業コンサルタントです。
以下の企業情報をもとに、「この企業が抱えていそうな業務課題」を
AI・自動化の観点から 3 点、箇条書きで具体的に挙げてください。

企業名: {company_name}
所在地: {prefecture}
業種: {industry}{web_section}

【厳守する出力形式】（余計な文章・前置き不要）
・[課題1（30字以内）]
・[課題2（30字以内）]
・[課題3（30字以内）]"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=180,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"[API エラー: {e}]"


# -------------------------------------------------------
# 公開インターフェース
# -------------------------------------------------------

def research_one(row: dict, verbose: bool = True) -> str:
    """
    1 社分の調査を実行し、課題メモ文字列を返す。
    すでに有効なメモがある場合はスキップする。
    """
    company = str(row.get("会社名", "")).strip()
    prefecture = str(row.get("都道府県", "")).strip()
    industry = str(row.get("業種", "")).strip()
    existing = str(row.get("課題メモ", "")).strip()

    # 既存メモが十分な内容であればスキップ（テストタグは上書き対象）
    skip = (
        existing
        and len(existing) > 15
        and not existing.startswith("【テスト】")
        and not existing.startswith("[")
    )
    if skip:
        if verbose:
            print(f"    -> スキップ（既存メモあり）")
        return existing

    # 公式サイト検索
    if verbose:
        print(f"    -> Webサイト検索中...", end=" ", flush=True)
    website_url = _search_website(company, prefecture)

    website_text = ""
    if website_url:
        if verbose:
            display = website_url if len(website_url) <= 55 else website_url[:52] + "..."
            print(f"発見\n    -> {display}")
            print(f"    -> ページ取得中...")
        website_text = _fetch_page_text(website_url)
    else:
        if verbose:
            print("見つからず（業種情報のみで分析）")

    # Claude API で課題分析
    if verbose:
        print(f"    -> Claude API で課題分析中...")
    return _analyze_with_claude(company, prefecture, industry, website_text)


def run_research(df, verbose: bool = True):
    """
    DataFrame 全件を調査して「課題メモ」列を更新した DataFrame を返す。
    元の DataFrame は変更しない（コピーして返す）。
    """
    import pandas as pd

    print(f"\n{'='*50}")
    print(f" 企業調査エージェント起動")
    print(f"{'='*50}")
    print(f" 対象: {len(df)}社\n")

    memos = []
    for i, (_, row) in enumerate(df.iterrows(), 1):
        company = row.get("会社名", "不明")
        print(f"  [{i}/{len(df)}] {company}")
        memo = research_one(row.to_dict(), verbose=verbose)
        memos.append(memo)
        if verbose:
            # 結果の先頭 60 字を表示
            preview = memo.replace("\n", " ")[:60]
            print(f"    -> 完了: {preview}\n")
        if i < len(df):
            time.sleep(1)  # API レート制限対策

    result = df.copy()
    result["課題メモ"] = memos
    return result
