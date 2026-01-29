import sys
import shutil
import subprocess
import os
import shlex
import multiprocessing

# --- 1. Platform & Library Setup ---
try:
    import readline
except ImportError:
    try:
        from pyreadline3 import Readline
        readline = Readline()
    except ImportError:
        # Dummy fallback to prevent crashes if no readline is found
        class DummyReadline:
            def __getattr__(self, name): return lambda *args, **kwargs: None
            def get_current_history_length(self): return 0
            def get_history_item(self, i): return None
            def get_line_buffer(self): return ""
        readline = DummyReadline()

# --- 2. Constants & Globals ---
DEFAULT_HIST_FILE = os.path.expanduser("~/.gemini_shell_history")
ACTIVE_HIST_FILE = None
last_appended_index = 0

# --- 3. Helper Functions ---
def get_history_path():
    """Returns the history path from env or default."""
    env_hist = os.getenv("HISTFILE")
    return os.path.expanduser(env_hist) if env_hist else DEFAULT_HIST_FILE

def sync_history_watermark():
    """Updates the internal counter to match current readline buffer."""
    global last_appended_index
    last_appended_index = readline.get_current_history_length()

def fix_path_for_platform(path):
    """Redirects /tmp/ paths to Windows Temp if running locally."""
    if os.name == 'nt' and path.startswith('/tmp/'):
        return os.path.join(os.environ.get('TEMP', 'C:\\Temp'), path[5:])
    return path

# --- 4. Built-in Command Logic ---
def handle_cd(path):
    target = os.getenv("HOME") if path == "~" or not path else path
    try:
        os.chdir(target)
    except Exception as e:
        print(f"cd: {target}: {e}")

def handle_exit():
    if ACTIVE_HIST_FILE:
        try: readline.write_history_file(ACTIVE_HIST_FILE)
        except Exception: pass
    sys.exit(0)

def handle_history(args):
    global last_appended_index
    if not args:
        end = readline.get_current_history_length()
        for i in range(1, end + 1):
            item = readline.get_history_item(i)
            if item: print(f"   {i}  {item}")
        return

    parts = args.split()
    flag = parts[0]
    path = os.path.expanduser(parts[1]) if len(parts) > 1 else None

    if flag == "-r" and path:
        try:
            readline.read_history_file(path)
            sync_history_watermark()
        except FileNotFoundError:
            print(f"history: -r: {path}: No such file or directory")
    elif flag == "-w" and path:
        try: readline.write_history_file(path)
        except Exception as e: print(f"history: -w: {e}")
    elif flag == "-a" and path:
        try:
            curr = readline.get_current_history_length()
            # Subtract 1 to exclude the 'history -a' command itself
            new_count = (curr - 1) - last_appended_index
            if new_count > 0 and hasattr(readline, 'append_history_file'):
                readline.append_history_file(new_count, path)
            last_appended_index = curr
        except Exception as e: print(f"history: -a: {e}")

# Registry of built-ins
built_in_commands = {
    "echo": lambda args: print(args if args else ""),
    "pwd": lambda _: print(os.getcwd()),
    "cd": handle_cd,
    "exit": lambda _: handle_exit(),
    "history": handle_history,
    "type": lambda cmd: print(f"{cmd} is a shell builtin" if cmd in built_in_commands else f"{cmd} is {shutil.which(cmd)}" if shutil.which(cmd) else f"{cmd}: not found"),
}

# --- 5. Autocompletion ---
def get_path_executables():
    execs = set()
    for d in os.getenv("PATH", "").split(os.pathsep):
        if os.path.isdir(d):
            try: 
                execs.update([f for f in os.listdir(d) if os.access(os.path.join(d, f), os.X_OK)])
            except Exception: pass
    return list(execs)

completion_options = list(built_in_commands.keys()) + get_path_executables()

def completer(text, state):
    matches = [c for c in completion_options if c.startswith(text)]
    return (matches[state] + " ") if state < len(matches) else None

readline.set_completer(completer)
readline.parse_and_bind("tab: complete")
# Safe hook for Windows compatibility
if hasattr(readline, 'set_completion_display_matches_hook'):
    readline.set_completion_display_matches_hook(
        lambda s, m, l: print(f"\n{' '.join(m)}\n$ {readline.get_line_buffer()}", end="", flush=True)
    )

