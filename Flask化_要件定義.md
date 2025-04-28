【Cursor Agentへの開発依頼プロンプト (Flask Webアプリ化)】
1. 開発対象システム
システム名: Gemini APIを利用したWeb版 議事録作成ツール
目的: ユーザーがWebブラウザから音声/動画ファイルをアップロードし、Gemini APIを利用して生成された議事録テキストを受け取れるようにする。最終的にはCloud Runでの公開を目指す。
プラットフォーム: Python Webアプリケーション
主要技術: Flask, HTML, google-generativeai, python-dotenv, (将来的には pydub)
ベースコード: 既存の main.py (tkinter版) のGemini API連携ロジック (generate_minutes_from_audio 関数に相当する部分) を流用・参考にする。tkinter 関連のコードは全て削除・置き換えとなる。
2. 今回作成するスコープ (シンプルなMVP)
対象機能:
ルートURL ("/") でファイルアップロード用のシンプルなHTMLフォームを表示する。
フォームから送信された音声/動画ファイルを受け取り、サーバー上に一時的に保存する。
一時保存したファイルを使い、Gemini APIを呼び出して議事録テキストを生成する（基本的な単一ファイル処理）。
生成された議事録テキストを、別のHTMLページで表示する。
基本的なエラー（ファイル未選択、APIエラー等）をハンドリングし、ユーザーに通知する。
対象外機能 (今回は実装しない):
長尺ファイルの自動分割・逐次処理機能。
非同期処理（処理中のプログレス表示など）。
ユーザー認証、過去の結果履歴表示。
洗練されたUIデザイン。
3. 機能要件（構造化タスク形式）
以下に、具体的な実装タスクを構造化形式で記述します。これらのタスクを実行して、Flaskアプリケーションを構築してください。
【タスク F-01】Flaskアプリケーションの基本設定
タスク名: Flaskアプリケーションの初期セットアップ
作業内容:
新しいPythonファイル（例: app.py）を作成する。
必要なライブラリ (Flask, render_template, request, redirect, url_for, os, google.generativeai, dotenv) をインポートする。
Flaskアプリケーションインスタンスを作成する (app = Flask(__name__))。
ファイルを一時保存するためのディレクトリ（例: uploads）を指定する定数を定義し、必要なら起動時にそのディレクトリを作成する処理を追加する (os.makedirs(..., exist_ok=True))。
.env ファイルから環境変数（特に GOOGLE_API_KEY）を読み込む処理を追加する (load_dotenv())。
アプリケーションを実行するための if __name__ == '__main__': app.run(debug=True) ブロックを追加する (debug=True は開発時のみ)。
成果物:
基本的なFlaskアプリの構造を持つ app.py ファイル。
uploads ディレクトリ（起動時に自動生成される）。
完了条件:
python app.py でFlask開発サーバーが起動し、エラーが発生しない。
環境変数がロードされる。
【タスク F-02】ファイルアップロードページの作成
タスク名: ファイルアップロード用HTMLページの表示機能実装
作業内容:
ルートURL ('/') に対するルート (@app.route('/')) を作成する。
このルートに対応する関数 (index など) を定義する。
簡単なHTMLフォームを持つテンプレートファイル (templates/index.html) を作成する。フォームには以下を含む:
ファイル選択 (<input type="file" name="audio_file" accept="audio/*,video/*">)
送信ボタン (<input type="submit" value="議事録作成">)
フォームの action 属性はファイル処理用のURL（例: /upload）を指定し、method は POST、enctype は multipart/form-data を指定する。
index 関数内で render_template('index.html') を呼び出し、このHTMLページを表示する。
Flaskアプリケーションのルートディレクトリに templates フォルダを作成し、index.html をその中に配置する。
成果物:
@app.route('/') が定義された app.py。
ファイルアップロードフォームを持つ templates/index.html ファイル。
完了条件:
Webブラウザで '/' (例: http://127.0.0.1:5000/) にアクセスすると、ファイル選択ボタンと送信ボタンが表示される。
【タスク F-03】ファイルアップロード処理の実装
タスク名: アップロードされたファイルを受け取り一時保存する機能の実装
作業内容:
ファイル処理用のURL ('/upload') に対するルート (@app.route('/upload', methods=['POST'])) を作成する。POSTメソッドのみ許可する。
このルートに対応する関数 (upload_file など) を定義する。
関数内で request.files['audio_file'] を使ってアップロードされたファイルオブジェクトを取得する。ファイルが選択されていない場合の基本的なエラーハンドリングを追加する。
ファイルオブジェクトが存在する場合、安全なファイル名（例: werkzeug.utils.secure_filename を使用）を取得する。
定義した一時保存用ディレクトリ (uploads フォルダ) に、そのファイル名でファイルを保存する (file.save(os.path.join(...)))。保存したファイルのパスを後続処理のために変数に格納する。
成果物:
@app.route('/upload', methods=['POST']) が定義された app.py。
アップロードされたファイルを uploads ディレクトリに保存するロジック。
完了条件:
index.html からファイルを送信すると、uploads ディレクトリ内にそのファイルが保存される。
ファイルが選択されずに送信された場合、エラーメッセージを表示するか、前のページに戻るなどの処理が行われる。
【タスク F-04】Gemini API連携ロジックの統合
タスク名: 既存のGemini API連携処理をFlaskアプリケーション用に修正・統合
作業内容:
既存の main.py(tkinter版) にあった generate_minutes_from_audio 関数のロジックを参考に、Flaskアプリケーション内で呼び出せる新しい関数（例: process_audio_with_gemini(file_path)）を作成する。
この新関数は、ファイルパスを引数として受け取るようにする。
関数内でAPIキーを環境変数から取得し、genai.configure() を実行する。
genai.upload_file() でファイルパスからファイルをアップロードする。
genai.GenerativeModel() でモデルを初期化する。
アップロードされたファイルオブジェクトと、定義済みの議事録作成用プロンプト (PROMPT 定数など) を使って model.generate_content() を呼び出す。
重要: generate_content() 完了後、finally 節などで genai.delete_file() を呼び出し、GCS上の一時ファイルを削除する。
Gemini APIからのレスポンス（議事録テキスト）を関数の戻り値とする。
API呼び出しに関するエラーハンドリング (try...except api_exceptions...) を実装し、エラー発生時はエラー内容を示す文字列などを返す。
成果物:
ファイルパスを受け取り、Gemini APIで議事録を生成してテキストを返す関数 (process_audio_with_gemini など) の実装コード。
完了条件:
process_audio_with_gemini 関数に有効なファイルパスを渡すと、Gemini APIによって生成された議事録テキストが返される。
処理完了後、GCS上の一時ファイルが削除される。
APIキーエラーやリソース枯渇などのAPI関連エラーが適切に処理される。
【タスク F-05】処理実行と結果表示の実装
タスク名: ファイル処理の実行と結果表示ページの作成
作業内容:
【タスク F-03】の upload_file 関数のファイル保存後処理を修正する。
保存したファイルのパスを引数として【タスク F-04】の process_audio_with_gemini 関数を呼び出す。
process_audio_with_gemini から返された結果（議事録テキストまたはエラーメッセージ）を取得する。
結果を表示するための新しいルート ('/result') とテンプレート (templates/result.html) を作成する。
upload_file 関数内で、取得した結果を一時的に保存する（例: Flaskの session を使うか、単純に結果表示ルートにパラメータとして渡す）。今回は、結果表示ルートにリダイレクトし、結果をパラメータで渡すシンプルな方法を試す。 (URLパラメータで長いテキストを渡すのは推奨されないが、最初のステップとして) または、結果を一時ファイルに書き出し、結果ページでそれを読み込む方法も可。 より良い方法として、結果をPOSTリクエストのデータとして結果表示ページに渡すか、sessionを使うことを検討する。（Agentに実装を任せる）
templates/result.html を作成し、渡された議事録テキスト（またはエラーメッセージ）を表示する。表示には <pre> タグなどを使うと改行が反映されやすい。
upload_file 関数の最後に、結果表示ルート ('/result') へリダイレクトする処理 (redirect(url_for('show_result', ...))) を追加する。
一時保存したファイル (uploads ディレクトリ内のファイル) は、処理完了後に削除するロジックを追加する（例: process_audio_with_gemini が成功した後に os.remove()）。
成果物:
修正された upload_file 関数（Gemini処理呼び出し、結果処理、リダイレクト）。
結果表示用のルート (@app.route('/result')) と対応する関数 (show_result など)。
結果を表示する templates/result.html ファイル。
ローカルの一時ファイル削除ロジック。
完了条件:
ファイルをアップロードすると、Geminiによる処理が実行される。
処理完了後、ブラウザが結果表示ページにリダイレクトされる。
結果表示ページに、生成された議事録テキストまたはエラーメッセージが表示される。
サーバーの uploads ディレクトリ内の一時ファイルが削除される。
4. 非機能要件（今回はシンプルに）
エラーハンドリング: ファイル未選択、APIエラー、ファイル保存エラーなど、基本的なエラー発生時にユーザーに状況がわかるように表示する。（例: 結果表示ページにエラーメッセージを表示）
セキュリティ: ファイルアップロード時のファイル名サニタイズ (secure_filename) を行う。APIキーは環境変数から読み込む。
5. 技術要件・制約
開発言語: Python 3.x
Webフレームワーク: Flask
主要外部ライブラリ: Flask, google-generativeai, python-dotenv
フロントエンド: 基本的なHTML、CSS（必須ではない）
API: Google Gemini API
APIキー: .env ファイルから環境変数 GOOGLE_API_KEY として読み込む。(Cloud Runデプロイ時はSecret Manager等への移行が必要である点に留意)
6. その他
まずは基本的な動作を実現することを最優先とする。長尺ファイル対応やUIの改善は次のフェーズで行う。
Flaskの基本的な使い方（ルーティング、テンプレート、リクエスト処理）に従って実装する。
このプロンプトをCursor Agentに与え、app.py と templates/ フォルダおよびその中のHTMLファイルを作成・修正させてください。必要に応じて、Agentの出力に対して追加の指示や修正依頼を行ってください。