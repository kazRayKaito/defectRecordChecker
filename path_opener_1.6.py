import tkinter as tk
from tkinter import messagebox
import os
import re
import glob
import csv
import configparser
from datetime import datetime, date
from PIL import Image, ImageTk

#シリアル例：02210620750025100104002715

# ── Constants ─────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR  = os.path.join(BASE_DIR, "NGワーク再検査結果")
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")

C_DONE   = "#22C55E"
C_AVAIL  = "#2563EB"
C_LOCKED = "#D1D5DB"
C_NG     = "#EF4444"
C_WHITE  = "#FFFFFF"
C_TEXT   = "#1F2937"
C_MUTED  = "#6B7280"
C_BG     = "#F9FAFB"

# ── Config helpers ─────────────────────────────────────────────────────────────
def load_config():
    cfg = configparser.ConfigParser()
    if os.path.exists(CONFIG_PATH):
        cfg.read(CONFIG_PATH, encoding='utf-8')
    return cfg.get('Settings', 'root_path', fallback='')

def save_config(root_path):
    cfg = configparser.ConfigParser()
    cfg['Settings'] = {'root_path': root_path}
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        cfg.write(f)

def load_defect_modes():
    cfg = configparser.ConfigParser()
    if os.path.exists(CONFIG_PATH):
        cfg.read(CONFIG_PATH, encoding='utf-8')
    fallback = 'その他,キズ,打痕,異物,汚れ,巣,割れ,ピン曲がり,変色,接着剤欠け,接着剤タレ,接着剤不足'
    modes_str = cfg.get('DefectModes', 'modes', fallback=fallback)
    return [m.strip() for m in modes_str.split(',') if m.strip()][:56]

def save_defect_modes(modes):
    cfg = configparser.ConfigParser()
    if os.path.exists(CONFIG_PATH):
        cfg.read(CONFIG_PATH, encoding='utf-8')
    if 'Settings' not in cfg:
        cfg['Settings'] = {}
    cfg['DefectModes'] = {'modes': ','.join(modes)}
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        cfg.write(f)

# ── Serial / path resolution ───────────────────────────────────────────────────
def extract_date_from_serial(serial):
    """先頭6桁(YYMMDD)からdate型を返す。失敗時はNoneを返す。"""
    try:
        yy = int(serial[12:14])
        mm = int(serial[14:16])
        dd = int(serial[16:18])
        return date(2000 + yy, mm, dd)
    except (ValueError, IndexError):
        return None

def find_capture_folder_from_serial(serial, root):
    """
    画像フォルダとResultファイルの該当する行を検索する。
    serialは26桁 02210620750025100104002714
    01 210620-7500 YYMMDD 0100 SSSS
    Capture/YYYY-MM/yyyy-mm-DD_______SSSS/ の形式でワークフォルダを検索する。
    シリアル日付(YYMMDD)以降の月フォルダのみを対象とする。
    見つかった場合は画像フォルダパスとResultファイルパスを、見つからない場合はNoneを返す。
    """
    serial_date = extract_date_from_serial(serial)
    if serial_date is None:
        return None

    candidate_months = []
    try:
        for entry in os.scandir(root):
            if entry.is_dir() and re.fullmatch(r"\d{4}-\d{2}", entry.name):
                try:
                    month_date = datetime.strptime(entry.name, "%Y-%m").date()
                    if (month_date.year, month_date.month) >= (serial_date.year, serial_date.month):
                        candidate_months.append(((month_date.year, month_date.month), entry.path))
                except ValueError:
                    pass
    except (PermissionError, FileNotFoundError):
        return None

    yymmdd = serial[12:18]
    ssss   = serial[-4:]
    suffix = f"{yymmdd}00{ssss}"

    for _, month_folder in sorted(candidate_months):
        try:
            for day_folder in os.scandir(month_folder):
                if not day_folder.is_dir():
                    continue
                for folder in os.scandir(day_folder):
                    if not folder.is_dir():
                        continue
                    if len(folder.name) >= 12 and folder.name[-12:] == suffix and folder.name[-12:].isdigit():
                        month_folder_name = os.path.basename(month_folder)
                        date_folder_name = day_folder.name
                        csv_file_path = os.path.join(root, month_folder_name, date_folder_name + ".csv")
                        if not os.path.exists(csv_file_path):
                            continue
                        return [folder.path, csv_file_path, suffix]
        except PermissionError:
            continue

    return None

