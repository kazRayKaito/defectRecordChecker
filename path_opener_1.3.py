import tkinter as tk
from tkinter import messagebox
import os
import glob
import csv
from datetime import datetime
from PIL import Image, ImageTk

# ── Constants ─────────────────────────────────────────────────────────────────
RESULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "result")

C_DONE   = "#22C55E"   # green  – completed
C_AVAIL  = "#2563EB"   # blue   – available
C_LOCKED = "#D1D5DB"   # grey   – locked
C_NG     = "#EF4444"   # red    – NG judgment
C_WHITE  = "#FFFFFF"
C_TEXT   = "#1F2937"
C_MUTED  = "#6B7280"
C_BG     = "#F9FAFB"

# ── Application state ─────────────────────────────────────────────────────────
state = {
    'path':        '',
    'step1_done':  False,
    'ng_jpgs':     [],
    'ng_results':  [],   # list of 'OK' / 'NG' per image
    'step2_done':  False,
    'all_jpgs':    [],
    'all_results': [],   # list of 'OK' / 'NG' per image
    'step3_done':  False,
    'step4_done':  False,
}

step_btns = {}

# ── Availability logic ────────────────────────────────────────────────────────
def ng_all_ok():
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


# ── STEP 1: path input window ─────────────────────────────────────────────────
def open_step1():
    win = tk.Toplevel(root)
    win.title("STEP 1 — ケースQR読取")
    win.geometry("480x130")
    win.resizable(False, False)
    win.grab_set()
    win.configure(bg=C_BG)

    frm = tk.Frame(win, padx=20, pady=16, bg=C_BG)
    frm.pack(fill=tk.BOTH, expand=True)

    tk.Label(frm, text="フォルダパスを入力してください",
             bg=C_BG, fg=C_TEXT, font=("Arial", 10)).pack(anchor='w', pady=(0, 8))

    row = tk.Frame(frm, bg=C_BG)
    row.pack(fill=tk.X)

    entry = tk.Entry(row, width=42, font=("Arial", 10))
    entry.pack(side=tk.LEFT, padx=(0, 8))
    if state['path']:
        entry.insert(0, state['path'])
    entry.focus_set()

    def confirm():
        path = entry.get().strip()
        if not os.path.exists(path):
            messagebox.showerror("エラー", f"パスが存在しません:\n{path}", parent=win)
            return
        state['path'] = path
        state['step1_done'] = True
        win.destroy()
        refresh_main()

    tk.Button(row, text="確認", command=confirm,
              bg=C_AVAIL, fg=C_WHITE, font=("Arial", 10, "bold"),
              relief=tk.FLAT, padx=14, pady=5).pack(side=tk.LEFT)

    win.bind('<Return>', lambda e: confirm())


# ── Generic image review window (STEP 2 & 3) ─────────────────────────────────
def open_image_review(title, jpgs, results_key, done_key):
    # Restore previous partial results if they exist and match
    prev = state.get(results_key) or []
    results = list(prev) if len(prev) == len(jpgs) else [None] * len(jpgs)

    win = tk.Toplevel(root)
    win.title(title)
    win.geometry("740x640")
    win.grab_set()
    win.configure(bg=C_BG)

    cur = [0]

    # ── Top info bar ──
    top_bar = tk.Frame(win, bg=C_BG, pady=8)
    top_bar.pack(fill=tk.X, padx=16)

    counter_lbl = tk.Label(top_bar, text="", bg=C_BG, fg=C_TEXT,
                            font=("Arial", 10, "bold"))
    counter_lbl.pack(side=tk.LEFT)

    result_lbl = tk.Label(top_bar, text="", bg=C_BG,
                           font=("Arial", 10, "bold"))
    result_lbl.pack(side=tk.RIGHT)

    # ── Image area ──
    img_frame = tk.Frame(win, bg="#E5E7EB", width=700, height=480)
    img_frame.pack(padx=20, pady=(0, 4))
    img_frame.pack_propagate(False)

    img_lbl = tk.Label(img_frame, bg="#E5E7EB")
    img_lbl.place(relx=0.5, rely=0.5, anchor='center')

    # ── Button row ──
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


# ── STEP 2: NG image review ───────────────────────────────────────────────────
def open_step2():
    ng_dir = os.path.join(state['path'], "NG_images")
    if not os.path.isdir(ng_dir):
        messagebox.showerror("エラー", f"NG_imagesフォルダが見つかりません:\n{ng_dir}")
        return
    jpgs = sorted([
        f for f in glob.glob(os.path.join(ng_dir, "*"))
        if os.path.splitext(f)[1].lower() in ('.jpg', '.jpeg', '.png', '.bmp')
    ])
    if not jpgs:
        messagebox.showinfo("情報", "NG_imagesフォルダに画像ファイルが見つかりませんでした。")
        return
    state['ng_jpgs'] = jpgs
    open_image_review("STEP 2 — NG画像確認", jpgs, 'ng_results', 'step2_done')


# ── STEP 3: All image review ──────────────────────────────────────────────────
def open_step3():
    all_dir = os.path.join(state['path'], "All_images")
    if not os.path.isdir(all_dir):
        messagebox.showerror("エラー", f"All_imagesフォルダが見つかりません:\n{all_dir}")
        return
    jpgs = sorted([
        f for f in glob.glob(os.path.join(all_dir, "*"))
        if os.path.splitext(f)[1].lower() in ('.jpg', '.jpeg', '.png', '.bmp')
    ])
    if not jpgs:
        messagebox.showinfo("情報", "All_imagesフォルダに画像ファイルが見つかりませんでした。")
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

    # Summary text area
    txt_frame = tk.Frame(win, bg=C_WHITE, relief=tk.SOLID, bd=1)
    txt_frame.pack(padx=20, fill=tk.BOTH, expand=True)

    txt = tk.Text(txt_frame, bg=C_WHITE, fg=C_TEXT, font=("Courier", 9),
                  relief=tk.FLAT, state=tk.DISABLED, padx=8, pady=8)
    sb = tk.Scrollbar(txt_frame, command=txt.yview)
    txt.configure(yscrollcommand=sb.set)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    txt.pack(fill=tk.BOTH, expand=True)

    # Build summary
    ng_ok  = sum(1 for r in state['ng_results']  if r == 'OK')
    ng_ng  = sum(1 for r in state['ng_results']  if r == 'NG')
    all_ok = sum(1 for r in state['all_results'] if r == 'OK')
    all_ng = sum(1 for r in state['all_results'] if r == 'NG')

    lines = [
        f"検査日時 : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
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
