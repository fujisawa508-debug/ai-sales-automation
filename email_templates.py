"""
業種別メールテンプレート
"""

from config import SENDER_NAME, SENDER_COMPANY, SENDER_PHONE, SENDER_EMAIL, SENDER_TITLE


def get_template(industry: str) -> dict:
    """業種に応じたテンプレートを返す"""
    industry = industry.strip()

    if "製造" in industry:
        return _manufacturing()
    elif "建設" in industry:
        return _construction()
    elif "物流" in industry:
        return _logistics()
    elif "食品" in industry:
        return _food()
    elif "農業" in industry:
        return _agriculture()
    elif "エネルギー" in industry:
        return _energy()
    else:
        return _general()


def render(template: dict, prospect: dict) -> dict:
    """テンプレートに企業情報を差し込んで完成させる"""
    company = prospect.get("会社名", "貴社")
    contact = prospect.get("担当者名", "ご担当者")
    contact = contact if contact and contact != "担当者未確認" else "ご担当者"
    prefecture = prospect.get("都道府県", "")
    issue = str(prospect.get("課題メモ", "")).strip()

    # 調査済みの課題メモがあれば専用セクションとして挿入する
    is_researched = (
        issue
        and len(issue) > 15
        and not issue.startswith("[")
        and not issue.startswith("【テスト】")
    )
    if is_researched:
        issue_section = (
            f"貴社について事前にリサーチさせていただいたところ、"
            f"以下のような課題をお持ちではないかと拝察いたしました。\n\n"
            f"{issue}\n\n"
        )
    else:
        issue_section = ""

    subject = template["subject"].format(
        company=company,
        prefecture=prefecture,
    )
    body_text = template["body_text"].format(
        company=company,
        contact=contact,
        prefecture=prefecture,
        issue=issue,
        issue_section=issue_section,
        sender_name=SENDER_NAME,
        sender_company=SENDER_COMPANY,
        sender_phone=SENDER_PHONE,
        sender_email=SENDER_EMAIL,
        sender_title=SENDER_TITLE,
    )
    body_html = _to_html(body_text)

    return {
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
    }


def _to_html(text: str) -> str:
    """プレーンテキストをシンプルなHTMLに変換"""
    lines = text.split("\n")
    html_lines = []
    for line in lines:
        if line.strip() == "":
            html_lines.append("<br>")
        elif line.startswith("■") or line.startswith("━"):
            html_lines.append(f"<b>{line}</b><br>")
        else:
            html_lines.append(f"{line}<br>")
    body = "\n".join(html_lines)
    return f"""<html><body style="font-family: メイリオ, sans-serif; font-size: 14px; line-height: 1.8; color: #333;">
{body}
</body></html>"""


# ============================================================
# 業種別テンプレート本文
# ============================================================

def _manufacturing() -> dict:
    return {
        "subject": "【AI業務自動化のご提案】{company}様 製造現場の人手不足・品質管理をAIで解決",
        "body_text": """{contact} 様

突然のご連絡、大変失礼いたします。
AI業務自動化のご支援をしております、{sender_company} {sender_title}の{sender_name}と申します。

{prefecture}の製造業様では現在、

  ・熟練技術者の高齢化・後継者不足
  ・品質検査の人的ミス・工数増加
  ・生産計画や在庫管理の非効率

といったお悩みをお持ちの企業様が増えていると伺っております。

{issue_section}弊社では製造業様向けにAIを活用した以下の自動化支援を行っております。

■ 弊社のご支援内容
  ・AI品質検査（画像認識による不良品自動検出）
  ・生産計画・在庫の需要予測自動化
  ・日報・帳票類の自動入力・集計
  ・ベテラン社員のノウハウのAIへの移植

■ 導入事例
  同規模の製造業A社様では、AI導入により
  品質検査工数を約60%削減、不良品流出ゼロを達成いたしました。

■ 費用について
  現在、IT導入補助金（最大450万円）を活用することで
  初期費用を大幅に抑えた導入が可能です。

まずは貴社の現状をお聞きし、最適なご提案をさせていただきたく、
30分ほどオンラインでお話を伺えますでしょうか？

ご都合の良い日程をご返信いただけますと幸いです。

━━━━━━━━━━━━━━━━━━━━
{sender_name}
{sender_company} {sender_title}
TEL: {sender_phone}
MAIL: {sender_email}
━━━━━━━━━━━━━━━━━━━━
""",
    }