def find_if_already_checked(serial_12):
    serial_12 = str(serial_12).strip()
    if not serial_12 or len(serial_12) != 12:
        return None

    if not os.path.isdir(RESULT_DIR):
        return None

    for csv_path in sorted(glob.glob(os.path.join(RESULT_DIR, "*.csv"))):
        name = os.path.basename(csv_path)
        stem, _ = os.path.splitext(name)
        if stem.endswith(serial_12):
            return name
    return None

# ── CSV reader ─────────────────────────────────────────────────────────────────
def load_result_csv(csvFilePath, serial, imageCount):
    """
    csvFilePath のCSVを読み込み、A列(0列目)が serial と一致する行を探す。
    一致行があれば、その行のJ列(9列目)以降を左から順に確認し、
    値が -1 または 1 の間だけ最大20個まで int として配列に格納して返す。

    戻り値: (results_list, error_message)
      results_list ... [-1, 1, -1, ...] 要素数はimageCount
      error_message ... 失敗時のみ文字列、成功時は None
    """
    if not os.path.exists(csvFilePath):
        return None, f"CSV が見つかりません:\n{csvFilePath}"

    try:
        rows = None
        for enc in ('utf-8-sig', 'utf-8', 'shift-jis', 'cp932'):
            try:
                with open(csvFilePath, 'r', encoding=enc, newline='') as f:
                    rows = list(csv.reader(f))
                break
            except UnicodeDecodeError:
                continue
        if rows is None:
            return None, "CSV の文字コードを読み取れませんでした。"
        if not rows:
            return None, "CSV にデータ行がありません。"

        def parse_pm_one(cell):
            s = str(cell).strip()
            if s == "-1":
                return 'NG'
            elif s == "1":
                return 'OK'
            return None

        target_row = None
        serial_str = str(serial).strip()
        for r in rows:
            if r and len(r) >= 1 and str(r[0]).strip() == serial_str:
                target_row = r
                break

        if target_row is None:
            return None, f"serial に一致する行が見つかりませんでした: {serial}"

        results = []
        for i in range(8, 8 + imageCount - 1):
            v = parse_pm_one(target_row[i])
            if v is None:
                break
            results.append(v)
            if len(results) >= 20:
                break

        return results, None

    except Exception as e:
        return None, f"CSV の読み込みエラー:\n{e}"

# ── Application state ─────────────────────────────────────────────────────────
def init_state():
    return {
        'captureRootDir':    load_config(),  # Captureルートフォルダのパス（config.ini）
        'caseSerial_26':     '',             # ケースシリアル26桁
        'caseSerial_12':     '',             # ケースシリアル12桁(YYMMDD00SSSS)
        'captureFolderPath': '',             # Captureフォルダのパス
        'captureImageCount': '',             # Captureフォルダ内の画像数
        'csvFilePath':       '',             # CSVファイルのパス

        'step1_done':        False,
        'ng_jpgs':           [],
        'ng_results':        [],
        'ng_defect_modes':   [],
        'step2_done':        False,
        'all_jpgs':          [],
        'all_results':       [],
        'step3_done':        False,
        'step4_done':        False,
    }

def reset_state(state_dict):
    state_dict.clear()
    state_dict.update(init_state())

state = init_state()
step_btns = {}

# ── Availability logic ────────────────────────────────────────────────────────
def ng_all_ok():
    return bool(state['ng_results']) and all(r == 'OK' for r in state['ng_results'])

