#!/usr/bin/env python3
import sys
import os
import shlex
import shutil
import subprocess

def main():

    # print("PYTHON PATH:", os.environ.get("PATH"))
    # print("shutil.which('codecrafters') ->", shutil.which("codecrafters"))


    while True:
        try:
            # prompt
            sys.stdout.write("$ ")
            sys.stdout.flush()

            if not error_message():
                break  # exit requested

        except EOFError:
            # Ctrl-D / end-of-input => exit
            sys.stdout.write("\n")
            break
        except KeyboardInterrupt:
            # Ctrl-C: print newline and continue prompting
            sys.stdout.write("\n")
            continue

def error_message():
    line = input().strip()
    if not line:
        return True

    if line.startswith("exit"):
        return False

    # parse respecting quotes
    try:
        parts = shlex.split(line)
    except ValueError as e:
        # malformed quoting
        print(f"shell: parse error: {e}")
        return True

    cmd = parts[0]

    # builtins
    if cmd == "echo":
        print(" ".join(parts[1:]))
        return True

    elif cmd == "type":
        if len(parts) < 2:
            print("type: missing operand")
        else:
            target = parts[1]
            builtins = {"echo", "type", "exit", "pwd", "cd"}
            if target in builtins:
                print(f"{target} is a shell builtin")
            elif (full := shutil.which(target)):
                print(f"{target} is {full}")
            else:
                print(f"{target}: not found")
        return True
    
    elif cmd == "pwd":
        print(os.getcwd())
        return True
    
    elif cmd == "cd":
        if len(parts) > 1:
            try:
                if parts[1] == "~":
                    parts[1] = os.getenv("HOME")
                else:
                    os.chdir(parts[1])
            except OSError:
                print(f"cd: {parts[1]}: No such file or directory")
        return True

    else:
        # check if command is an external program
        if full_path := findExe(cmd):
            # run it safely with arguments
            try:
                subprocess.run([cmd] + parts[1:], executable=full_path)
                # optionally: handle non-zero exit codes
                # if result.returncode != 0:s
                #     print(f"exit status: {result.returncode}")
            except FileNotFoundError:
                print(f"{cmd}: not found (FileNotFoundError)")
            except PermissionError:
                print(f"{cmd}: permission denied")
            except Exception as e:
                print(f"{cmd}: execution failed: {e}")
        
        else:
            print(f"{cmd}: command not found")
            return True

        return True

def findExe(exe):
    """Return full path to executable or None."""
    return shutil.which(exe)

if __name__ == "__main__":
    main()