def _construction() -> dict:
    return {
        "subject": "【AI業務自動化のご提案】{company}様 見積・工程管理の自動化で受注件数3倍の事例",
        "body_text": """{contact} 様

突然のご連絡、大変失礼いたします。
AI業務自動化のご支援をしております、{sender_company} {sender_title}の{sender_name}と申します。

{prefecture}の建設業様では、

  ・見積書作成に多くの時間がかかっている
  ・工程管理・書類作成がExcel頼みで属人的
  ・現場報告・日報のデジタル化が進んでいない

といったお悩みをお持ちの企業様が多くいらっしゃいます。

{issue_section}■ 弊社のご支援内容
  ・AI見積書自動生成（過去案件データを学習）
  ・工程管理・進捗の自動レポート化
  ・現場写真の自動分類・報告書作成
  ・請求書・契約書の自動処理

■ 導入事例
  東北の建設資材会社様では、AI導入により
  見積提出件数が年間450件→1,263件（約3倍）に増加しました。

■ 費用について
  IT導入補助金（最大450万円）の活用で
  初期費用を抑えた導入が可能です。

30分のオンライン相談でも詳しくご説明できます。
ご都合の良い日程をお知らせいただけますでしょうか？

━━━━━━━━━━━━━━━━━━━━
{sender_name}
{sender_company} {sender_title}
TEL: {sender_phone}
MAIL: {sender_email}
━━━━━━━━━━━━━━━━━━━━
""",
    }


def _logistics() -> dict:
    return {
        "subject": "【AI業務自動化のご提案】{company}様 配送ルート最適化・ドライバー不足をAIで解決",
        "body_text": """{contact} 様

突然のご連絡、大変失礼いたします。
AI業務自動化のご支援をしております、{sender_company} {sender_title}の{sender_name}と申します。

物流業界では2024年問題以降、

  ・ドライバー不足・労働時間規制への対応
  ・配送ルートの非効率・燃料費増加
  ・配車計画の属人化・担当者依存

といった課題が深刻化しております。

{issue_section}■ 弊社のご支援内容
  ・AIによる最適配送ルート自動計算
  ・需要予測に基づく配車計画の自動化
  ・配送状況のリアルタイム可視化
  ・ドライバーへのデジタル指示・報告の自動化

■ 導入事例
  同規模の物流会社様では、AI配送ルート最適化により
  燃料費15%削減・配車担当者の業務時間40%短縮を実現しました。

■ 費用について
  IT導入補助金（最大450万円）の活用が可能です。

まずは30分のオンライン相談でご状況をお聞かせください。
ご都合の良い日程をご返信いただければ幸いです。

━━━━━━━━━━━━━━━━━━━━
{sender_name}
{sender_company} {sender_title}
TEL: {sender_phone}
MAIL: {sender_email}
━━━━━━━━━━━━━━━━━━━━
""",
    }


def _food() -> dict:
    return {
        "subject": "【AI業務自動化のご提案】{company}様 需要予測・在庫最適化をAIで自動化",
        "body_text": """{contact} 様

突然のご連絡、大変失礼いたします。
AI業務自動化のご支援をしております、{sender_company} {sender_title}の{sender_name}と申します。

食品製造業様では、

  ・需要予測が経験頼みで在庫ロスが多い
  ・品質管理・異物検査に人手がかかっている
  ・受発注・請求処理が手作業で非効率

といったお悩みをお持ちの企業様が多くいらっしゃいます。

{issue_section}■ 弊社のご支援内容
  ・AI需要予測による在庫最適化
  ・画像AIによる品質・異物検査の自動化
  ・受発注・請求書処理の自動化（AI-OCR）
  ・生産計画の自動立案

■ 導入事例
  食品メーカーB社様では、AI需要予測の導入により
  食品廃棄ロスを30%削減、在庫回転率が1.5倍に改善しました。

■ 費用について
  IT導入補助金（最大450万円）を活用した導入が可能です。

30分のオンライン相談からでも承ります。
ご都合をお知らせいただけますでしょうか？

━━━━━━━━━━━━━━━━━━━━
{sender_name}
{sender_company} {sender_title}
TEL: {sender_phone}
MAIL: {sender_email}
━━━━━━━━━━━━━━━━━━━━
""",
    }