def step2_avail(): return state['step1_done']
def step3_avail(): return state['step2_done'] and ng_all_ok()
def step4_avail(): return state['step2_done'] and (state['step3_done'] or not ng_all_ok())

# ── Generic UI helpers ────────────────────────────────────────────────────────
def show_popup(msg, title="確認", parent=None):
    dlg = tk.Toplevel(parent or root)
    dlg.transient(parent or root)
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.configure(bg=C_BG)
    tk.Label(dlg, text=msg,
             bg=C_BG, fg=C_NG, font=("Arial", 24, "bold"), padx=30, pady=24).pack()
    tk.Button(dlg, text="OK", command=dlg.destroy,
              bg=C_AVAIL, fg=C_WHITE, font=("Arial", 24, "bold"),
              relief=tk.FLAT, padx=20, pady=8).pack(pady=(0, 20))
    dlg.update_idletasks()
    w = dlg.winfo_reqwidth()
    h = dlg.winfo_reqheight()
    x = (dlg.winfo_screenwidth()  - w) // 2
    y = (dlg.winfo_screenheight() - h) // 2
    dlg.geometry(f"+{x}+{y}")
    dlg.grab_set()
    dlg.wait_window()

def ask_popup(msg, parent=None):
    result = [False]
    dlg = tk.Toplevel(parent or root)
    dlg.title("確認")
    dlg.resizable(False, False)
    dlg.configure(bg=C_BG)
    tk.Label(dlg, text=msg,
             bg=C_BG, fg=C_TEXT, font=("Arial", 24, "bold"), padx=30, pady=24).pack()
    btn_row = tk.Frame(dlg, bg=C_BG)
    btn_row.pack(pady=(0, 20))
    def yes():
        result[0] = True
        dlg.destroy()
    tk.Button(btn_row, text="はい", command=yes,
              bg=C_AVAIL, fg=C_WHITE, font=("Arial", 24, "bold"),
              relief=tk.FLAT, padx=20, pady=8).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_row, text="いいえ", command=dlg.destroy,
              bg=C_MUTED, fg=C_WHITE, font=("Arial", 24, "bold"),
              relief=tk.FLAT, padx=20, pady=8).pack(side=tk.LEFT, padx=10)
    dlg.update_idletasks()
    w = dlg.winfo_reqwidth()
    h = dlg.winfo_reqheight()
    x = (dlg.winfo_screenwidth()  - w) // 2
    y = (dlg.winfo_screenheight() - h) // 2
    dlg.geometry(f"+{x}+{y}")
    dlg.grab_set()
    dlg.wait_window()
    return result[0]

