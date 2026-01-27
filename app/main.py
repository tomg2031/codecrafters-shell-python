#!/usr/bin/env python3
import sys
import os
import readline
import shlex
import shutil
import subprocess

def main():
    # Setup readline once
    readline.set_completer(auto_complete)
    readline.set_completion_display_matches_hook(display_matches)
    readline.parse_and_bind("tab: complete")
    # Use 'tab: complete' for standard behavior
    if 'libedit' in readline.__doc__: 
         readline.parse_and_bind("bind ^I rl_complete")
    else:
         readline.parse_and_bind("tab: complete")

    while True:
        try:
            if not handle_command():
                break  # exit requested

        except EOFError:
            # Ctrl-D / end-of-input => exit
            sys.stdout.write("\n")
            break
        except KeyboardInterrupt:
            # Ctrl-C: print newline and continue prompting
            sys.stdout.write("\n")
            continue

def handle_command():
    try:
        line = input("$ ").strip()
    except EOFError:
        print()
        return False
    
    if not line:
        return True
    if line == "exit 0" or line.startswith("exit"):
        return False
    
    # Redirection check
    if ">" in line or "1>" in line:
        os.system(line)
        return True

    # parse respecting quotes
    try:
        parts = shlex.split(line)
    except ValueError as e:
        # malformed quoting
        print(f"shell: parse error: {e}")
        return True

    cmd, *args = parts

    # builtins
    match cmd:
        case "echo":
            print(" ".join(args))
        case "pwd":
            print(os.getcwd())
        case "cd":
            path = args[0] if args else os.getnev("HOME")
            if path == "~":
                path = os.getenv("HOME")
            try:
                os.chdir(path)
            except OSError:
                print(f"cd: {path}: No such file or directory")
        case "type":
            if not args:
                print("type: missing operand")
            else:
                target = args[0]
                builtins = {"echo", "type", "exit", "pwd", "cd"}
                if target in builtins:
                    print(f"{target} is a shell builtin")
                elif (full := shutil.which(target)):
                    print(f"{target} is {full}")
                else:
                    print(f"{target}: not found")
        case _:
            if full_path := findExe(cmd):
                # run it safely with arguments
                try:
                    subprocess.run(parts)

                except Exception as e:
                    print(f"{cmd}: execution failed: {e}")
            
            else:
                print(f"{cmd}: command not found")
    return True

def auto_complete(text, state):
    # Get all potential commands
    builtins = ["echo", "type", "exit", "pwd", "cd"]
    commands = set(builtins)
    
    path_env = os.environ.get("PATH", "")
    for directory in path_env.split(os.pathsep):
        if os.path.isdir(directory):
            try:
                for filename in os.listdir(directory):
                    if filename.startswith(text):
                        commands.add(filename)
            except Exception:
                continue

    matches = sorted([c for c in commands if c.startswith(text)])

    if state < len(matches):
        # If it's a unique match, add a space
        if len(matches) == 1:
            return matches[state] + " "
        # Otherwise, return the match without a space so user can keep typing
        return matches[state]
    return None

def display_matches(substitution, matches, longest_match_len):
    """
    This hook is called when the user presses TAB twice.
    It prints the possibilities on a new line.
    """
    print() # Move to new line
    # Print matches separated by two spaces (standard shell style)
    print("  ".join(matches))
    # Re-print the prompt and current line content
    print(f"$ {readline.get_line_buffer()}", end="", flush=True)

def findExe(exe):
    """Return full path to executable or None."""
    return shutil.which(exe)

if __name__ == "__main__":
    main()