# --- 6. Pipeline & Redirection Logic ---
def run_piped_cmd_windows(cmd_args, in_fd, out_fd):
    """Worker function for Windows Multiprocessing"""
    if in_fd is not None:
        os.dup2(in_fd, sys.stdin.fileno())
        os.close(in_fd)
    if out_fd is not None:
        os.dup2(out_fd, sys.stdout.fileno())
        os.close(out_fd)
        
    cmd = cmd_args[0]
    if cmd in built_in_commands:
        built_in_commands[cmd](" ".join(cmd_args[1:]) if len(cmd_args) > 1 else None)
        sys.exit(0)
    else:
        try: subprocess.run(cmd_args)
        except Exception: sys.exit(1)

def handle_pipeline(line):
    cmds = [shlex.split(c.strip()) for c in line.split('|')]
    
    # --- Windows Implementation (Multiprocessing) ---
    if os.name == 'nt':
        pipes = [os.pipe() for _ in range(len(cmds) - 1)]
        procs = []
        for i in range(len(cmds)):
            inf = pipes[i-1][0] if i > 0 else None
            outf = pipes[i][1] if i < len(cmds)-1 else None
            p = multiprocessing.Process(target=run_piped_cmd_windows, args=(cmds[i], inf, outf))
            p.start()
            procs.append(p)
            # Parent must close pipe ends immediately
            if inf: os.close(inf)
            if outf: os.close(outf)
        for p in procs: p.join()
        return

    # --- Linux Implementation (os.fork) ---
    # This is preferred for the CodeCrafters tester
    pipes = [os.pipe() for _ in range(len(cmds) - 1)]
    pids = []
    
    for i, cmd_args in enumerate(cmds):
        pid = os.fork()
        if pid == 0: # Child
            if i > 0: os.dup2(pipes[i - 1][0], sys.stdin.fileno())
            if i < len(cmds) - 1: os.dup2(pipes[i][1], sys.stdout.fileno())
            
            for r, w in pipes: os.close(r); os.close(w)
            
            if cmd_args[0] in built_in_commands:
                try: built_in_commands[cmd_args[0]](" ".join(cmd_args[1:]) if len(cmd_args) > 1 else None)
                except: pass
                os._exit(0)
            else:
                try: os.execvp(cmd_args[0], cmd_args)
                except: print(f"{cmd_args[0]}: command not found"); os._exit(1)
        else: # Parent
            pids.append(pid)
            
    for r, w in pipes: os.close(r); os.close(w)
    for pid in pids: os.waitpid(pid, 0)

def handle_redirection(command, op):
    parts = command.split(op)
    left, path = parts[0].rstrip(), parts[1].strip()
    
    # Detect Stream (1=stdout, 2=stderr)
    use_stderr = False
    if left.endswith("2"):
        use_stderr = True
        left = left[:-1].rstrip()
    elif left.endswith("1"):
        left = left[:-1].rstrip()
        
    path = fix_path_for_platform(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    cmd_list = shlex.split(left)
    mode = "a" if op == ">>" else "w"
    
    try:
        with open(path, mode) as f:
            if use_stderr:
                subprocess.run(cmd_list, stdout=sys.stdout, stderr=f)
            else:
                subprocess.run(cmd_list, stdout=f, stderr=sys.stderr)
    except Exception as e:
        print(f"bash: {path}: {e}")

# --- 7. Main Loop ---
def main():
    global ACTIVE_HIST_FILE
    
    # Initialize History
    ACTIVE_HIST_FILE = get_history_path()
    if os.path.exists(ACTIVE_HIST_FILE):
        try: readline.read_history_file(ACTIVE_HIST_FILE)
        except Exception: pass
    sync_history_watermark()

    while True:
        try:
            line = input("$ ")
            if not line.strip(): continue
            
            if "|" in line:
                handle_pipeline(line)
                continue
            
            if ">>" in line:
                handle_redirection(line, ">>")
                continue
            elif ">" in line:
                handle_redirection(line, ">")
                continue
            
            # Standard Execution
            cmd_parts = shlex.split(line)
            cmd = cmd_parts[0]
            args = " ".join(cmd_parts[1:]) if len(cmd_parts) > 1 else None
            
            if cmd in built_in_commands:
                built_in_commands[cmd](args)
            elif shutil.which(cmd):
                subprocess.run(cmd_parts)
            else:
                print(f"{cmd}: command not found")
                
        except (EOFError, KeyboardInterrupt):
            print()
            handle_exit()

if __name__ == "__main__":
    main()