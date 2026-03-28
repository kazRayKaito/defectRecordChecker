import tkinter as tk
from tkinter import messagebox
import os
import re
import glob
import csv
import configparser
from datetime import datetime, date
from PIL import Image, ImageTk

# ── Constants ─────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR  = os.path.join(BASE_DIR, "result")
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")

# Sub-folder names inside the work folder
ALL_FOLDER    = "All_images"
WORK_RESULT   = "result.csv"    # CSV inside the work folder (input)

C_DONE   = "#22C55E"
C_AVAIL  = "#2563EB"
C_LOCKED = "#D1D5DB"
C_NG     = "#EF4444"
C_WHITE  = "#FFFFFF"
C_TEXT   = "#1F2937"
C_MUTED  = "#6B7280"
C_BG     = "#F9FAFB"

# ── Config file helpers ────────────────────────────────────────────────────────
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

# ── Serial / path resolution ───────────────────────────────────────────────────
def extract_date_from_serial(serial):
    """先頭6桁(YYMMDD)からdate型を返す。失敗時はNoneを返す。"""
    try:
        yy = int(serial[0:2])
        mm = int(serial[2:4])
        dd = int(serial[4:6])
        return date(2000 + yy, mm, dd)
    except (ValueError, IndexError):
        return None

def find_work_path(serial, root):
    """
    root/YYYYMMDD/[*serial*]/ の形式でワークフォルダを検索する。
    シリアル先頭6桁(YYMMDD)以降の日付フォルダのみを対象とする。
    見つかった場合はそのフォルダパス、見つからない場合はNoneを返す。
    """
    serial_date = extract_date_from_serial(serial)
    if serial_date is None:
        return None

    # ルート直下のYYYYMMDDフォルダを収集
    candidate_dates = []
    try:
        for entry in os.scandir(root):
            if entry.is_dir() and re.match(r'^\d{8}$', entry.name):
                try:
                    folder_date = datetime.strptime(entry.name, "%Y%m%d").date()
                    if folder_date >= serial_date:
                        candidate_dates.append((folder_date, entry.path))
                except ValueError:
                    pass
    except (PermissionError, FileNotFoundError):
        return None

    # 日付昇順で走査し、シリアルを含むサブフォルダを探す
    for _, date_folder in sorted(candidate_dates):
        try:
            for entry in os.scandir(date_folder):
                if entry.is_dir() and serial in entry.name:
                    return entry.path
        except PermissionError:
            continue

    return None

# ── Application state ─────────────────────────────────────────────────────────
state = {
    'root':        load_config(),   # root path from config.ini
    'serial':      '',
    'path':        '',              # resolved work folder path
    'step1_done':  False,
    'ng_jpgs':     [],
    'ng_results':  [],
    'step2_done':  False,
    'all_jpgs':    [],
    'all_results': [],
    'step3_done':  False,
    'step4_done':  False,
}

step_btns = {}

# ── result.csv reader ─────────────────────────────────────────────────────────
def load_result_csv(work_path):
    """
    ワークフォルダ内の result.csv を読み込む。
    行構成:
      0行目: 判定日時,  {値}
      1行目: ワークシリアル, {値}
      2〜21行目: 1枚目結果〜20枚目結果,  {OK / NG / -}
    戻り値: (results_list, error_message)
      results_list ... ['OK','NG','-',...] 最大20件
      error_message ... 失敗時のみ文字列、成功時は None
    """
    csv_path = os.path.join(work_path, WORK_RESULT)
    if not os.path.exists(csv_path):
        return None, f"result.csv が見つかりません:\n{csv_path}"
    try:
        rows = None
        for enc in ('utf-8-sig', 'utf-8', 'shift-jis', 'cp932'):
            try:
                with open(csv_path, 'r', encoding=enc, newline='') as f:
                    rows = list(csv.reader(f))
                break
            except UnicodeDecodeError:
                continue
        if rows is None:
            return None, "result.csv の文字コードを読み取れませんでした。"
        if len(rows) < 2:
            return None, "result.csv にデータ行がありません。"

        # データ行（2行目）の列2〜21が画像1枚目〜20枚目の結果
        data = rows[1]
        results = [data[i].strip() if i < len(data) else '-' for i in range(2, 22)]
        return results, None
    except Exception as e:
        return None, f"result.csv の読み込みエラー:\n{e}"


# ── Availability logic ────────────────────────────────────────────────────────
def ng_all_ok():
    # NG画像が0枚でSTEP2完了済みの場合もOKとする
    if state['step2_done'] and len(state['ng_jpgs']) == 0:
        return True
    return bool(state['ng_results']) and all(r == 'OK' for r in state['ng_results'])

def step2_avail(): return state['step1_done']
def step3_avail(): return state['step2_done'] and ng_all_ok()
def step4_avail(): return state['step2_done'] and state['step3_done']

