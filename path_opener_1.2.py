import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import os
import glob

# ── Color palette ─────────────────────────────────────────────────────────────
C_DONE    = "#22C55E"   # green  – completed
C_ACTIVE  = "#3B82F6"   # blue   – in progress
C_PENDING = "#9CA3AF"   # grey   – not started
C_PANEL   = "#F3F4F6"   # left panel background
C_WHITE   = "#FFFFFF"
C_TEXT    = "#1F2937"
C_MUTED   = "#6B7280"
C_BORDER  = "#E5E7EB"

# ── Application state ─────────────────────────────────────────────────────────
state = {
    # STEP 1
    'qr_read':    False,
    'inq_ok':     False,
    'content_ok': False,
    # STEP 2
    'ng_jpgs':    [],
    'ng_idx':     -1,
    'ng_done':    0,
    # STEP 3
    'all_jpgs':   [],
    'all_idx':    -1,
    'all_done':   0,
    # STEP 4
    'csv_ok':     False,
    'fiot_ok':    False,
    # current image mode
    'mode':       None,   # 'ng' or 'all'
}

w = {}  # widget reference store


# ── Step completion helpers ────────────────────────────────────────────────────
def step1_ok():
    return state['qr_read'] and state['inq_ok'] and state['content_ok']

def step2_ok():
    n = len(state['ng_jpgs'])
    return n > 0 and state['ng_done'] >= n

def step3_ok():
    n = len(state['all_jpgs'])
    return n > 0 and state['all_done'] >= n

def all_ok():
    return step1_ok() and step2_ok() and step3_ok()


# ── Panel refresh ─────────────────────────────────────────────────────────────
def refresh():
    # STEP 1
    w['qr_dot'].config(fg=C_DONE if state['qr_read']    else C_PENDING)
    w['inq_dot'].config(fg=C_DONE if state['inq_ok']    else C_PENDING)
    w['cont_dot'].config(fg=C_DONE if state['content_ok'] else C_PENDING)
    w['s1_title'].config(fg=C_DONE if step1_ok() else C_TEXT)

    # STEP 2
    ng_n = len(state['ng_jpgs'])
    ng_d = state['ng_done']
    w['ng_fetch_dot'].config(fg=C_DONE if ng_n > 0 else C_PENDING)
    if ng_n > 0:
        prog_col = C_DONE if ng_d >= ng_n else C_ACTIVE
        w['ng_prog_dot'].config(fg=prog_col)
        w['ng_prog_lbl'].config(text=f"{ng_d}/{ng_n}枚目完了")
    else:
        w['ng_prog_dot'].config(fg=C_PENDING)
        w['ng_prog_lbl'].config(text="―")
    w['s2_title'].config(fg=C_DONE if step2_ok() else C_TEXT)

    # STEP 3
    all_n = len(state['all_jpgs'])
    all_d = state['all_done']
    w['all_fetch_dot'].config(fg=C_DONE if all_n > 0 else C_PENDING)
    if all_n > 0:
        prog_col = C_DONE if all_d >= all_n else C_ACTIVE
        w['all_prog_dot'].config(fg=prog_col)
        w['all_prog_lbl'].config(text=f"{all_d}/{all_n}枚目完了")
    else:
        w['all_prog_dot'].config(fg=C_PENDING)
        w['all_prog_lbl'].config(text="―")
    w['s3_title'].config(fg=C_DONE if step3_ok() else C_TEXT)

    # STEP 4
    w['csv_dot'].config(fg=C_DONE if state['csv_ok']  else C_PENDING)
    w['fiot_dot'].config(fg=C_DONE if state['fiot_ok'] else C_PENDING)
    can_write = all_ok() and not state['csv_ok']
    w['write_btn'].config(
        state=tk.NORMAL if can_write else tk.DISABLED,
        bg=C_ACTIVE if can_write else C_BORDER,
        fg=C_WHITE  if can_write else C_MUTED,
    )
    w['s4_title'].config(fg=C_DONE if (state['csv_ok'] and state['fiot_ok']) else C_TEXT)

    # Navigation buttons
    mode = state['mode']
    if mode == 'ng' and ng_n > 0:
        idx = state['ng_idx']
        at_last = idx == ng_n - 1
        w['nav_prev'].config(state=tk.NORMAL if idx > 0   else tk.DISABLED)
        w['nav_next'].config(state=tk.NORMAL if not at_last else tk.DISABLED)
        w['nav_done'].config(state=tk.NORMAL if at_last and not step2_ok() else tk.DISABLED)
    elif mode == 'all' and all_n > 0:
        idx = state['all_idx']
        at_last = idx == all_n - 1
        w['nav_prev'].config(state=tk.NORMAL if idx > 0   else tk.DISABLED)
        w['nav_next'].config(state=tk.NORMAL if not at_last else tk.DISABLED)
        w['nav_done'].config(state=tk.NORMAL if at_last and not step3_ok() else tk.DISABLED)
    else:
        for k in ('nav_prev', 'nav_next', 'nav_done'):
            w[k].config(state=tk.DISABLED)