def _agriculture() -> dict:
    return {
        "subject": "【AI業務自動化のご提案】{company}様 スマート農業・収穫予測AIのご紹介",
        "body_text": """{contact} 様

突然のご連絡、大変失礼いたします。
AI業務自動化のご支援をしております、{sender_company} {sender_title}の{sender_name}と申します。

農業・食品分野では、

  ・熟練農家の減少・後継者不足
  ・天候・市場変動による収量・価格の不安定さ
  ・収穫・物流の計画が立てにくい

といった課題が年々深刻化しております。

{issue_section}■ 弊社のご支援内容
  ・AIによる収穫量・品質予測
  ・気象データ×販売データを組み合わせた需要予測
  ・スマート農機・センサーデータの自動分析
  ・農作業日誌・出荷記録の自動化

■ 費用について
  農業分野専用の補助金（スマート農業推進事業）も活用可能です。

まずは現状のお悩みをお聞かせいただけますでしょうか？
30分のオンライン相談から承ります。

━━━━━━━━━━━━━━━━━━━━
{sender_name}
{sender_company} {sender_title}
TEL: {sender_phone}
MAIL: {sender_email}
━━━━━━━━━━━━━━━━━━━━
""",
    }


def _energy() -> dict:
    return {
        "subject": "【AI業務自動化のご提案】{company}様 配送・需要予測をAIで最適化",
        "body_text": """{contact} 様

突然のご連絡、大変失礼いたします。
AI業務自動化のご支援をしております、{sender_company} {sender_title}の{sender_name}と申します。

エネルギー・プロパン販売業様では、

  ・配送スケジュールの最適化が難しい
  ・顧客ごとの使用量予測が経験頼み
  ・ドライバー不足への対応

といった課題をお持ちの企業様が増えております。

{issue_section}■ 弊社のご支援内容
  ・AI需要予測による効率的な配送計画の自動化
  ・顧客使用量の予測モデル構築
  ・配送管理のデジタル化・可視化
  ・緊急配送の優先順位自動判定

■ 費用について
  IT導入補助金（最大450万円）の活用が可能です。

30分のオンライン相談でご状況をお聞かせいただけますでしょうか？

━━━━━━━━━━━━━━━━━━━━
{sender_name}
{sender_company} {sender_title}
TEL: {sender_phone}
MAIL: {sender_email}
━━━━━━━━━━━━━━━━━━━━
""",
    }


def _general() -> dict:
    return {
        "subject": "【AI業務自動化のご提案】{company}様 業務効率化・人手不足解消をAIでご支援",
        "body_text": """{contact} 様

突然のご連絡、大変失礼いたします。
AI業務自動化のご支援をしております、{sender_company} {sender_title}の{sender_name}と申します。

貴社のような{prefecture}の中小企業様では、

  ・人手不足・採用難への対応
  ・繰り返し業務の自動化
  ・データ活用・意思決定の効率化

といった課題をお持ちの企業様が多くいらっしゃいます。

{issue_section}■ 弊社のご支援内容
  ・定型業務のAI・RPA自動化
  ・書類・帳票処理の自動化（AI-OCR）
  ・データ分析・レポート自動生成
  ・社内問い合わせ対応AIチャットボット

■ 費用について
  IT導入補助金（最大450万円）の活用が可能です。

まずは30分のオンライン相談でお気軽にお声がけください。

━━━━━━━━━━━━━━━━━━━━
{sender_name}
{sender_company} {sender_title}
TEL: {sender_phone}
MAIL: {sender_email}
━━━━━━━━━━━━━━━━━━━━
""",
    }
