#!/usr/bin/env python3
import sys
import os
import readline
import shlex
import shutil
import subprocess
import io

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

def execute_command(cmd, args, input_data=None):
    output_capture = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = output_capture
    
    try:
        match cmd:
            # ... (your existing cases for echo, pwd, cd, type) ...
            case "echo" | "pwd" | "cd" | "type":
                # Existing logic here
                if cmd == "echo": print(" ".join(args))
                elif cmd == "pwd": print(os.getcwd())
                # etc...
                
            case _:
                # For external commands, use subprocess
                sys.stdout = old_stdout # Switch back to real stdout
                result = subprocess.run(
                    [cmd] + args, 
                    input=input_data, 
                    capture_output=True, 
                    text=True
                )
                return result.stdout
                
    finally:
        sys.stdout = old_stdout
        
    return output_capture.getvalue()

def run_multi_pipeline(line):
    # Split by pipe: ['cat file', 'grep hello', 'wc -l']
    stages = [s.strip() for s in line.split("|")]
    current_input = None

    for i, stage in enumerate(stages):
        parts = shlex.split(stage)
        if not parts:
            continue
            
        cmd, *args = parts
        
        # If it's the LAST stage, we want it to print to the REAL terminal
        if i == len(stages) - 1:
            # Check if builtin
            if cmd in {"echo", "pwd", "cd", "type"}:
                # Capture the result and print it to the actual terminal
                result = execute_command(cmd, args, input_data=current_input)
                sys.stdout.write(result)
                sys.stdout.flush()
            else:
                # External command: feed the accumulated input
                subprocess.run([cmd] + args, input=current_input, text=True)
        else:
            # Not the last stage: capture output to pass to the next stage
            current_input = execute_command(cmd, args, input_data=current_input)

def handle_command():
    try:
        line = input("$ ").strip()
    except EOFError:
        print()
        return False
    
    if not line: return True
    if line.startswith("exit"): return False

    # Handle all pipelines (1, 2, or N pipes)
    if "|" in line:
        run_multi_pipeline(line)
        return True

    # Handle single commands
    parts = shlex.split(line)
    cmd, *args = parts
    execute_command(cmd, args)
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

def run_pipeline(cmd1_str, cmd2_str):
    # Parse both commands respecting quotes
    parts1 = shlex.split(cmd1_str)
    parts2 = shlex.split(cmd2_str)

    builtins = {"echo", "pwd", "type"}

    if parts1[0] in builtins:
        # Create a pipe: R = READ END W = WRITE END
        r, w = os.pipe()

        try:
            
            # We redirect stdout to our 'write' file temporarily
            old_stdout = sys.stdout
            sys.stdout = os.fdopen(w, 'w')
            
            # Start the first process
            p1 = subprocess.Popen(parts1, stdout=subprocess.PIPE)

            # Start the second process
            # We take p1.stdout and use it as p2's stdin
            p2 = subprocess.Popen(parts2, stdin=p1.stdout)

            # Allow p1 to receive a SIGPIPE if p2 exits
            p1.stdout.close() 
            sys.stdout = old_stdout
            # Wait for the final command to finish
            subprocess.run(parts2, stdin=r)
            os.close(r)

        except Exception as e:
            sys.stdout = old_stdout
            print(f"pipeline error: {e}")
    else:
        # Standard external-to-external pipeline
        p1 = subprocess.Popen(parts1, stdout=subprocess.PIPE)
        p2 = subprocess.Popen(parts2, stdin=p1.stdout)
        p1.stdout.close()
        p2.communicate()

def findExe(exe):
    """Return full path to executable or None."""
    return shutil.which(exe)

if __name__ == "__main__":
    main()
