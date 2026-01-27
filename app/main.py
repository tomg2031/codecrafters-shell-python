import contextlib
import io
import shlex
import shutil
import subprocess
import sys
from functools import partial
from io import TextIOWrapper
from pathlib import Path
import os
from subprocess import Popen
from typing import TextIO

import readline

BUILTINS = {
    "exit": lambda code=0, *_: exit(int(code)),
    "echo": lambda *args: print(" ".join(args)),
    "type": lambda cmd, *_: type_command(cmd),
    "pwd": lambda *_: print(Path.cwd()),
    "cd": lambda directory, *_: cd(directory)
}

def type_command(cmd):
    if cmd in BUILTINS:
        print(f"{cmd} is a shell builtin")
    elif path := shutil.which(cmd):
        print(f"{cmd} is {path}")
    else:
        print(f"{cmd}: not found", file=sys.stderr)

def cd(directory):
    directory = directory.replace("~", str(Path.home()))

    try:
        os.chdir(directory)
    except FileNotFoundError:
        print(f"cd: {directory}: No such file or directory", file=sys.stderr)

def handle_command(cmd, stdout=sys.stdout, stdin=sys.stdin) -> Popen[str] | None:
    if not cmd:
        return
    args = cmd[1:]
    if cmd[0] in BUILTINS:
        BUILTINS[cmd[0]](*args)
    elif path := shutil.which(cmd[0]):
        p = subprocess.run(cmd, stdout=stdout, stderr=sys.stderr)
        return p
    else:
        print(f"{cmd[0]}: command not found", file=sys.stderr)

    return None

def parse_command(unparsed_command):
    commands = unparsed_command.split("|")
    tokens = []
    for i in commands:
        tokens.append(shlex.split(i, posix=True))

    return tokens

class BuiltInCompleter:
    def __init__(self, builtins, executables):
        self.completions = sorted(list(set(builtins + executables)))
        self.last_tab_text = ""
        self.matches = []
        self.last_tab_count = 0

    def complete(self, text: str, state: int) -> str | None:
        line = readline.get_line_buffer()

        if line.strip() and " " in line.lstrip():
            # If there is a space, we are not completing the command except for trailing spaces
            return None

        if text != self.last_tab_text and state == 0:
            # Text changed, reset matches
            # print(f"resetting matches '{text}':'{self.last_tab_text}'")
            self.last_tab_text = text
            self.matches = [cmd + " " for cmd in self.completions if cmd.startswith(text)]
            self.last_tab_count = 0

        if len(self.matches) == 1:
            # If there is only one match, return it
            if state == 0:
                return self.matches[0]
            return None
        elif len(self.matches) == 0:
            # If there are no matches, beep and return None
            print("\a", end="", flush=True)  # Beep sound for no match
            return None
        elif self.last_tab_count == 0:
            # If this is the first tab press (and there are multiple matches), beep
            self.last_tab_count += 1
            print("\a", end="", flush=True)  # Beep sound for multiple matches

            if state == 0:
                partial_completion = text
                index = len(partial_completion)

                for idx, char in enumerate(min(self.matches, key=len)[index:]):
                    if all(m[idx + index] == char for m in self.matches):
                        partial_completion += char
                    else:
                        break

                if partial_completion != text:
                    self.last_tab_text = partial_completion
                    return partial_completion

            return None
        elif state == 0 and self.last_tab_count == 1:
            # If this is the second tab press, print all matches
            print()
            print(" ".join(self.matches))
            print(f"$ {text}", end="", flush=True)
            self.last_tab_count += 1
            return text
        else:
            # If this is a subsequent tab press and nothing changed, don't complete it again
            return None

def hande_redirects(command):
    redirect_out = None
    redirect_err = None
    if ">" in command or "1>" in command:
        output_file = command[-1]
        redirect_out = open(output_file, "w")
    elif "2>" in command:
        error_file = command[-1]
        redirect_err = open(error_file, "w")
    elif ">>" in command or "1>>" in command:
        output_file = command[-1]
        redirect_out = open(output_file, "a")
    elif "2>>" in command:
        error_file = command[-1]
        redirect_err = open(error_file, "a")

    return redirect_out, redirect_err

def handle_pipeline(commands_list):
    processes = []
    prev_pipe = None
    orig_stdout = sys.stdout

    for i, cmd in enumerate(commands_list):
        cmd_parts = shlex.split(cmd)
        if not cmd_parts:
            continue

        if i == len(commands_list) - 1:
            pipe_w = None
            sys.stdout = orig_stdout
        else:
            pipe_r, pipe_w = os.pipe()
            sys.stdout = os.fdopen(pipe_w, "w")

        if cmd_parts[0] in BUILTINS:
            # Handle built-in commands
            BUILTINS[cmd_parts[0]](*cmd_parts[1:])
        elif shutil.which(cmd_parts[0]):
            process = subprocess.Popen(cmd_parts, stdin=prev_pipe, stdout=sys.stdout, stderr=sys.stderr)
            processes.append(process)
        else:
            print(f"{cmd_parts[0]}: command not found", file=sys.stderr)

        if prev_pipe is not None:
            os.close(prev_pipe)
        if i != len(commands_list) - 1:
            sys.stdout.close()  # This closes pipe_w

        prev_pipe = pipe_r
    for process in processes:
        process.wait()


def dispatch_command(command):
    cmd = parse_command(command)

    out, err = hande_redirects(cmd[-1])
    orig_out, orig_err = sys.stdout, sys.stderr
    if out:
        sys.stdout = out
        cmd[-1] = cmd[-1][:-2]
    elif err:
        sys.stderr = err
        cmd[-1] = cmd[-1][:-2]

    if len(cmd) == 1:
        handle_command(cmd[0], stdout=out, stdin=sys.stdin)
    else:
        handle_pipeline(command.split("|"))

    if out:
        sys.stdout.close()
    elif err:
        sys.stderr.close()
    sys.stdout, sys.stderr = orig_out, orig_err


def main():
    path = os.getenv("PATH").split(":")
    executables = []
    for directory in path:
        if not os.path.isdir(directory):
            continue
        executables.extend([file for file in os.listdir(directory)])

    readline.set_completer(BuiltInCompleter(list(BUILTINS.keys()), executables).complete)
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims("  ")

    sys.stderr = sys.stdout
    while True:
        command = input("$ ")
        dispatch_command(command)


if __name__ == "__main__":
    main()