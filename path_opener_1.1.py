import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import os
import glob

def open_path():
    path = entry.get().strip()
    if not os.path.exists(path):
        messagebox.showerror("Error", f"No such folder:\n{path}")
        return

    jpgs = sorted(glob.glob(os.path.join(path, "*.jpg")))
    if not jpgs:
        messagebox.showinfo("Info", "No JPG files found in this folder.")
        return

    img = Image.open(jpgs[0])
    img.thumbnail((760, 600))
    photo = ImageTk.PhotoImage(img)
    image_label.config(image=photo)
    image_label.image = photo  # keep reference
    filename_label.config(text=os.path.basename(jpgs[0]))

root = tk.Tk()
root.title("Path Opener")
root.geometry("800x750")

top = tk.Frame(root, padx=10, pady=10)
top.pack()

entry = tk.Entry(top, width=60)
entry.pack(side=tk.LEFT, padx=(0, 8))
entry.focus()

tk.Button(top, text="Open", width=8, command=open_path).pack(side=tk.LEFT)
root.bind("<Return>", lambda e: open_path())

filename_label = tk.Label(root, text="", fg="gray")
filename_label.pack()

image_label = tk.Label(root)
image_label.pack(pady=5)

root.mainloop()