def show_defect_mode_picker(parent, modes):
    """Modal grid of defect mode buttons (up to 56, 7 cols × 8 rows). Returns selected mode or None if cancelled."""
    result = [None]

    dlg = tk.Toplevel(parent)
    dlg.title("不良モード選択")
    dlg.configure(bg=C_BG)
    dlg.resizable(False, False)

    tk.Label(dlg, text="不良モードを選択してください",
             bg=C_BG, fg=C_TEXT, font=("Arial", 13, "bold"), pady=14).pack()

    btn_frame = tk.Frame(dlg, bg=C_BG, padx=16, pady=4)
    btn_frame.pack()

    COLS = 7
    for idx, mode in enumerate(modes[:56]):
        row, col = divmod(idx, COLS)
        def make_cmd(m):
            def cmd():
                result[0] = m
                dlg.destroy()
            return cmd
        tk.Button(btn_frame, text=mode, command=make_cmd(mode),
                  bg=C_NG, fg=C_WHITE, font=("Arial", 11, "bold"),
                  relief=tk.FLAT, width=10, pady=10).grid(
                      row=row, column=col, padx=4, pady=4)

    tk.Frame(dlg, bg=C_MUTED, height=1).pack(fill=tk.X, padx=16, pady=(12, 0))

    new_mode_frame = tk.Frame(dlg, bg=C_BG, padx=16, pady=10)
    new_mode_frame.pack(fill=tk.X)

    tk.Label(new_mode_frame, text="新規モード手書き入力:",
             bg=C_BG, fg=C_TEXT, font=("Arial", 11)).pack(side=tk.LEFT, padx=(0, 8))

    new_mode_entry = tk.Entry(new_mode_frame, font=("Arial", 11), width=20)
    new_mode_entry.pack(side=tk.LEFT, padx=(0, 8))

    def submit_new_mode():
        new_mode = new_mode_entry.get().strip()
        if not new_mode:
            return
        updated = load_defect_modes()
        if new_mode not in updated:
            updated.append(new_mode)
            save_defect_modes(updated)
        result[0] = new_mode
        dlg.destroy()

    tk.Button(new_mode_frame, text="登録して選択", command=submit_new_mode,
              bg=C_AVAIL, fg=C_WHITE, font=("Arial", 11, "bold"),
              relief=tk.FLAT, padx=12, pady=6).pack(side=tk.LEFT)

    new_mode_entry.bind('<Return>', lambda _: submit_new_mode())

    tk.Button(dlg, text="キャンセル (NG取消)", command=dlg.destroy,
              bg=C_MUTED, fg=C_WHITE, font=("Arial", 11),
              relief=tk.FLAT, padx=16, pady=8).pack(pady=(8, 16))

    dlg.update_idletasks()
    w = dlg.winfo_reqwidth()
    h = dlg.winfo_reqheight()
    x = (dlg.winfo_screenwidth()  - w) // 2
    y = (dlg.winfo_screenheight() - h) // 2
    dlg.geometry(f"+{x}+{y}")
    dlg.grab_set()
    dlg.wait_window()
    return result[0]

# ── Main window refresh ───────────────────────────────────────────────────────
def refresh_main():
    config = [
        ('step1', True,           state['step1_done'], open_step1, 'STEP 1\nケースQR読取'),
        ('step2', step2_avail(),  state['step2_done'], open_step2, 'STEP 2\nNG画像確認'),
        ('step3', step3_avail(),  state['step3_done'], open_step3, 'STEP 3\n全画像確認'),
        ('step4', step4_avail(),  state['step4_done'], open_step4, 'STEP 4\n結果出力'),
    ]
    for key, avail, done, cmd, base in config:
        btn = step_btns[key]
        text = base + ('\n✓ 完了' if done else '')
        if done:
            btn.config(text=text, bg=C_DONE, fg=C_WHITE,
                       activebackground=C_DONE, activeforeground=C_WHITE,
                       command=lambda: None, cursor='arrow')
        elif avail:
            btn.config(text=text, bg=C_AVAIL, fg=C_WHITE,
                       activebackground='#1D4ED8', activeforeground=C_WHITE,
                       command=cmd, cursor='hand2')
        else:
            btn.config(text=text, bg=C_LOCKED, fg=C_MUTED,
                       activebackground=C_LOCKED, activeforeground=C_MUTED,
                       command=lambda: None, cursor='arrow')

