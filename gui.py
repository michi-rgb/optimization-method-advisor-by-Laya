"""Tk GUI; inference in a worker, all Tk operations on the main thread."""
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from advisor import Advisor, EXAMPLES, render


def run():
    root = tk.Tk()
    root.title("製造業 手法アドバイザー | Laya")
    root.geometry("860x860")
    root.minsize(720, 700)
    root.option_add("*Font", "{Yu Gothic UI} 10")
    frame = ttk.Frame(root, padding=22)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="やりたいことから、最初に使う手法を選ぶ", font=("Yu Gothic UI", 18, "bold")).pack(anchor="w")
    ttk.Label(frame, text="要因効果分析 ／ 応答曲面法 ／ 逐次最適化 ／ オンライン学習").pack(anchor="w", pady=(6, 16))
    ttk.Label(frame, text="製品・工程、改善したいこと、試験の制約を自由に入力してください（補足を含め1600文字まで）").pack(anchor="w")
    entry = ScrolledText(frame, height=6, wrap="word")
    entry.pack(fill="x", pady=8)
    example = ttk.Combobox(frame, values=EXAMPLES, state="readonly", width=75)
    example.set("入力例を選ぶ")
    example.pack(fill="x")

    def fill_example(_):
        entry.delete("1.0", "end")
        entry.insert("1.0", example.get())

    example.bind("<<ComboboxSelected>>", fill_example)
    ttk.Label(frame, text="任意の補足：試験の費用・時間、連続値か材料種か、既存データ、継続更新の必要性など").pack(anchor="w", pady=(12, 4))
    context = ttk.Entry(frame)
    context.pack(fill="x")
    toolbar = ttk.Frame(frame)
    toolbar.pack(fill="x", pady=12)
    status = tk.StringVar(value="準備できました。モデルの初回読込には時間がかかります。")
    ttk.Label(frame, textvariable=status).pack(anchor="w")
    output = ScrolledText(frame, height=18, wrap="word", state="disabled")
    output.pack(fill="both", expand=True, pady=(8, 0))
    advisor = Advisor()
    events = queue.Queue()
    current = [None]

    def work(text, extra):
        try:
            events.put((True, advisor.recommend(text, extra)))
        except Exception as exc:
            events.put((False, str(exc)))

    def start():
        text = entry.get("1.0", "end").strip()
        extra = context.get().strip()
        if not text or len(text) + len(extra) > 1600:
            messagebox.showinfo("入力の確認", "やりたいことを入力し、補足を含め1600文字以内にしてください。")
            return
        button.config(state="disabled")
        save.config(state="disabled")
        current[0] = None
        output.config(state="normal")
        output.delete("1.0", "end")
        output.config(state="disabled")
        status.set("Layaで判定しています…（このPC内で処理）")
        threading.Thread(target=work, args=(text, extra), daemon=True).start()

    def poll():
        try:
            ok, value = events.get_nowait()
        except queue.Empty:
            root.after(150, poll)
            return
        button.config(state="normal")
        if ok:
            current[0] = value
            output.config(state="normal")
            output.delete("1.0", "end")
            output.insert("1.0", render(value))
            output.config(state="disabled")
            save.config(state="normal")
            status.set("判定が完了しました。条件を補足して再判定できます。")
        else:
            status.set("判定できませんでした。")
            messagebox.showerror("実行エラー", value)
        root.after(150, poll)

    def export():
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("判定結果 JSON", "*.json")])
        if path and current[0]:
            try:
                with open(path, "w", encoding="utf-8") as stream:
                    json.dump(current[0], stream, ensure_ascii=False, indent=2)
            except OSError as exc:
                messagebox.showerror("保存エラー", str(exc))

    button = ttk.Button(toolbar, text="おすすめを判定", command=start)
    button.pack(side="left")
    save = ttk.Button(toolbar, text="結果をJSONで保存", command=export, state="disabled")
    save.pack(side="left", padx=10)
    root.after(150, poll)
    root.mainloop()


if __name__ == "__main__":
    run()
