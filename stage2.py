import os
import re
import shlex
import sys
import argparse
import time
import tkinter as tk
from tkinter import scrolledtext

# --- utils -------------------------------------------------------
def now_ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")

LOGFILE = "emulator.log"
def log(msg):
    line = f"{now_ts()}  {msg}\n"
    try:
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        # не критично для GUI — просто игнорируем ошибку логирования
        pass

# На Windows: если нет HOME, поставить USERPROFILE как HOME, чтобы $HOME работал
if os.name == 'nt' and 'HOME' not in os.environ and 'USERPROFILE' in os.environ:
    os.environ['HOME'] = os.environ['USERPROFILE']

VFS_NAME = os.environ.get("VFS_NAME", "VFS-default")
PROMPT = f"{VFS_NAME}$ "

def expand_arg(arg):
    """Развёртка ~/ и ${VAR} / $VAR — оставляем незаполненные переменные как есть."""
    arg = os.path.expanduser(arg)
    pattern = re.compile(r'\${([^}]+)}|\$([A-Za-z0-9_]+)')
    def repl(m):
        name = m.group(1) or m.group(2)
        val = os.environ.get(name)
        if val is None:
            return m.group(0)  # оставляем как есть
        return val
    return pattern.sub(repl, arg)

# --- GUI + REPL -------------------------------------------------
class EmulatorGUI:
    def __init__(self, master, vfs_path=None, start_script=None):
        self.master = master
        master.title(f"Эмулятор оболочки — {VFS_NAME}")

        self.vfs_path = vfs_path
        self.start_script = start_script

        # Output area
        self.output = scrolledtext.ScrolledText(master, wrap=tk.WORD, height=20, state='disabled')
        self.output.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # Input frame
        frame = tk.Frame(master)
        frame.pack(fill=tk.X, padx=8, pady=(0,8))

        self.prompt_label = tk.Label(frame, text=PROMPT, anchor='w')
        self.prompt_label.pack(side=tk.LEFT)

        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(frame, textvariable=self.input_var)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_entry.bind("<Return>", self.on_enter)
        self.input_entry.focus()

        # Menu
        menubar = tk.Menu(master)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Exit", command=self.do_exit)
        menubar.add_cascade(label="File", menu=filemenu)
        master.config(menu=menubar)

        # initial messages
        self.println(f"Запуск эмулятора. VFS_NAME: {VFS_NAME}")
        self.println(f"Отладка: vfs_path={self.vfs_path!r}; start_script={self.start_script!r}")
        self.println("Поддерживаемые команды (стаб): ls, cd, exit, echo")
        self.println("Стартовый скрипт: комментарии начинаются с '#'")
        self.println("-" * 60)

        log(f"Started emulator (VFS_NAME={VFS_NAME}, vfs_path={self.vfs_path}, start_script={self.start_script})")

        # Если указан стартовый скрипт — запустим его после маленькой задержки (чтобы GUI успел отрисоваться)
        if self.start_script:
            self.master.after(150, lambda: self.run_start_script(self.start_script))

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
        # show input and execute
        self.println(f">>> {line}")
        log(f"Interactive input: {line}")
        try:
            self.execute_line(line)
        except Exception as e:
            self.println(f"Ошибка выполнения: {e}")
            log(f"Error executing interactive line: {e}")
        finally:
            self.input_var.set("")

    def execute_line(self, line):
        """Парсит и выполняет одну строку команды. Возвращает True при успехе, False при ошибке (не фатальной)."""
        try:
            parts = shlex.split(line)
        except ValueError as e:
            self.println(f"Ошибка разбора команды: {e}")
            log(f"Parse error: {e}  line={line}")
            return False

        if not parts:
            return True

        cmd = parts[0]
        raw_args = parts[1:]
        args = [expand_arg(a) for a in raw_args]

        # detect unresolved vars (informational)
        for raw, exp in zip(raw_args, args):
            if re.search(r'\${[^}]+}|\$[A-Za-z0-9_]+', exp):
                self.println(f"Предупреждение: переменная в аргументе {raw!r} не найдена и оставлена как {exp!r}")

        # dispatch supported stub commands
        if cmd == "exit":
            if args:
                self.println("Ошибка: exit не принимает аргументов.")
                return False
            self.println("Выход из эмулятора...")
            log("Exit command received (script/interactive).")
            # закрываем через небольшую задержку, чтобы сообщение успело показаться
            self.master.after(200, self.do_exit)
            return True

        if cmd == "ls":
            if len(args) > 1:
                self.println("Ошибка: ls принимает не более одного аргумента.")
                log(f"ls: bad args {args}")
                return False
            self.println(f"ls called. args: {args}")
            if len(args) == 0:
                self.println("file1.txt  dir1/  README.md")
            else:
                self.println(f"Listing for {args[0]} (stub):")
                self.println("fileA  fileB  subdir/")
            return True

        if cmd == "cd":
            if len(args) != 1:
                self.println("Ошибка: cd требует ровно один аргумент (путь).")
                log(f"cd: bad args {args}")
                return False
            self.println(f"cd called. args: {args}")
            # stage2: не меняем реальный cwd
            return True

        if cmd == "echo":
            # echo — просто печатаем аргументы через пробел
            self.println(" ".join(args))
            return True

        # unknown command
        self.println(f"Неизвестная команда: {cmd}")
        log(f"Unknown command: {cmd}  args={args}")
        return False

    def run_start_script(self, path):
        self.println(f"Выполнение стартового скрипта: {path}")
        log(f"Running start script: {path}")
        if not os.path.exists(path):
            self.println(f"Ошибка: стартовый скрипт не найден: {path}")
            log(f"Start script not found: {path}")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            self.println(f"Ошибка чтения стартового скрипта: {e}")
            log(f"Error reading start script: {e}")
            return

        for idx, raw in enumerate(lines, start=1):
            line = raw.rstrip("\n")
            # show comments and blank lines but do not execute comments
            if line.strip() == "":
                # show blank line (optional)
                self.println("") 
                continue
            if line.lstrip().startswith("#"):
                # comment: show as a comment
                self.println(line)
                continue

            # it's a command line: show it and execute
            self.println(f">>> {line}")
            log(f"Script line {idx}: {line}")
            try:
                ok = self.execute_line(line)
                if not ok:
                    self.println(f"Ошибка в строке {idx}: {line}")
                    log(f"Error executing script line {idx}: {line}")
                # продолжаем выполнение следующих строк
            except Exception as e:
                self.println(f"Исключение при выполнении строки {idx}: {e}")
                log(f"Exception executing script line {idx}: {e}")
                # не прерываем выполнение скрипта
        self.println(f"Выполнение стартового скрипта завершено.")
        log(f"Finished start script: {path}")

    def do_exit(self):
        self.master.quit()
        self.master.destroy()

def parse_args(argv):
    p = argparse.ArgumentParser(description="Эмулятор оболочки — этап 2")
    p.add_argument("--vfs-path", dest="vfs_path", help="Путь к директории-источнику VFS", default=None)
    p.add_argument("--start-script", dest="start_script", help="Путь к стартовому скрипту", default=None)
    return p.parse_args(argv)

def main(argv):
    args = parse_args(argv)
    root = tk.Tk()
    app = EmulatorGUI(root, vfs_path=args.vfs_path, start_script=args.start_script)
    root.mainloop()

if __name__ == "__main__":
    main(sys.argv[1:])
