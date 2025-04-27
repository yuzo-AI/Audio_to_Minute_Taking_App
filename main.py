import tkinter as tk
from tkinter import filedialog, messagebox, ttk # ttkを追加して進捗バー表示
import threading
import os
from dotenv import load_dotenv # dotenvを追加
import google.generativeai as genai
from google.api_core import exceptions as api_exceptions
import time # 進捗確認用 (オプション)

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

# .env ファイルから環境変数を読み込む
load_dotenv()

# --- Gemini API 呼び出し関数 ---
def generate_minutes_from_audio(file_path: str, model_name: str, prompt: str, status_callback=None, progress_callback=None) -> str:
    """音声ファイルからGeminiを使って議事録を生成する関数"""
    uploaded_file = None # finally節で使うため先に定義
    try:
        # APIキーを環境変数から取得
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return "エラー: 環境変数 GOOGLE_API_KEY が設定されていません。"

        if not os.path.exists(file_path):
             return f"エラー: ファイルが見つかりません: {file_path}"

        if status_callback: status_callback("APIキーを設定中...")
        genai.configure(api_key=api_key)

        # --- ファイルアップロードと進捗表示 ---
        if status_callback: status_callback(f"ファイルをアップロード中: {os.path.basename(file_path)}...")
        if progress_callback: progress_callback(0, "アップロード開始") # 進捗0%

        # upload_file は非同期に行われる場合があるため、状態を確認する
        uploaded_file = genai.upload_file(path=file_path)

        # 状態がACTIVEになるまで待機し、進捗を表示 (簡易的なポーリング)
        upload_progress = 10 # アップロード開始時点で10%とする
        if progress_callback: progress_callback(upload_progress, "アップロード中...")
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2) # 2秒待機
            uploaded_file = genai.get_file(uploaded_file.name) # 最新の状態を取得
            # 進捗を少しずつ進める（実際の進捗率はAPIからは取得できないため仮）
            if upload_progress < 70:
                upload_progress += 5
                if progress_callback: progress_callback(upload_progress, "アップロード中...")

        if uploaded_file.state.name != "ACTIVE":
            return f"エラー: ファイルのアップロードまたは処理に失敗しました。状態: {uploaded_file.state.name}"

        if progress_callback: progress_callback(70, "ファイル処理完了") # 70%まで進める
        # --------------------------------------

        if status_callback: status_callback("ファイルの準備完了。議事録生成を開始します...")
        if progress_callback: progress_callback(75, "モデル準備中")
        model = genai.GenerativeModel(model_name)
        if progress_callback: progress_callback(80, "コンテンツ生成中...")

        response = model.generate_content([uploaded_file, prompt])

        if progress_callback: progress_callback(100, "生成完了")
        if status_callback: status_callback("議事録の生成が完了しました。")

        return response.text

    except FileNotFoundError:
        # これは通常、上の os.path.exists で捕捉されるはず
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
                if status_callback: status_callback("一時ファイルを削除中...")
                genai.delete_file(uploaded_file.name)
                if status_callback: status_callback("一時ファイルを削除しました。")
            except Exception as e:
                # 削除エラーは致命的ではない場合が多いのでログ出力に留める
                print(f"警告: アップロードされたファイル '{uploaded_file.name}' の削除中にエラーが発生しました: {e}")


