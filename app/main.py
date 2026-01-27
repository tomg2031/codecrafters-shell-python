import os
import sys
import subprocess
import copy
import readline
from contextlib import redirect_stdout

from typing import Callable, Any


class Shell:
    _builtins: dict[str, Callable] = {}
    _executables: dict[str, str] = {}
    _path: list[str] = []

    def __init__(self):
        self.getExecutables()
        self._path = os.getcwd().split(os.sep)

    def register(self, name: str, fn: Callable):
        self._builtins[name.lower()] = fn

    def _execute_inner(self, command: str, args: list[str],outfile=None,errfile=None) -> Any:
        try:
            if command in self._builtins:
                if outfile is not None:
                    with redirect_stdout(outfile):
                        self._builtins[command](args)
                else:
                    self._builtins[command](args)

            elif command in self._executables:
                self._builtins["executable"](command, args,outfile,errfile)

            else:
                print(f"{command}: command not found", file=sys.stderr)

        except Exception as e:
                print(e,file=sys.stderr)


    def execute(self, command: str, args: list[str]) -> Any:
        # Prioritize builtins over executables
        outfile = None
        errfile = None
        appendFile = False

        REDIRECTS = {">", ">>", "1>", "1>>", "2>", "2>>"}

        for arg in args:
           if arg in REDIRECTS:
            if ">" in args:
                i = args.index(">")
                outfile = args[i + 1]
            elif "1>" in args:
                i = args.index("1>")
                outfile = args[i + 1]
            elif ">>" in args:
                i = args.index(">>")
                outfile = args[i + 1]    
                appendFile = True
            elif "1>>" in args:
                i = args.index("1>>")
                outfile = args[i + 1]
                appendFile = True
            elif "2>>" in args:
                i = args.index("2>>")
                errfile = args[i+1]
                appendFile = True
            else:
                i = args.index("2>")
                errfile = args[i + 1]
            args = args[:i]  

        if outfile is not None:
            os.makedirs(os.path.dirname(outfile) or ".", exist_ok=True)

            if appendFile:
                outfile = open(outfile, "a")   
            else:
                outfile = open(outfile, "w")   


        if errfile is not None:
            os.makedirs(os.path.dirname(errfile) or ".", exist_ok=True)
            
            if appendFile:
                errfile = open(errfile, "a")   
            else:
                errfile = open(errfile, "w")

        self._execute_inner(command, args,outfile,errfile)



    def getExecutables(self):
        directories: list[str] = os.environ["PATH"].split(os.pathsep)
        for directory in directories:
            if not os.path.exists(directory):
                continue
            for file in os.scandir(directory):
                if (
                    file.is_file()
                    and os.access(directory + os.sep + file.name, os.X_OK)
                    and file.name not in self._executables
                ):
                    self._executables[file.name] = directory + os.sep + file.name
    
    last_text = ""
    count = 0

    def split_pipeline(self,tokens):
        pipe_index = tokens.index("|")
        return tokens[:pipe_index], tokens[pipe_index+1:]

    def execute_pipeline(self,tokens):
        left, right =  self.split_pipeline(tokens)

        r, w = os.pipe()
        pid1 = os.fork()

        if pid1 == 0:
            os.dup2(w,1)
            os.close(r)
            os.close(w)

            if left[0] in self._builtins:
                self._builtins[left[0]](left[1:])
                sys.exit(0)
            else:
                os.execvp(left[0],left)
            sys.exit(1)

        pid2 = os.fork()
        if pid2 ==0:
            os.dup2(r,0)
            os.close(w)
            os.close(r)

            if right[0] in self._builtins:
                self._builtins[right[0]](right[1:])
                sys.exit(0)
            else:
                os.execvp(right[0],right)
            sys.exit(1)

        os.close(r)
        os.close(w)

        os.waitpid(pid1,0)
        os.waitpid(pid2,0)

    def completer(self, text, state):

        commands = sorted(
            set(self._builtins.keys()) | set(self._executables.keys())
        )

        matches = [cmd for cmd in commands if cmd.startswith(text)]
        
        # FIX 1: Use self.last_text and self.count
        if self.last_text != text:
            self.count = 0 
            self.last_text = text

        if state == 0 and len(matches) > 1 :
            # FIX 2: Use self.count
            if self.count == 0:
                if all(match.startswith(matches[0]) for match in matches[1:]):
                    return matches[0]
                
                sys.stdout.write("\a")
                self.count += 1  # FIX 3: Increment self.count
                return None
            else:
                print("\n" + "  ".join(matches))   
                sys.stdout.write("$ {}".format(text))
                sys.stdout.flush()
                return text
            
        if state < len(matches):
            return matches[state] + " "
        sys.stdout.write("\a")
        return None