# ── Main window refresh ───────────────────────────────────────────────────────
def refresh_main():
    config = [
        ('step1', True,            state['step1_done'], open_step1, 'STEP 1\nケースQR読取'),
        ('step2', step2_avail(),   state['step2_done'], open_step2, 'STEP 2\nNG画像確認'),
        ('step3', step3_avail(),   state['step3_done'], open_step3, 'STEP 3\n全画像確認'),
        ('step4', step4_avail(),   state['step4_done'], open_step4, 'STEP 4\n結果出力'),
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

    # ── Root path row ──
    tk.Label(frm, text="画像ルートフォルダ（config.ini）",
             bg=C_BG, fg=C_MUTED, font=("Arial", 8)).pack(anchor='w')

    root_row = tk.Frame(frm, bg=C_BG)
    root_row.pack(fill=tk.X, pady=(2, 10))

    root_entry = tk.Entry(root_row, width=44, font=("Arial", 10))
    root_entry.pack(side=tk.LEFT, padx=(0, 8))
    root_entry.insert(0, state['root'])

    def save_root():
        r = root_entry.get().strip()
        if not os.path.isdir(r):
            messagebox.showerror("エラー", f"ルートフォルダが存在しません:\n{r}", parent=win)
            return
        state['root'] = r
        save_config(r)
        messagebox.showinfo("保存", "ルートパスを保存しました。", parent=win)

    tk.Button(root_row, text="保存", command=save_root,
              bg="#6B7280", fg=C_WHITE, font=("Arial", 9),
              relief=tk.FLAT, padx=8, pady=4).pack(side=tk.LEFT)

    # ── Serial row ──
    tk.Label(frm, text="ワークシリアル番号（12桁）",
             bg=C_BG, fg=C_TEXT, font=("Arial", 10)).pack(anchor='w', pady=(0, 4))

    serial_row = tk.Frame(frm, bg=C_BG)
    serial_row.pack(fill=tk.X)

    serial_entry = tk.Entry(serial_row, width=20, font=("Arial", 14))
    serial_entry.pack(side=tk.LEFT, padx=(0, 8))
    if state['serial']:
        serial_entry.insert(0, state['serial'])
    serial_entry.focus_set()

    status_lbl = tk.Label(frm, text="", bg=C_BG, font=("Arial", 9))
    status_lbl.pack(anchor='w', pady=(6, 0))

    def confirm():
        serial = serial_entry.get().strip()

        # Validate: exactly 12 digits
        if not re.match(r'^\d{12}$', serial):
            status_lbl.config(text="✗ 12桁の数字を入力してください", fg=C_NG)
            return

        # Validate: date portion is valid
        serial_date = extract_date_from_serial(serial)
        if serial_date is None:
            status_lbl.config(text="✗ シリアルの日付部分(先頭6桁)が不正です", fg=C_NG)
            return

        # Validate: root is set
        root_path = state['root']
        if not root_path or not os.path.isdir(root_path):
            status_lbl.config(text="✗ ルートフォルダを先に設定・保存してください", fg=C_NG)
            return

        status_lbl.config(text="検索中...", fg=C_MUTED)
        win.update()

        work_path = find_work_path(serial, root_path)
        if work_path is None:
            status_lbl.config(
                text=f"✗ シリアル {serial} に一致するフォルダが見つかりません", fg=C_NG)
            return

        state['serial'] = serial
        state['path']   = work_path
        state['step1_done'] = True
        win.destroy()
        refresh_main()

    tk.Button(serial_row, text="確認", command=confirm,
              bg=C_AVAIL, fg=C_WHITE, font=("Arial", 10, "bold"),
              relief=tk.FLAT, padx=14, pady=5).pack(side=tk.LEFT)

    win.bind('<Return>', lambda e: confirm())

# ── Generic image review window (STEP 2 & 3) ─────────────────────────────────
def open_image_review(title, jpgs, results_key, done_key):
    prev = state.get(results_key) or []
    results = list(prev) if len(prev) == len(jpgs) else [None] * len(jpgs)

    win = tk.Toplevel(root)
    win.title(title)
    win.geometry("740x640")
    win.grab_set()
    win.configure(bg=C_BG)

    cur = [0]

    top_bar = tk.Frame(win, bg=C_BG, pady=8)
    top_bar.pack(fill=tk.X, padx=16)

    counter_lbl = tk.Label(top_bar, text="", bg=C_BG, fg=C_TEXT,
                            font=("Arial", 10, "bold"))
    counter_lbl.pack(side=tk.LEFT)

    result_lbl = tk.Label(top_bar, text="", bg=C_BG,
                           font=("Arial", 10, "bold"))
    result_lbl.pack(side=tk.RIGHT)

    img_frame = tk.Frame(win, bg="#E5E7EB", width=700, height=480)
    img_frame.pack(padx=20, pady=(0, 4))
    img_frame.pack_propagate(False)

    img_lbl = tk.Label(img_frame, bg="#E5E7EB")
    img_lbl.place(relx=0.5, rely=0.5, anchor='center')

    btn_frame = tk.Frame(win, bg=C_BG, pady=10)
    btn_frame.pack()

    def show(i):
        cur[0] = i
        try:
            img = Image.open(jpgs[i])
            img.thumbnail((680, 460))
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

    def record(result):
        results[cur[0]] = result
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

    show(0)

# ── STEP 2: NG image review (result.csv ベース) ───────────────────────────────
def open_step2():
    # All_images フォルダを読み込む
    all_dir = os.path.join(state['path'], ALL_FOLDER)
    if not os.path.isdir(all_dir):
        messagebox.showerror("エラー", f"{ALL_FOLDER}フォルダが見つかりません:\n{all_dir}")
        return
    all_jpgs = sorted([
        f for f in glob.glob(os.path.join(all_dir, "*"))
        if os.path.splitext(f)[1].lower() in ('.jpg', '.jpeg', '.png', '.bmp')
    ])
    if not all_jpgs:
        messagebox.showinfo("情報", f"{ALL_FOLDER}フォルダに画像ファイルが見つかりませんでした。")
        return

    # result.csv を読んで NG 画像を抽出
    csv_results, err = load_result_csv(state['path'])
    if err:
        messagebox.showerror("エラー", err)
        return

    ng_jpgs = [
        all_jpgs[i] for i, r in enumerate(csv_results)
        if r == 'NG' and i < len(all_jpgs)
    ]

    # NG 画像がない場合は異常として中断
    if not ng_jpgs:
        messagebox.showwarning(
            "確認エラー",
            "NG判定された画像が存在しません。\nワークの素性を確認してください。"
        )
        return

    state['ng_jpgs'] = ng_jpgs
    open_image_review("STEP 2 — NG画像確認", ng_jpgs, 'ng_results', 'step2_done')

# ── STEP 3: All image review ──────────────────────────────────────────────────
def open_step3():
    all_dir = os.path.join(state['path'], ALL_FOLDER)
    if not os.path.isdir(all_dir):
        messagebox.showerror("エラー", f"{ALL_FOLDER}フォルダが見つかりません:\n{all_dir}")
        return
    jpgs = sorted([
        f for f in glob.glob(os.path.join(all_dir, "*"))
        if os.path.splitext(f)[1].lower() in ('.jpg', '.jpeg', '.png', '.bmp')
    ])
    if not jpgs:
        messagebox.showinfo("情報", f"{ALL_FOLDER}フォルダに画像ファイルが見つかりませんでした。")
        return
    state['all_jpgs'] = jpgs
    open_image_review("STEP 3 — 全画像確認", jpgs, 'all_results', 'step3_done')

# ── STEP 4: Result output ─────────────────────────────────────────────────────
def open_step4():
    win = tk.Toplevel(root)
    win.title("STEP 4 — 結果出力")
    win.geometry("480x420")
    win.grab_set()
    win.configure(bg=C_BG)

    tk.Label(win, text="検査結果サマリー", bg=C_BG, fg=C_TEXT,
             font=("Arial", 12, "bold")).pack(pady=(16, 8))

    txt_frame = tk.Frame(win, bg=C_WHITE, relief=tk.SOLID, bd=1)
    txt_frame.pack(padx=20, fill=tk.BOTH, expand=True)

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

    lines = [
        f"検査日時 : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"シリアル : {state['serial']}",
        f"フォルダ : {state['path']}",
        "",
        f"── NG画像確認  OK:{ng_ok}  NG:{ng_ng} ──────────────",
    ]
    for jpg, res in zip(state['ng_jpgs'], state['ng_results']):
        mark = "✓" if res == 'OK' else "✗"
        lines.append(f"  {mark} {os.path.basename(jpg):<30} [{res}]")

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

    def save():
        os.makedirs(RESULT_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(RESULT_DIR, f"result_{ts}.csv")

        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['検査日時', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow(['シリアル番号', state['serial']])
            writer.writerow(['フォルダパス', state['path']])
            writer.writerow([])
            writer.writerow(['種別', 'ファイル名', '判定'])
            for jpg, res in zip(state['ng_jpgs'], state['ng_results']):
                writer.writerow(['NG画像', os.path.basename(jpg), res or ''])
            for jpg, res in zip(state['all_jpgs'], state['all_results']):
                writer.writerow(['全画像', os.path.basename(jpg), res or ''])

        state['step4_done'] = True
        win.destroy()
        refresh_main()
        messagebox.showinfo("保存完了", f"結果を保存しました:\n{csv_path}")

    tk.Button(win, text="CSVに保存して完了", command=save,
              bg=C_AVAIL, fg=C_WHITE, font=("Arial", 11, "bold"),
              relief=tk.FLAT, padx=16, pady=8).pack(pady=12)

# ── Main window ───────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("defectRecordChecker")
root.geometry("380x480")
root.resizable(False, False)
root.configure(bg=C_BG)

tk.Label(root, text="defectRecordChecker", bg=C_BG, fg=C_TEXT,
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
