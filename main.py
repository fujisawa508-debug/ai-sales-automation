"""
AI営業自動化ツール - メイン実行スクリプト
=========================================
このファイルはツール全体の司令塔（実行の起点）です。
prospects.csv の読み込みからメール文面の生成、Outlookへの下書き保存までの
一連の流れを取りまとめます。メール文面やOutlook操作そのものの実装は
email_templates.py / outlook_draft.py に委譲しています。

【動作フロー（main関数）】
  1. コマンドライン引数を判定
     - --scrape  : scraper.py を呼び出し、Webから見込み先を収集して
                   prospects.csv に追加してから続行
     - --all     : A/B/C全ランクを対象にする（指定なしはAランクのみ）
  2. prospects.csv を読み込む（load_prospects）
     - 優先度（優先度A/B/C）でフィルター
     - 下書き済み（下書き済み列が「済」）の行は除外
     - メールアドレス未設定の行は除外
  3. --research 指定時は company_researcher.py の企業調査エージェントで
     各社の「課題メモ」を自動生成する（--save も指定時は prospects.csv に上書き保存）
  4. 1社ずつメール文を生成しOutlookに下書き保存（process_all）
     - 業種に応じたテンプレートを選択し、会社名などを差し込んで本文を生成
     - outlook_draft.create_draft で下書きのみ保存（送信は一切しない）
  5. 下書きに成功した行の「下書き済み」フラグを prospects.csv に保存
     - --save の指定有無に関わらず必ず実行される（重複下書き防止の要）
  6. 実行結果サマリー（成功/失敗/スキップ件数）を表示

【実行方法】
  python main.py                    → 全件処理（Aランクのみ）
  python main.py --all              → 全ランク処理
  python main.py --scrape           → Webスクレイピング後に実行
  python main.py --research         → 企業調査エージェントで課題メモを自動生成してから実行
  python main.py --research --save  → 調査結果を prospects.csv に上書き保存してから実行

※ 既に下書き作成済み（下書き済み=済）の会社は自動的にスキップされる
"""

import pandas as pd
import sys
import os
from datetime import datetime

# Windows コンソールの文字コードをUTF-8に設定
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from email_templates import get_template, render
from outlook_draft import create_draft

CSV_PATH = os.path.join(os.path.dirname(__file__), "prospects.csv")

FLAG_COLUMN = "下書き済み"
FLAG_DONE = "済"


def _ensure_flag_column(df: pd.DataFrame) -> pd.DataFrame:
    """既存CSVに下書き済み列がない場合は追加する（後方互換）"""
    if FLAG_COLUMN not in df.columns:
        df[FLAG_COLUMN] = ""
    df[FLAG_COLUMN] = df[FLAG_COLUMN].fillna("").astype(str).str.strip()
    return df


def load_prospects(rank_filter: list[str] | None = None) -> pd.DataFrame:
    """CSVから見込み先リストを読み込む"""
    if not os.path.exists(CSV_PATH):
        print(f"[エラー] {CSV_PATH} が見つかりません。")
        sys.exit(1)

    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    df = _ensure_flag_column(df)
    print(f"  読み込み完了: {len(df)}件")

    if rank_filter:
        df = df[df["優先度"].isin(rank_filter)]
        print(f"  フィルター後 ({'/'.join(rank_filter)}ランク): {len(df)}件")

    # 下書き作成済みの行は除外してログに残す
    already_drafted = df[df[FLAG_COLUMN] == FLAG_DONE]
    if len(already_drafted) > 0:
        print(f"\n  [i] 下書き済み（スキップ）: {len(already_drafted)}件")
        for _, row in already_drafted.iterrows():
            print(f"      - {row['会社名']}")
    df = df[df[FLAG_COLUMN] != FLAG_DONE]

    # メールアドレスがない行は除外してログに残す
    no_email = df[df["メールアドレス"].isna() | (df["メールアドレス"].str.strip() == "")]
    if len(no_email) > 0:
        print(f"\n  [!] メールアドレス未設定（スキップ）: {len(no_email)}件")
        for _, row in no_email.iterrows():
            print(f"      - {row['会社名']} ({row['都道府県']})")

    df = df[df["メールアドレス"].notna() & (df["メールアドレス"].str.strip() != "")]
    return df