# ── Image display ─────────────────────────────────────────────────────────────
def show_current_image():
    mode = state['mode']
    if mode == 'ng':
        jpgs, idx = state['ng_jpgs'], state['ng_idx']
    elif mode == 'all':
        jpgs, idx = state['all_jpgs'], state['all_idx']
    else:
        return

    if idx < 0 or idx >= len(jpgs):
        return

    img = Image.open(jpgs[idx])
    img.thumbnail((500, 500))
    photo = ImageTk.PhotoImage(img)
    w['image_lbl'].config(image=photo)
    w['image_lbl'].image = photo
    w['filename_lbl'].config(text=f"[{idx + 1}/{len(jpgs)}]  {os.path.basename(jpgs[idx])}")
    refresh()


# ── Navigation callbacks ───────────────────────────────────────────────────────
def nav_prev():
    mode = state['mode']
    if mode == 'ng' and state['ng_idx'] > 0:
        state['ng_idx'] -= 1
    elif mode == 'all' and state['all_idx'] > 0:
        state['all_idx'] -= 1
    show_current_image()

def nav_next():
    mode = state['mode']
    if mode == 'ng':
        idx, n = state['ng_idx'], len(state['ng_jpgs'])
        if idx < n - 1:
            state['ng_idx'] = idx + 1
            state['ng_done'] = max(state['ng_done'], idx + 1)
    elif mode == 'all':
        idx, n = state['all_idx'], len(state['all_jpgs'])
        if idx < n - 1:
            state['all_idx'] = idx + 1
            state['all_done'] = max(state['all_done'], idx + 1)
    show_current_image()

def nav_confirm_done():
    mode = state['mode']
    if mode == 'ng':
        state['ng_done'] = len(state['ng_jpgs'])
    elif mode == 'all':
        state['all_done'] = len(state['all_jpgs'])
    refresh()


# ── Image load callbacks ──────────────────────────────────────────────────────
def load_images(target):
    path = w['entry'].get().strip()
    if not os.path.exists(path):
        messagebox.showerror("Error", f"フォルダが見つかりません:\n{path}")
        return
    jpgs = sorted(glob.glob(os.path.join(path, "*.jpg")))
    if not jpgs:
        messagebox.showinfo("Info", "JPGファイルが見つかりませんでした。")
        return
    if target == 'ng':
        state['ng_jpgs'] = jpgs
        state['ng_idx']  = 0
        state['ng_done'] = 0
    else:
        state['all_jpgs'] = jpgs
        state['all_idx']  = 0
        state['all_done'] = 0
    state['mode'] = target
    show_current_image()


# ── Write callback ────────────────────────────────────────────────────────────
def do_write():
    state['csv_ok'] = True
    refresh()
    root.after(800, _fiot_write)

def _fiot_write():
    state['fiot_ok'] = True
    refresh()


# ── UI builder helpers ────────────────────────────────────────────────────────
def add_step_header(parent, num, title, title_key):
    f = tk.Frame(parent, bg=C_PANEL)
    f.pack(fill=tk.X, padx=12, pady=(10, 2))
    tk.Label(f, text=f"STEP {num}", bg=C_PANEL, fg=C_ACTIVE,
             font=("Arial", 8, "bold")).pack(side=tk.LEFT, padx=(0, 6))
    lbl = tk.Label(f, text=title, bg=C_PANEL, fg=C_TEXT, font=("Arial", 10, "bold"))
    lbl.pack(side=tk.LEFT)
    w[title_key] = lbl

def add_indicator(parent, text, dot_key):
    f = tk.Frame(parent, bg=C_PANEL)
    f.pack(fill=tk.X, padx=(30, 8), pady=1)
    dot = tk.Label(f, text="●", bg=C_PANEL, fg=C_PENDING, font=("Arial", 9))
    dot.pack(side=tk.LEFT, padx=(0, 5))
    tk.Label(f, text=text, bg=C_PANEL, fg=C_TEXT, font=("Arial", 9),
             anchor="w").pack(side=tk.LEFT)
    w[dot_key] = dot

def add_progress_row(parent, dot_key, lbl_key):
    f = tk.Frame(parent, bg=C_PANEL)
    f.pack(fill=tk.X, padx=(30, 8), pady=1)
    dot = tk.Label(f, text="●", bg=C_PANEL, fg=C_PENDING, font=("Arial", 9))
    dot.pack(side=tk.LEFT, padx=(0, 5))
    lbl = tk.Label(f, text="―", bg=C_PANEL, fg=C_TEXT, font=("Arial", 9), anchor="w")
    lbl.pack(side=tk.LEFT)
    w[dot_key] = dot
    w[lbl_key]  = lbl

def add_separator(parent):
    tk.Frame(parent, bg=C_BORDER, height=1).pack(fill=tk.X, padx=8, pady=5)


