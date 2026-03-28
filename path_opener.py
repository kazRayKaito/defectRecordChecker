import tkinter as tk
from tkinter import messagebox
import os

def open_path():
    path = entry.get().strip()
    if os.path.exists(path):
        os.startfile(path)
    else:
        messagebox.showerror("Error", f"No such path:\n{path}")

root = tk.Tk()
root.title("Path Opener")
root.geometry("400x100")

frame = tk.Frame(root, padx=10, pady=10)
frame.pack()

entry = tk.Entry(frame, width=45)
entry.pack(side=tk.LEFT, padx=(0, 8))
entry.focus()

tk.Button(frame, text="Open", width=8, command=open_path).pack(side=tk.LEFT)
root.bind("<Return>", lambda e: open_path())

root.mainloop()