# ── STEP 1: serial input window ───────────────────────────────────────────────
def open_step1():
    win = tk.Toplevel(root)
    win.title("STEP 1 — ケースQR読取")
    win.geometry("520x220")
    win.resizable(False, False)
    win.grab_set()
    win.configure(bg=C_BG)

    frm = tk.Frame(win, padx=20, pady=16, bg=C_BG)
    frm.pack(fill=tk.BOTH, expand=True)

    tk.Label(frm, text="Captureフォルダパス（config.ini）",
             bg=C_BG, fg=C_MUTED, font=("Arial", 8)).pack(anchor='w')

    root_row = tk.Frame(frm, bg=C_BG)
    root_row.pack(fill=tk.X, pady=(2, 10))

    root_entry = tk.Entry(root_row, width=44, font=("Arial", 10))
    root_entry.pack(side=tk.LEFT, padx=(0, 8))
    root_entry.insert(0, state['captureRootDir'])

    def save_root():
        r = root_entry.get().strip()
        if not os.path.isdir(r):
            messagebox.showerror("エラー", f"Captureフォルダが存在しません:\n{r}", parent=win)
            return
        state['captureRootDir'] = r
        save_config(r)
        messagebox.showinfo("保存", "Captureフォルダパスを保存しました。", parent=win)

    tk.Button(root_row, text="保存", command=save_root,
              bg="#6B7280", fg=C_WHITE, font=("Arial", 9),
              relief=tk.FLAT, padx=8, pady=4).pack(side=tk.LEFT)

    tk.Label(frm, text="ワークシリアル番号（26桁）",
             bg=C_BG, fg=C_TEXT, font=("Arial", 10)).pack(anchor='w', pady=(0, 4))

    serial_row = tk.Frame(frm, bg=C_BG)
    serial_row.pack(fill=tk.X)

    serial_entry = tk.Entry(serial_row, width=20, font=("Arial", 14))
    serial_entry.pack(side=tk.LEFT, padx=(0, 8))
    serial_entry.insert(0, state['caseSerial_26'] or '02210620750025100104002715')
    serial_entry.focus_set()

    status_lbl = tk.Label(frm, text="", bg=C_BG, font=("Arial", 9))
    status_lbl.pack(anchor='w', pady=(6, 0))

    def confirm():
        serial = serial_entry.get().strip()

        if not re.match(r'^\d{26}$', serial):
            status_lbl.config(text="✗ 26桁の数字を入力してください", fg=C_NG)
            return

        serial_date = extract_date_from_serial(serial)
        if serial_date is None:
            status_lbl.config(text="✗ シリアルの日付部分(13~18桁目)が不正です", fg=C_NG)
            return

        root_path = state['captureRootDir']
        if not root_path or not os.path.isdir(root_path):
            status_lbl.config(text="✗ ルートフォルダを先に設定・保存してください", fg=C_NG)
            return

        status_lbl.config(text="検索中...", fg=C_MUTED)
        win.update()

        result = find_capture_folder_from_serial(serial, root_path)
        if result is None:
            status_lbl.config(
                text=f"✗ シリアル {serial} に一致するフォルダが見つかりません", fg=C_NG)
            return

        recordResult = find_if_already_checked(result[2])
        if recordResult is not None:
            status_lbl.config(
                text=f"✗ 既に再検査記録があります。 \n{recordResult} ", fg=C_NG)
            return

        state['caseSerial_26']      = serial
        state['captureFolderPath']  = result[0]
        state['csvFilePath']        = result[1]
        state['caseSerial_12']      = result[2]
        state['step1_done'] = True
        win.destroy()
        refresh_main()

    tk.Button(serial_row, text="確認", command=confirm,
              bg=C_AVAIL, fg=C_WHITE, font=("Arial", 10, "bold"),
              relief=tk.FLAT, padx=14, pady=5).pack(side=tk.LEFT)

    win.bind('<Return>', lambda _: confirm())

