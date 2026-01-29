import sys, shutil, subprocess, os, shlex, readline

# --- Constants & Globals ---
DEFAULT_HIST_FILE = os.path.expanduser("~/.gemini_shell_history")
ACTIVE_HIST_FILE = None
last_appended_index = 0

# --- History Management ---
def get_history_file_path():
    """Determines the correct history file path from env or default."""
    env_hist = os.getenv("HISTFILE")
    if env_hist:
        return os.path.expanduser(env_hist)
    return DEFAULT_HIST_FILE

def load_history_at_startup():
    global ACTIVE_HIST_FILE, last_appended_index
    
    ACTIVE_HIST_FILE = get_history_file_path()
    
    if ACTIVE_HIST_FILE and os.path.exists(ACTIVE_HIST_FILE):
        try:
            readline.read_history_file(ACTIVE_HIST_FILE)
        except Exception:
            pass # Fail silently if file is unreadable

    # Set the watermark so we know where the 'current session' begins
    last_appended_index = readline.get_current_history_length()

def save_history_session():
    """Writes the current history to the active file."""
    if ACTIVE_HIST_FILE:
        try:
            readline.write_history_file(ACTIVE_HIST_FILE)
        except Exception:
            pass

def append_history(file_path):
    global last_appended_index
    try:
        path = os.path.expanduser(file_path.strip())
        current_length = readline.get_current_history_length()
        
        # Calculate new lines since last append
        new_items_count = current_length - last_appended_index
        
        if new_items_count > 0:
            readline.append_history_file(new_items_count, path)
            last_appended_index = current_length
    except Exception as e:
        print(f"history: -a: {e}")

def handle_history_command(args):
    if not args:
        print(format_history_output(), end="")
        return

    parts = args.split()
    flag = parts[0]
    file_arg = parts[1] if len(parts) > 1 else None

    if flag == "-r" and file_arg:
        try:
            readline.read_history_file(os.path.expanduser(file_arg))
        except FileNotFoundError:
            print(f"history: -r: {file_arg}: No such file or directory")
    elif flag == "-w" and file_arg:
        try:
            readline.write_history_file(os.path.expanduser(file_arg))
        except Exception as e:
            print(f"history: -w: {e}")
    elif flag == "-a" and file_arg:
        append_history(file_arg)
    else:
        # Fallback: interpret args as a number (e.g. "history 5")
        print(format_history_output(args), end="")

def format_history_output(limit_arg=None):
    result = ""
    end = readline.get_current_history_length()
    start = 1
    
    if limit_arg and str(limit_arg).isdigit():
        start = max(1, end - int(limit_arg) + 1)

    for i in range(start, end + 1):
        cmd = readline.get_history_item(i)
        if cmd:
            # Matches standard 4-space indentation
            result += f"   {i}  {cmd}\n"
    return result

# --- Built-in Commands ---
def builtin_cd(path):
    target = os.getenv("HOME") if path == "~" or not path else path
    try:
        os.chdir(target)
    except FileNotFoundError:
        print(f"cd: {target}: No such file or directory")
    except NotADirectoryError:
        print(f"cd: {target}: Not a directory")

def builtin_type(cmd):
    if cmd in built_in_commands:
        print(f"{cmd} is a shell builtin")
    else:
        path = shutil.which(cmd)
        if path:
            print(f"{cmd} is {path}")
        else:
            print(f"{cmd}: not found")

def builtin_exit(_):
    save_history_session()
    sys.exit(0)

built_in_commands = {
    "echo": print,
    "pwd": lambda _: print(os.getcwd()),
    "cd": builtin_cd,
    "type": builtin_type,
    "exit": builtin_exit,
    "history": handle_history_command,
}

# --- Autocompletion ---
def get_executables_from_path():
    executables = set()
    for directory in os.getenv("PATH", "").split(os.pathsep):
        if not os.path.isdir(directory):
            continue
        try:
            for file in os.listdir(directory):
                full_path = os.path.join(directory, file)
                if os.access(full_path, os.X_OK) and not os.path.isdir(full_path):
                    executables.add(file)
        except PermissionError:
            continue
    return list(executables)

completion_options = list(built_in_commands.keys()) + get_executables_from_path()