# ── Left panel ────────────────────────────────────────────────────────────────
def build_left_panel(parent):
    panel = tk.Frame(parent, bg=C_PANEL, width=260)
    panel.pack(side=tk.LEFT, fill=tk.Y)
    panel.pack_propagate(False)

    tk.Label(panel, text="工程進捗", bg=C_PANEL, fg=C_TEXT,
             font=("Arial", 11, "bold")).pack(pady=(12, 4))
    add_separator(panel)

    # STEP 1
    add_step_header(panel, 1, "ケースQR読取", 's1_title')
    add_indicator(panel, "読取OK",               'qr_dot')
    add_indicator(panel, "流動情報への問い合わせOK", 'inq_dot')
    add_indicator(panel, "流動情報の内容OK",       'cont_dot')
    add_separator(panel)

    # STEP 2
    add_step_header(panel, 2, "NG画像確認", 's2_title')
    add_indicator(panel,    "NG画像の取得OK", 'ng_fetch_dot')
    add_progress_row(panel, 'ng_prog_dot', 'ng_prog_lbl')
    add_separator(panel)

    # STEP 3
    add_step_header(panel, 3, "全画像確認", 's3_title')
    add_indicator(panel,    "全画像の取得OK", 'all_fetch_dot')
    add_progress_row(panel, 'all_prog_dot', 'all_prog_lbl')
    add_separator(panel)

    # STEP 4
    add_step_header(panel, 4, "結果出力", 's4_title')
    btn_f = tk.Frame(panel, bg=C_PANEL)
    btn_f.pack(fill=tk.X, padx=(30, 8), pady=4)
    btn = tk.Button(btn_f, text="書き込み実施", command=do_write,
                    state=tk.DISABLED, bg=C_BORDER, fg=C_MUTED,
                    font=("Arial", 9, "bold"), relief=tk.FLAT,
                    padx=10, pady=4)
    btn.pack(side=tk.LEFT)
    w['write_btn'] = btn
    add_indicator(panel, "CSV記録書き込みOK", 'csv_dot')
    add_indicator(panel, "F-IoT書き込みOK",  'fiot_dot')


# ── Right panel ───────────────────────────────────────────────────────────────
def build_right_panel(parent):
    panel = tk.Frame(parent, bg=C_WHITE)
    panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Path input row
    top = tk.Frame(panel, bg=C_WHITE, padx=10, pady=10)
    top.pack(fill=tk.X)
    tk.Label(top, text="フォルダパス:", bg=C_WHITE, fg=C_TEXT,
             font=("Arial", 9)).pack(side=tk.LEFT)
    entry = tk.Entry(top, width=36, font=("Arial", 10))
    entry.pack(side=tk.LEFT, padx=(4, 8))
    entry.focus()
    w['entry'] = entry

    tk.Button(top, text="NG画像読込", command=lambda: load_images('ng'),
              bg="#FEF3C7", fg="#92400E",
              font=("Arial", 9, "bold"), relief=tk.FLAT,
              padx=8, pady=3).pack(side=tk.LEFT, padx=(0, 4))
    tk.Button(top, text="全画像読込", command=lambda: load_images('all'),
              bg="#DBEAFE", fg="#1E40AF",
              font=("Arial", 9, "bold"), relief=tk.FLAT,
              padx=8, pady=3).pack(side=tk.LEFT)

    # Filename / counter label
    filename_lbl = tk.Label(panel, text="", bg=C_WHITE, fg=C_MUTED,
                             font=("Arial", 9))
    filename_lbl.pack()
    w['filename_lbl'] = filename_lbl

    # Image display
    image_lbl = tk.Label(panel, bg=C_WHITE)
    image_lbl.pack(pady=4)
    w['image_lbl'] = image_lbl

    # Navigation row
    nav = tk.Frame(panel, bg=C_WHITE, pady=6)
    nav.pack()

    prev_btn = tk.Button(nav, text="◀ 前へ", command=nav_prev,
                         state=tk.DISABLED, width=8,
                         font=("Arial", 10), relief=tk.FLAT,
                         bg=C_BORDER, fg=C_TEXT)
    prev_btn.pack(side=tk.LEFT, padx=6)

    next_btn = tk.Button(nav, text="次へ ▶", command=nav_next,
                         state=tk.DISABLED, width=8,
                         font=("Arial", 10), relief=tk.FLAT,
                         bg=C_BORDER, fg=C_TEXT)
    next_btn.pack(side=tk.LEFT, padx=6)

    done_btn = tk.Button(nav, text="✓ 確認完了", command=nav_confirm_done,
                         state=tk.DISABLED, width=10,
                         font=("Arial", 10, "bold"), relief=tk.FLAT,
                         bg=C_DONE, fg=C_WHITE)
    done_btn.pack(side=tk.LEFT, padx=6)

    w['nav_prev'] = prev_btn
    w['nav_next'] = next_btn
    w['nav_done'] = done_btn


# ── Main ──────────────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("defectRecordChecker")
root.geometry("1000x700")
root.configure(bg=C_WHITE)

main = tk.Frame(root, bg=C_WHITE)
main.pack(fill=tk.BOTH, expand=True)

build_left_panel(main)
tk.Frame(main, bg=C_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)  # divider
build_right_panel(main)

refresh()
root.mainloop()