# ── Generic image review window (STEP 2 & 3) ─────────────────────────────────
def open_image_review(title, jpgs, results_key, done_key, defect_modes_key=None):
    prev = state.get(results_key) or []
    results = list(prev) if len(prev) == len(jpgs) else [None] * len(jpgs)

    prev_modes = (state.get(defect_modes_key) or []) if defect_modes_key else []
    defect_modes = list(prev_modes) if len(prev_modes) == len(jpgs) else [None] * len(jpgs)

    win = tk.Toplevel(root)
    win.title(title)
    win.configure(bg=C_BG)
    win.state('zoomed')
    win.grab_set()

    cur = [0]

    top_bar = tk.Frame(win, bg=C_BG, pady=8)
    top_bar.pack(fill=tk.X, padx=16)

    counter_lbl = tk.Label(top_bar, text="", bg=C_BG, fg=C_TEXT,
                            font=("Arial", 10, "bold"))
    counter_lbl.pack(side=tk.LEFT)

    result_lbl = tk.Label(top_bar, text="", bg=C_BG,
                           font=("Arial", 10, "bold"))
    result_lbl.pack(side=tk.RIGHT)

    btn_frame = tk.Frame(win, bg=C_BG, pady=10)
    btn_frame.pack(side=tk.BOTTOM)

    img_frame = tk.Frame(win, bg="#E5E7EB")
    img_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 4))

    img_lbl = tk.Label(img_frame, bg="#E5E7EB")
    img_lbl.place(relx=0.5, rely=0.5, anchor='center')

    def show(i):
        cur[0] = i
        fw = img_frame.winfo_width()  or win.winfo_screenwidth()
        fh = img_frame.winfo_height() or win.winfo_screenheight()
        try:
            img = Image.open(jpgs[i])
            img.thumbnail((fw, fh))
            photo = ImageTk.PhotoImage(img)
            img_lbl.config(image=photo)
            img_lbl.image = photo
        except Exception as e:
            img_lbl.config(image='', text=f"読込エラー: {e}", fg="red")

        counter_lbl.config(text=f"[{i + 1} / {len(jpgs)}]  {os.path.basename(jpgs[i])}")
        r = results[i]
        result_lbl.config(
            text=f"判定: {r}" if r else "未判定",
            fg=C_DONE if r == 'OK' else C_NG if r == 'NG' else C_MUTED
        )

    def record(result_val):
        if result_val == 'NG' and defect_modes_key:
            mode = show_defect_mode_picker(win, load_defect_modes())
            if mode is None:
                return  # cancelled — stay on current image
            defect_modes[cur[0]] = mode
            state[defect_modes_key] = list(defect_modes)
        results[cur[0]] = result_val
        state[results_key] = list(results)
        i = cur[0]
        if i < len(jpgs) - 1:
            show(i + 1)
        else:
            finish()

    def on_back():
        if cur[0] > 0:
            show(cur[0] - 1)
        else:
            if messagebox.askyesno("確認", "判定を中断しますか？", parent=win):
                win.destroy()

    def finish():
        state[results_key] = list(results)
        state[done_key] = True
        win.destroy()
        refresh_main()

    def on_close():
        if messagebox.askyesno("確認", "判定を中断しますか？\n判定結果は保存されません。", parent=win):
            win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_close)

    tk.Button(btn_frame, text="OK", command=lambda: record('OK'),
              bg=C_DONE, fg=C_WHITE, font=("Arial", 13, "bold"),
              relief=tk.FLAT, width=9, pady=8).pack(side=tk.LEFT, padx=10)

    tk.Button(btn_frame, text="NG", command=lambda: record('NG'),
              bg=C_NG, fg=C_WHITE, font=("Arial", 13, "bold"),
              relief=tk.FLAT, width=9, pady=8).pack(side=tk.LEFT, padx=10)

    tk.Button(btn_frame, text="戻る", command=on_back,
              bg="#6B7280", fg=C_WHITE, font=("Arial", 13),
              relief=tk.FLAT, width=9, pady=8).pack(side=tk.LEFT, padx=10)

    win.after(100, lambda: show(0))