# --- GUI アプリケーションクラス ---
class MinutesApp:
    def __init__(self, master):
        self.master = master
        master.title("Gemini 議事録作成ツール")
        master.geometry("650x250") # ウィンドウサイズ調整

        self.selected_file_path = tk.StringVar()
        self.status_text = tk.StringVar()
        self.status_text.set("音声ファイルを選択してください。")
        self.is_processing = False # 処理中フラグ

        # APIキーチェック（環境変数）
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
             self.status_text.set("警告: 環境変数 GOOGLE_API_KEY が設定されていません！")
             # 起動時にダイアログも表示
             self.master.after(100, lambda: messagebox.showwarning("APIキー未設定", "環境変数 GOOGLE_API_KEY を設定してください。\n設定しないと実行時にエラーになります。"))

        # --- GUI要素の作成 ---
        # 上部フレーム (ファイル選択)
        top_frame = tk.Frame(master, pady=10)
        top_frame.pack(fill=tk.X, padx=10)

        tk.Label(top_frame, text="音声/動画ファイル:").pack(side=tk.LEFT, padx=5)
        self.file_entry = tk.Entry(top_frame, textvariable=self.selected_file_path, width=55, state='readonly')
        self.file_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.browse_button = tk.Button(top_frame, text="参照...", command=self.browse_file)
        self.browse_button.pack(side=tk.LEFT, padx=5)

        # 中央フレーム (実行ボタン)
        middle_frame = tk.Frame(master, pady=5)
        middle_frame.pack(fill=tk.X, padx=10)

        self.run_button = tk.Button(middle_frame, text="議事録を作成して保存", command=self.start_generation, state=tk.DISABLED, width=30, height=2)
        self.run_button.pack(pady=5)

        # 下部フレーム (進捗とステータス)
        bottom_frame = tk.Frame(master, pady=5)
        bottom_frame.pack(fill=tk.X, padx=10, side=tk.BOTTOM, anchor='sw') # 下に配置

        # プログレスバー
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(bottom_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 5)) # 下に少し余白

        # ステータス表示ラベル
        self.status_label = tk.Label(bottom_frame, textvariable=self.status_text, anchor="w", justify=tk.LEFT)
        self.status_label.pack(fill=tk.X)

        # 起動時のAPIキーチェックは __init__ 内で行うように変更


    def browse_file(self):
        """ファイル選択ダイアログを開き、選択されたパスをセットする"""
        if self.is_processing: return # 処理中は選択不可
        filetypes = (
            ("音声/動画ファイル", "*.mp3 *.wav *.m4a *.aac *.ogg *.flac *.opus *.mp4 *.mov *.wmv *.avi *.webm *.mpeg"),
            ("すべてのファイル", "*.*")
        )
        filepath = filedialog.askopenfilename(title="音声/動画ファイルを選択", filetypes=filetypes)
        if filepath:
            self.selected_file_path.set(filepath)
            self.status_text.set(f"ファイル選択: {os.path.basename(filepath)}")
            # APIキーが設定されていればボタンを有効化 (環境変数チェック)
            if self.api_key:
                self.run_button.config(state=tk.NORMAL)
            self.progress_var.set(0) # 進捗リセット

    def update_status(self, message):
        """ステータスラベルをスレッドセーフに更新する"""
        self.master.after(0, self.status_text.set, message)

    def update_progress(self, value, text_prefix="処理中"):
        """プログレスバーとステータスをスレッドセーフに更新する"""
        self.master.after(0, self._update_progress_ui, value, text_prefix)

    def _update_progress_ui(self, value, text_prefix):
        """GUI更新用（afterから呼び出す）"""
        self.progress_var.set(value)
        self.status_text.set(f"{text_prefix}: {int(value)}%")

    def set_ui_processing(self, processing):
        """処理中/処理完了に応じてUIの状態を切り替える"""
        self.is_processing = processing
        new_state = tk.DISABLED if processing else tk.NORMAL
        self.browse_button.config(state=new_state)
        # 実行ボタンはファイル選択かつAPIキーOKの場合のみ有効化 (環境変数チェック)
        if not processing and self.selected_file_path.get() and self.api_key:
            self.run_button.config(state=tk.NORMAL)
        else:
            self.run_button.config(state=tk.DISABLED)

        if not processing:
             # 処理完了後、進捗をリセットするかどうか（ここではリセットしない）
             # self.progress_var.set(0)
             pass


    def generation_thread(self, filepath):
        """議事録生成を別スレッドで実行する"""
        try:
            self.master.after(0, self.set_ui_processing, True) # UIを処理中状態に
            self.update_status("処理を開始します...")
            self.update_progress(0, "開始")

            # APIキーは generate_minutes_from_audio 関数内で環境変数から取得するため、ここでは渡さない
            result = generate_minutes_from_audio(
                file_path=filepath,
                model_name=MODEL_NAME,
                prompt=PROMPT,
                status_callback=self.update_status, # 詳細ステータス更新用
                progress_callback=self.update_progress # 進捗バー更新用
            )

            if result.startswith("エラー:"):
                self.master.after(0, messagebox.showerror, "エラー", result)
                self.update_status("エラーが発生しました。")
                self.update_progress(0, "エラー") # エラー時は進捗を0に戻す
            else:
                # 生成成功、ファイル保存ダイアログを表示
                # GUIの更新はメインスレッドで行うため、afterを使用
                self.master.after(0, self.save_result, result, filepath)

        except Exception as e:
            # スレッド内で予期せぬエラーが発生した場合
            error_message = f"予期せぬエラーが発生しました:\n{e}"
            self.master.after(0, messagebox.showerror, "重大なエラー", error_message)
            self.update_status("重大なエラーが発生しました。")
            self.update_progress(0, "エラー")
        finally:
            # UIの状態を元に戻す
            self.master.after(0, self.set_ui_processing, False)


    def save_result(self, minutes_text, original_filepath):
        """生成されたテキストをファイルに保存する"""
        # デフォルトのファイル名を提案 (元のファイル名 + _minutes.md)
        base, _ = os.path.splitext(original_filepath)
        default_filename = f"{os.path.basename(base)}_minutes.md"
        initial_dir = os.path.dirname(original_filepath)

        save_path = filedialog.asksaveasfilename(
            title="議事録を保存",
            initialdir=initial_dir,
            initialfile=default_filename,
            defaultextension=".md",
            filetypes=(("Markdown ファイル", "*.md"), ("テキストファイル", "*.txt"), ("すべてのファイル", "*.*"))
        )

        if save_path:
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(minutes_text)
                self.update_status(f"議事録を保存しました: {os.path.basename(save_path)}")
                # 保存完了後、進捗を100%のままにしておくか、リセットするかはお好みで
                self.update_progress(100, "保存完了")
                messagebox.showinfo("成功", f"議事録を保存しました:\n{save_path}")
            except Exception as e:
                error_message = f"ファイルの保存中にエラーが発生しました:\n{e}"
                messagebox.showerror("保存エラー", error_message)
                self.update_status("ファイルの保存中にエラーが発生しました。")
                self.update_progress(0, "保存エラー") # 保存エラー時はリセット
        else:
            self.update_status("ファイル保存がキャンセルされました。")
            # キャンセル時は進捗を100%のままにするか、リセットするか
            # self.update_progress(100, "生成完了 (保存キャンセル)")
            self.progress_var.set(0) # キャンセル時はリセットする


    def start_generation(self):
        """議事録生成処理を開始する"""
        if self.is_processing: return # 既に処理中なら何もしない

        filepath = self.selected_file_path.get()
        if not filepath:
            messagebox.showwarning("ファイル未選択", "音声/動画ファイルを選択してください。")
            return
        # APIキーチェック (環境変数)
        if not self.api_key:
             messagebox.showerror("APIキーエラー", "環境変数 GOOGLE_API_KEY が設定されていません。\n実行前に設定してください。")
             return

        # スレッドを作成して実行
        thread = threading.Thread(target=self.generation_thread, args=(filepath,), daemon=True)
        thread.start()


# --- アプリケーションの起動 ---
if __name__ == "__main__":
    root = tk.Tk()
    app = MinutesApp(root)
    root.mainloop()