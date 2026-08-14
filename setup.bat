@echo off
echo ========================================
echo  AI営業自動化ツール セットアップ
echo ========================================
echo.
echo 必要なパッケージをインストールしています...
pip install -r requirements.txt
echo.
echo セットアップ完了！
echo.
echo 【次のステップ】
echo 1. config.py を開いて送信者情報を編集してください
echo 2. prospects.csv を開いてメールアドレスを入力してください
echo 3. python main.py を実行してください
echo.
pause
