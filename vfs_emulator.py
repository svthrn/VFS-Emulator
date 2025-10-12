#!/usr/bin/env python3
"""
emulator_gui.py  — GUI REPL (исправленная развёртка переменных окружения)

Запуск:
    python3 emulator_gui.py

Изменения по сравнению с предыдущей версией:
- Надёжная развёртка переменных окружения ($VAR и ${VAR}) с fallback'ом для Windows.
- Поддержка ~ (os.path.expanduser).
- Если переменная не найдена — оставляем её как есть и выводим предупреждение.
"""
import os
import re
import shlex
import sys
import tkinter as tk
from tkinter import scrolledtext, messagebox

# На Windows часто нет HOME, но есть USERPROFILE — сделаем fallback, чтобы $HOME работал.
if os.name == 'nt' and 'HOME' not in os.environ and 'USERPROFILE' in os.environ:
    os.environ['HOME'] = os.environ['USERPROFILE']

VFS_NAME = os.environ.get("VFS_NAME", "VFS-default")
PROMPT = f"{VFS_NAME}$ "

def expand_arg(arg):
    """
    Надёжно разворачивает:
      - ~/user -> полный путь (expanduser)
      - ${VAR} и $VAR -> значение из os.environ (если найдено)
    Если переменная окружения не найдена, оставляем конструкцию без изменений.
    """
    # сначала expanduser для ~
    arg = os.path.expanduser(arg)

    # функция-заместитель для ${VAR} или $VAR
    pattern = re.compile(r'\${([^}]+)}|\$([A-Za-z0-9_]+)')
    def repl(m):
        name = m.group(1) or m.group(2)
        val = os.environ.get(name)
        if val is None:
            # не нашли — возвращаем оригинальную подстроку ($VAR / ${VAR})
            return m.group(0)
        return val

    result = pattern.sub(repl, arg)
    return result

class EmulatorGUI:
    def __init__(self, master):
        self.master = master
        master.title(f"Эмулятор оболочки — {VFS_NAME}")

        self.output = scrolledtext.ScrolledText(master, wrap=tk.WORD, height=20, state='disabled')
        self.output.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        frame = tk.Frame(master)
        frame.pack(fill=tk.X, padx=8, pady=(0,8))

        self.prompt_label = tk.Label(frame, text=PROMPT, anchor='w')
        self.prompt_label.pack(side=tk.LEFT)

        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(frame, textvariable=self.input_var)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_entry.bind("<Return>", self.on_enter)
        self.input_entry.focus()

        menubar = tk.Menu(master)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Exit", command=self.do_exit)
        menubar.add_cascade(label="File", menu=filemenu)
        master.config(menu=menubar)

        self.println(f"Запуск эмулятора. Заголовок содержит имя VFS: {VFS_NAME}")
        self.println("Поддерживаемые команды: ls, cd, exit")
        self.println("Пример: ls $HOME")
        self.println("-" * 40)

    def println(self, text=""):
        self.output.config(state='normal')
        self.output.insert(tk.END, text + "\n")
        self.output.see(tk.END)
        self.output.config(state='disabled')

    def on_enter(self, event):
        line = self.input_var.get().strip()
        if not line:
            self.input_var.set("")
            return
        # show input
        self.println(f">>> {line}")
        try:
            self.execute_line(line)
        except Exception as e:
            self.println(f"Ошибка выполнения: {e}")
        finally:
            self.input_var.set("")

    def execute_line(self, line):
        try:
            parts = shlex.split(line)
        except ValueError as e:
            self.println(f"Ошибка разбора команды: {e}")
            return

        if not parts:
            return

        cmd = parts[0]
        raw_args = parts[1:]

        # Expand environment variables using our robust function.
        args = [expand_arg(a) for a in raw_args]

        # detect any still-unexpanded variables and warn (optional)
        unresolved = []
        for raw, expanded in zip(raw_args, args):
            if re.search(r'\${[^}]+}|\$[A-Za-z0-9_]+', expanded):
                # если после замены в expanded осталась конструкция $VAR, то переменная не найдена
                unresolved.append((raw, expanded))

        if unresolved:
            for raw, exp in unresolved:
                self.println(f"Предупреждение: переменная в аргументе {raw!r} не найдена и оставлена как {exp!r}")

        # Dispatch commands
        if cmd == "exit":
            if args:
                self.println("Ошибка: exit не принимает аргументов.")
                return
            self.println("Выход из эмулятора...")
            self.master.after(200, self.do_exit)
        elif cmd == "ls":
            if len(args) > 1:
                self.println("Ошибка: ls принимает не более одного аргумента.")
                return
            self.println(f"ls called. args: {args}")
            if len(args) == 0:
                self.println("file1.txt  dir1/  README.md")
            else:
                self.println(f"Listing for {args[0]} (stub):")
                self.println("fileA  fileB  subdir/")
        elif cmd == "cd":
            if len(args) != 1:
                self.println("Ошибка: cd требует ровно один аргумент (путь).")
                return
            self.println(f"cd called. args: {args}")
            # stage1 не меняем реальный cwd
        else:
            self.println(f"Неизвестная команда: {cmd}")

    def do_exit(self):
        self.master.quit()
        self.master.destroy()

def main():
    root = tk.Tk()
    app = EmulatorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
