from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import os
import google.generativeai as genai
from google.api_core import exceptions as api_exceptions
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import io
import datetime

# --- .env_sample優先で環境変数を読み込む ---
if os.path.exists('.env_sample'):
    load_dotenv('.env_sample')
else:
    load_dotenv()

# --- 設定項目 ---
# APIキーは環境変数 GOOGLE_API_KEY から読み込む
MODEL_NAME = "gemini-1.5-pro-latest"
# MODEL_NAME = "gemini-1.5-flash-latest" # 高速化が必要な場合

PROMPT = """
以下の音声ファイルの内容を解析し、構造化された議事録を作成してください。

議事録に含めるべき項目：
1.  **会議名/議題:** (音声内容から推測)
2.  **日時:** (音声内で言及があれば記載)
3.  **参加者:** (音声内で名前や役割が言及されていれば記載)
4.  **議論の要点:** (主要なトピックごとに箇条書きでまとめる)
5.  **決定事項:** (会議で決定されたことがあれば記載)
6.  **ToDo/アクションアイテム:** (誰が、何を、いつまでに行うか)
7.  **その他特記事項:** (上記以外で重要な点があれば)

出力は読みやすいMarkdown形式でお願いします。
"""
# --- ここまで設定項目 ---

# Flaskアプリケーションの初期化
app = Flask(__name__)
app.secret_key = os.urandom(24)  # フラッシュメッセージとセッション用

# ファイルアップロード先のディレクトリ設定
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MBまでのファイルを許可

# アップロード可能な拡張子
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'aac', 'ogg', 'flac', 'opus', 'mp4', 'mov', 'wmv', 'avi', 'webm', 'mpeg'}

# アップロードディレクトリの作成
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ファイル拡張子のチェック関数
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Gemini API 呼び出し関数 ---
def process_audio_with_gemini(file_path):
    """音声ファイルからGeminiを使って議事録を生成する関数"""
    uploaded_file = None # finally節で使うため先に定義
    try:
        # APIキーを環境変数から取得
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return "エラー: 環境変数 GOOGLE_API_KEY が設定されていません。"

        if not os.path.exists(file_path):
            return f"エラー: ファイルが見つかりません: {file_path}"

        # APIキーを設定
        genai.configure(api_key=api_key)

        # ファイルをアップロード
        uploaded_file = genai.upload_file(path=file_path)

        # ファイルの処理状態を確認
        if uploaded_file.state.name != "ACTIVE":
            return f"エラー: ファイルのアップロードまたは処理に失敗しました。状態: {uploaded_file.state.name}"

        # モデルの初期化と議事録生成
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content([uploaded_file, PROMPT])

        return response.text

    except FileNotFoundError:
        return f"エラー: 指定されたファイルが見つかりません: {file_path}"
    except api_exceptions.PermissionDenied:
        return "エラー: APIキーが無効か、必要な権限がありません。"
    except api_exceptions.ResourceExhausted:
        return "エラー: APIの利用上限に達した可能性があります。時間をおいて試すか、利用状況を確認してください。"
    except Exception as e:
        return f"予期せぬエラーが発生しました: {e}"
    finally:
        # 一時ファイルを削除 (重要: コスト削減とクリーンアップのため)
        if uploaded_file:
            try:
                genai.delete_file(uploaded_file.name)
            except Exception as e:
                print(f"警告: アップロードされたファイル '{uploaded_file.name}' の削除中にエラーが発生しました: {e}")

# ルートURL - ファイルアップロードページを表示
@app.route('/')
def index():
    return render_template('index.html')

# ファイルアップロード処理
@app.route('/upload', methods=['POST'])
def upload_file():
    # ファイルが存在するか確認
    if 'audio_file' not in request.files:
        flash('ファイルが見つかりません')
        return redirect(url_for('index'))
    
    file = request.files['audio_file']
    
    # ファイルが選択されているか確認
    if file.filename == '':
        flash('ファイルが選択されていません')
        return redirect(url_for('index'))
    
    # ファイルが許可された形式か確認
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Gemini APIを使用して議事録を生成
            result = process_audio_with_gemini(filepath)
            
            # 処理完了後、ローカルの一時ファイルを削除
            if os.path.exists(filepath):
                os.remove(filepath)
            
            # 結果とファイル名をセッションに保存
            session['minutes_result'] = result
            session['original_filename'] = filename
            
            # エラーチェック
            if result.startswith("エラー:"):
                flash(result)
                return redirect(url_for('index'))
                
            # 結果表示ページにリダイレクト
            return redirect(url_for('show_result'))
            
        except Exception as e:
            flash(f'処理中にエラーが発生しました: {str(e)}')
            # エラーが発生しても一時ファイルを削除
            if os.path.exists(filepath):
                os.remove(filepath)
            return redirect(url_for('index'))
    else:
        flash('許可されていないファイル形式です')
        return redirect(url_for('index'))

# 結果表示ページ
@app.route('/result')
def show_result():
    result = session.get('minutes_result', None)
    if not result:
        flash('議事録データがありません。ファイルをアップロードしてください。')
        return redirect(url_for('index'))
    
    # 結果がエラーだった場合
    if result.startswith('エラー:'):
        flash(result)
        return redirect(url_for('index'))
    
    # 結果をHTMLで表示（テンプレートを使用）
    return render_template('result.html', minutes=result)

@app.route('/download')
def download_minutes():
    result = session.get('minutes_result', None)
    original_filename = session.get('original_filename', 'minutes')
    if not result:
        flash('議事録データがありません。ファイルをアップロードしてください。')
        return redirect(url_for('index'))
    # ファイル名を決定（例: サンプル会議音声１_YYYYMMDD.md）
    base = os.path.splitext(original_filename)[0]  # 拡張子を除いた部分
    today = datetime.datetime.now().strftime('%Y%m%d')
    filename = f'{base}_{today}.md'
    # メモリ上にファイルを作成
    file_stream = io.BytesIO(result.encode('utf-8'))
    return send_file(
        file_stream,
        as_attachment=True,
        download_name=filename,
        mimetype='text/markdown; charset=utf-8'
    )

# アプリケーション実行
if __name__ == '__main__':
    app.run(debug=True) 