# ── STEP 2: NG image review ───────────────────────────────────────────────────
def open_step2():
    all_dir = state['captureFolderPath']
    if not os.path.isdir(all_dir):
        messagebox.showerror("エラー", f"{all_dir}フォルダが見つかりません:\n{all_dir}")
        return

    all_jpgs = sorted(
        [f for f in glob.glob(os.path.join(all_dir, "*"))
         if os.path.splitext(f)[1].lower() in ('.jpg', '.jpeg', '.png', '.bmp')],
        key=lambda p: (
            int(re.search(r'_p(\d+)_', os.path.basename(p), re.IGNORECASE).group(1))
            if re.search(r'_p(\d+)_', os.path.basename(p), re.IGNORECASE) else 10**9,
            os.path.basename(p).lower()
        )
    )
    if not all_jpgs:
        messagebox.showinfo("情報", f"{all_dir}フォルダに画像ファイルが見つかりませんでした。")
        return

    state['captureImageCount'] = len(all_jpgs)

    csv_results, err = load_result_csv(state['csvFilePath'], state['caseSerial_12'], state['captureImageCount'])
    if err:
        messagebox.showerror("エラー", err)
        return

    ng_jpgs = [
        all_jpgs[i] for i, r in enumerate(csv_results)
        if r == 'NG' and i < len(all_jpgs)
    ]

    if not ng_jpgs:
        messagebox.showwarning(
            "確認エラー",
            "NG判定された画像が存在しません。\nワークの素性を確認してください。"
        )
        return

    state['ng_jpgs'] = ng_jpgs

    show_popup(f"NG画像が{len(ng_jpgs)}枚あります。\n「現物」を確認し、良否を判定してください。")
    open_image_review("STEP 2 — NG画像確認", ng_jpgs, 'ng_results', 'step2_done', defect_modes_key='ng_defect_modes')

# ── STEP 3: All image review ──────────────────────────────────────────────────
def open_step3():
    all_dir = state['captureFolderPath']
    if not os.path.isdir(all_dir):
        messagebox.showerror("エラー", f"{all_dir}フォルダが見つかりません:\n{all_dir}")
        return

    jpgs = sorted(
        [f for f in glob.glob(os.path.join(all_dir, "*"))
         if os.path.splitext(f)[1].lower() in ('.jpg', '.jpeg', '.png', '.bmp')],
        key=lambda p: (
            int(re.search(r'_p(\d+)_', os.path.basename(p), re.IGNORECASE).group(1))
            if re.search(r'_p(\d+)_', os.path.basename(p), re.IGNORECASE) else 10**9,
            os.path.basename(p).lower()
        )
    )
    if not jpgs:
        messagebox.showinfo("情報", f"{all_dir}フォルダに画像ファイルが見つかりませんでした。")
        return

    state['all_jpgs'] = jpgs

    show_popup(f"最終全体検査\n\n各画像の部位に欠陥がないことを\n「現物」で確認してください。\n画像は全部で{state['captureImageCount']}枚あります。")
    open_image_review("STEP 3 — 全画像確認", jpgs, 'all_results', 'step3_done', defect_modes_key='ng_defect_modes')