SHELL: Shell = Shell()
readline.set_completer(SHELL.completer)
readline.parse_and_bind("tab: complete")
PLATFORM: str = ""
if sys.platform.startswith("win"):
    PLATFORM = "win"
elif sys.platform.startswith("linux"):
    PLATFORM = "lin"
else:
    PLATFORM = "mac"


def parse_command(command: str) -> list[str]:
    escaped = False
    quoted = False
    single_escape = False
    current = []
    parts = []
    for c in command:
        if single_escape:
            if quoted and (c != "\\" and c != '"'):
                current.append("\\")
            current.append(c)
            single_escape = False
        elif c == "\\" and not escaped:
            single_escape = True
        elif c == "'" and not quoted:
            escaped = not escaped
        elif c == '"' and not escaped:
            quoted = not quoted
        elif c == " " and not (escaped or quoted):
            if len(current) > 0:
                parts.append("".join(current))
                current = []
        else:
            current.append(c)
    if len(current) > 0:
        parts.append("".join(current))
    return parts


def command(name: str) -> Callable:
    global SHELL

    def wrapper(fn: Callable) -> Callable:
        SHELL.register(name, fn)
        return fn

    return wrapper

def execute(cmd: str) -> Any:
    global SHELL
    cmds: list[str] = parse_command(cmd)
    if not cmds: # Added safety check for empty input
        return
    if "|" in cmds:
         SHELL.execute_pipeline(cmds)
    else:
         SHELL.execute(cmds[0],cmds[1:])

@command("exit")
def _exit(args: list[str]) -> None:
    if not args:
        exit(0)
    exit(int(args[0]))


@command("echo")
def _echo(args: list[str]) -> None:
    print(" ".join(args))


@command("type")
def _type(args: list[str]) -> None:
    if args[0] in SHELL._builtins:
        print(f"{args[0]} is a shell builtin")
    elif args[0] in SHELL._executables:
        print(f"{args[0]} is {SHELL._executables[args[0]]}")
    else:
        print(f"{args[0]}: not found")


@command("executable")
def _executable(cmd: str, args: list[str],outfile=None,errfile=None) -> None:
        
        subprocess.run(
                [cmd, *args],
                stdout=outfile,
                stderr=errfile,
                check=False
            )

@command("pwd")
def _pwd(args: list[str]) -> None:
    print(os.sep.join(SHELL._path))


@command("cd")
def _cd(args: list[str]) -> None:
    cmds: list[str] = args[0].split(os.sep)
    temp: list[str] = copy.deepcopy(SHELL._path)
    if PLATFORM == "win" and cmds[0].endswith(":"):
        temp = []
    elif not cmds[0]:
        temp = [""]

    for dir in cmds:
        if not dir:
            continue
        elif dir == ".":
            continue
        elif dir == "..":
            if len(temp) <= 1:
                print(f"cd: {args[0]}: No such file or directory")
                return
            temp.pop()
        elif dir == "~":
            temp = os.getenv("HOME").split(os.sep)
        else:
            temp.append(dir)
            if not os.path.isdir(os.sep.join(temp)):
                print(f"cd: {args[0]}: No such file or directory")
                return
    SHELL._path = temp


def main():
    while True:
        try:
            execute(input("$ "))
        except EOFError: # Handles Ctrl+D gracefully
            print()
            break
        except KeyboardInterrupt: # Handles Ctrl+C gracefully
            print()


if __name__ == "__main__":
    main()