def completer(text, state):
    matches = [cmd for cmd in completion_options if cmd.startswith(text)]
    return (matches[state] + ' ') if state < len(matches) else None

readline.set_completer(completer)
readline.parse_and_bind('tab: complete')
readline.set_completion_display_matches_hook(
    lambda substitution, matches, longest_match_length:
        print(f"\n{' '.join(matches)}\n$ {readline.get_line_buffer()}", end="", flush=True)
)

# --- Execution Logic ---
def parse_args(shell_input):
    parts = shlex.split(shell_input)
    command = parts[0]
    args = " ".join(parts[1:]) if len(parts) > 1 else None
    return command, args

def run_external_command(command_list, stdout=sys.stdout, stderr=sys.stderr):
    try:
        subprocess.run(command_list, stdout=stdout, stderr=stderr)
    except FileNotFoundError:
        print(f"{command_list[0]}: command not found")

def handle_redirection(command, operator):
    # Split command: "echo hello > file.txt" -> ["echo hello ", " file.txt"]
    parts = command.split(operator)
    cmd_part = parts[0].strip()
    file_part = parts[1].strip()
    
    # Check for stderr redirection (2>, 2>>)
    use_stderr = False
    if cmd_part.endswith("2"):
        use_stderr = True
        cmd_part = cmd_part[:-1].strip()

    cmd_list = shlex.split(cmd_part)
    file_mode = "a" if operator == ">>" else "w"

    try:
        with open(file_part, file_mode) as f:
            if use_stderr:
                run_external_command(cmd_list, stdout=sys.stdout, stderr=f)
            else:
                run_external_command(cmd_list, stdout=f, stderr=sys.stderr)
    except PermissionError:
        print(f"bash: {file_part}: Permission denied")

def handle_pipeline(command_line):
    # Split by pipe '|'
    commands = [shlex.split(cmd.strip()) for cmd in command_line.split('|')]
    num_cmds = len(commands)
    
    if num_cmds < 2:
        print("Pipeline requires at least two commands.")
        return

    pipes = [os.pipe() for _ in range(num_cmds - 1)]
    pids = []

    for i, cmd_args in enumerate(commands):
        pid = os.fork()
        if pid == 0: # Child
            # Set up reading from previous pipe
            if i > 0:
                os.dup2(pipes[i - 1][0], sys.stdin.fileno())
            # Set up writing to next pipe
            if i < num_cmds - 1:
                os.dup2(pipes[i][1], sys.stdout.fileno())

            # Close all pipe fds in child
            for r, w in pipes:
                os.close(r); os.close(w)

            # Execution
            cmd_name = cmd_args[0]
            if cmd_name in built_in_commands:
                # Builtins in pipes must exit explicitely or the child process hangs
                built_in_commands[cmd_name](" ".join(cmd_args[1:]) if len(cmd_args) > 1 else None)
                os._exit(0)
            else:
                try:
                    os.execvp(cmd_name, cmd_args)
                except FileNotFoundError:
                    print(f"{cmd_name}: command not found")
                    os._exit(1)
        else: # Parent
            pids.append(pid)

    # Parent closes all pipes
    for r, w in pipes:
        os.close(r); os.close(w)

    # Wait for children
    for pid in pids:
        os.waitpid(pid, 0)

# --- Main Loop ---
def main():
    load_history_at_startup()

    while True:
        try:
            command = input("$ ")
            if not command.strip():
                continue
        except (EOFError, KeyboardInterrupt):
            # Handle Ctrl-D and Ctrl-C gracefully
            print()
            save_history_session()
            sys.exit(0)

        # 1. Pipeline
        if "|" in command:
            handle_pipeline(command)
            continue

        # 2. Redirection
        if ">>" in command:
            handle_redirection(command, ">>")
            continue
        if ">" in command:
            handle_redirection(command, ">")
            continue

        # 3. Standard Execution
        cmd_name, args = parse_args(command)
        
        if cmd_name in built_in_commands:
            try:
                built_in_commands[cmd_name](args)
            except Exception as e:
                print(f"Error executing builtin {cmd_name}: {e}")
        elif shutil.which(cmd_name):
            run_external_command(shlex.split(command))
        else:
            print(f"{cmd_name}: command not found")

if __name__ == "__main__":
    main()