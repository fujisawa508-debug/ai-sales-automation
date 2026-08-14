"""
Outlook 下書き作成モジュール
※ mail.Save() のみ使用 → 送信は絶対にしない
"""

import win32com.client
from config import USE_HTML


def create_draft(to_email: str, subject: str, body_text: str, body_html: str) -> bool:
    """
    Outlookの下書きフォルダにメールを保存する。
    送信（Send）は行わない。
    """
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 = olMailItem

        mail.To = to_email
        mail.Subject = subject

        if USE_HTML:
            mail.HTMLBody = body_html
        else:
            mail.Body = body_text

        # ★ Save() のみ → 下書きフォルダに保存（送信しない）
        mail.Save()
        return True

    except Exception as e:
        print(f"    [エラー] Outlook下書き作成失敗: {e}")
        return False