def process_all(df: pd.DataFrame):
    """全見込み先に対してメール生成→下書き保存"""
    success = 0
    failed = 0
    skipped = 0
    drafted_indices = []

    print(f"\n{'='*50}")
    print(f" Outlook 下書き作成開始（送信はしません）")
    print(f"{'='*50}\n")

    for idx, row in df.iterrows():
        prospect = row.to_dict()
        company = prospect.get("会社名", "不明")
        to_email = str(prospect.get("メールアドレス", "")).strip()
        industry = str(prospect.get("業種", ""))

        print(f"  [{company}]")
        print(f"    業種: {industry} / メール: {to_email}")

        # メールアドレス簡易バリデーション
        if "@" not in to_email:
            print(f"    → スキップ（メールアドレス形式不正）\n")
            skipped += 1
            continue

        # テンプレート取得・差し込み
        template = get_template(industry)
        rendered = render(template, prospect)

        # Outlook下書き保存（送信しない）
        ok = create_draft(
            to_email=to_email,
            subject=rendered["subject"],
            body_text=rendered["body_text"],
            body_html=rendered["body_html"],
        )

        if ok:
            print(f"    -> [OK] 下書き保存完了\n")
            success += 1
            drafted_indices.append(idx)
        else:
            print(f"    -> [NG] 保存失敗\n")
            failed += 1

    return success, failed, skipped, drafted_indices


def print_summary(total: int, success: int, failed: int, skipped: int):
    """実行結果サマリーを表示"""
    print(f"\n{'='*50}")
    print(f" 実行結果サマリー")
    print(f"{'='*50}")
    print(f"  対象件数  : {total}件")
    print(f"  下書き保存: {success}件 [OK]")
    print(f"  失敗      : {failed}件 [NG]")
    print(f"  スキップ  : {skipped}件 [--]")
    print(f"\n  Outlookの「下書き」フォルダをご確認ください。")
    print(f"  内容を確認後、手動で送信してください。")
    print(f"{'='*50}\n")


def main():
    args = sys.argv[1:]

    print(f"\n{'='*50}")
    print(f" AI営業自動化ツール")
    print(f" 実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    # スクレイピングオプション
    if "--scrape" in args:
        from scraper import run_scraping
        run_scraping()

    # ランクフィルター
    if "--all" in args:
        rank_filter = ["A", "B", "C"]
        print("  対象: 全ランク (A/B/C)")
    else:
        rank_filter = ["A"]
        print("  対象: Aランクのみ（--all で全件実行）")

    # 見込み先読み込み
    print("\n--- 見込み先リスト読み込み ---")
    df = load_prospects(rank_filter)

    if len(df) == 0:
        print("\n  処理対象のデータがありません。")
        print("  prospects.csv にメールアドレスを追加するか、")
        print("  --all オプションで全ランクを対象にしてください。")
        return

    # 企業調査エージェント（--research オプション）
    if "--research" in args:
        from company_researcher import run_research
        df = run_research(df)

        # --save が付いていれば CSV を上書き保存
        if "--save" in args:
            # メールアドレスなし行も含めた全データを保持して保存
            all_df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
            all_df.update(df)
            all_df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
            print(f"\n  [保存完了] prospects.csv を更新しました。\n")

    # 処理実行
    success, failed, skipped, drafted_indices = process_all(df)

    # 下書き済みフラグを保存（--save指定の有無に関わらず必ず保存する。
    # 重複下書き防止の要となるため、ここは常に永続化する）
    if drafted_indices:
        save_df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
        save_df = _ensure_flag_column(save_df)
        save_df.loc[drafted_indices, FLAG_COLUMN] = FLAG_DONE
        save_df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
        print(f"\n  [保存完了] 下書き済みフラグを保存しました（{len(drafted_indices)}件）\n")

    # サマリー
    print_summary(len(df), success, failed, skipped)


if __name__ == "__main__":
    main()