# ── STEP 4: Result output ─────────────────────────────────────────────────────
def open_step4():
    def close():
        ans = ask_popup("ワークの処置は完了しましたか？", parent=win)
        if ans:
            reset_state(state)
            win.destroy()
            refresh_main()
        else:
            show_popup("ワークを処置してからウィンドを閉じてください", parent=win)

    win = tk.Toplevel(root)
    win.title("STEP 4 — 結果出力")
    win.configure(bg=C_BG)
    win.resizable(True, True)

    tk.Button(win, text="Windowを閉じる", command=close,
              bg=C_AVAIL, fg=C_WHITE, font=("Arial", 11, "bold"),
              relief=tk.FLAT, padx=16, pady=8).pack(side=tk.BOTTOM, pady=12)

    tk.Label(win, text="検査結果サマリー", bg=C_BG, fg=C_TEXT,
             font=("Arial", 12, "bold")).pack(pady=(16, 8))

    txt_frame = tk.Frame(win, bg=C_WHITE, relief=tk.SOLID, bd=1)
    txt_frame.pack(side=tk.TOP, padx=20, fill=tk.BOTH, expand=True)

    txt = tk.Text(txt_frame, bg=C_WHITE, fg=C_TEXT, font=("Courier", 9),
                  relief=tk.FLAT, state=tk.DISABLED, padx=8, pady=8)
    sb = tk.Scrollbar(txt_frame, command=txt.yview)
    txt.configure(yscrollcommand=sb.set)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    txt.pack(fill=tk.BOTH, expand=True)

    ng_ok  = sum(1 for r in state['ng_results']  if r == 'OK')
    ng_ng  = sum(1 for r in state['ng_results']  if r == 'NG')
    all_ok = sum(1 for r in state['all_results'] if r == 'OK')
    all_ng = sum(1 for r in state['all_results'] if r == 'NG')

    ng_modes = state.get('ng_defect_modes') or []

    lines = [
        f"検査日時 : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"シリアル : {state['caseSerial_26']}",
        f"フォルダ : {state['captureFolderPath']}",
        "",
        f"── NG画像確認  OK:{ng_ok}  NG:{ng_ng} ──────────────",
    ]
    for i, (jpg, res) in enumerate(zip(state['ng_jpgs'], state['ng_results'])):
        mark = "✓" if res == 'OK' else "✗"
        mode = ng_modes[i] if i < len(ng_modes) and res == 'NG' else ''
        suffix = f"  ({mode})" if mode else ''
        lines.append(f"  {mark} {os.path.basename(jpg):<30} [{res}]{suffix}")

    lines += [
        "",
        f"── 全画像確認  OK:{all_ok}  NG:{all_ng} ──────────────",
    ]
    for jpg, res in zip(state['all_jpgs'], state['all_results']):
        mark = "✓" if res == 'OK' else "✗"
        lines.append(f"  {mark} {os.path.basename(jpg):<30} [{res}]")

    txt.config(state=tk.NORMAL)
    txt.insert('1.0', '\n'.join(lines))
    txt.config(state=tk.DISABLED)

    os.makedirs(RESULT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    csv_path = os.path.join(RESULT_DIR, f"{ts}_{state['caseSerial_12']}.csv")

    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['検査日時', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow(['シリアル番号', state['caseSerial_26']])
        writer.writerow(['フォルダパス', state['captureFolderPath']])
        writer.writerow([])
        writer.writerow(['種別', 'ファイル名', '判定', '不良モード'])
        for i, (jpg, res) in enumerate(zip(state['ng_jpgs'], state['ng_results'])):
            mode = ng_modes[i] if i < len(ng_modes) and res == 'NG' else ''
            writer.writerow(['NG画像', os.path.basename(jpg), res or '', mode])
        for jpg, res in zip(state['all_jpgs'], state['all_results']):
            writer.writerow(['全画像', os.path.basename(jpg), res or '', ''])

    win.update_idletasks()
    w, h = 480, 588
    x = (win.winfo_screenwidth() - w) // 2
    win.geometry(f"{w}x{h}+{x}+0")
    win.minsize(w, h)
    win.grab_set()

    show_popup("結果を保存しました:\n必ずワークを処置してからウィンドを閉じてください", title="保存完了", parent=win)

# ── Main window ───────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("不良再検査ﾌﾟﾛｸﾞﾗﾑ")
root.geometry("380x480")
root.resizable(False, False)
root.configure(bg=C_BG)

tk.Label(root, text="不良再検査ﾌﾟﾛｸﾞﾗﾑ", bg=C_BG, fg=C_TEXT,
         font=("Arial", 12, "bold")).pack(pady=(20, 12))

for key, label in [
    ('step1', 'STEP 1\nケースQR読取'),
    ('step2', 'STEP 2\nNG画像確認'),
    ('step3', 'STEP 3\n全画像確認'),
    ('step4', 'STEP 4\n結果出力'),
]:
    btn = tk.Button(root, text=label,
                    bg=C_LOCKED, fg=C_MUTED,
                    font=("Arial", 12, "bold"),
                    relief=tk.FLAT, width=26,
                    padx=16, pady=12,
                    activebackground=C_LOCKED, activeforeground=C_MUTED,
                    command=lambda: None, cursor='arrow')
    btn.pack(pady=5)
    step_btns[key] = btn

refresh_main()
root.mainloop()
