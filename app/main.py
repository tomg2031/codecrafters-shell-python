import sys
import shutil
import subprocess
import os
import shlex
import multiprocessing

# --- Cross-Platform Readline Import ---
try:
    import readline
except ImportError:
    try:
        from pyreadline3 import Readline
        readline = Readline()
    except ImportError:
        # Minimal fallback if pyreadline3 is not installed
        class DummyReadline:
            def __getattr__(self, name): return lambda *args, **kwargs: None
            def get_current_history_length(self): return 0
            def get_history_item(self, index): return None
            def get_line_buffer(self): return ""
        readline = DummyReadline()

# --- Constants & Globals ---
DEFAULT_HIST_FILE = os.path.expanduser("~/.gemini_shell_history")
ACTIVE_HIST_FILE = None
last_appended_index = 0

# --- History Management ---
def get_history_file_path():
    env_hist = os.getenv("HISTFILE")
    if env_hist:
        return os.path.expanduser(env_hist)
    return DEFAULT_HIST_FILE

def load_history(file_path):
    global last_appended_index
    try:
        path = os.path.expanduser(file_path.strip())
        readline.read_history_file(path)
        # Crucial: update the watermark so we don't 'append' these again later
        last_appended_index = readline.get_current_history_length()
    except Exception as e:
        print(f"history: -r: {e}")

def save_history_session():
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
        
        # Calculate items added since the last sync, excluding this current command
        new_items_count = (current_length - 1) - last_appended_index
        
        if new_items_count > 0:
            if hasattr(readline, 'append_history_file'):
                readline.append_history_file(new_items_count, path)
            
            # Sync watermark to the end of the buffer
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
        except Exception as e:
            print(f"history: -r: {file_arg}: {e}")
    elif flag == "-w" and file_arg:
        try:
            readline.write_history_file(os.path.expanduser(file_arg))
        except Exception as e:
            print(f"history: -w: {e}")
    elif flag == "-a" and file_arg:
        append_history(file_arg)
    else:
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
            result += f"   {i}  {cmd}\n"
    return result

# --- Built-in Commands ---
def builtin_cd(path):
    target = os.getenv("HOME") if path == "~" or not path else path
    try:
        os.chdir(target)
    except Exception as e:
        print(f"cd: {target}: {e}")

def builtin_type(cmd):
    if cmd in built_in_commands:
        print(f"{cmd} is a shell builtin")
    else:
        path = shutil.which(cmd)
        if path:
            print(f"{cmd} is {path}")
        else:
            print(f"{cmd}: not found")

built_in_commands = {
    "echo": print,
    "pwd": lambda _: print(os.getcwd()),
    "cd": builtin_cd,
    "type": builtin_type,
    "exit": lambda _: (save_history_session(), sys.exit(0)),
    "history": handle_history_command,
}

# --- Autocompletion ---
def get_executables_from_path():
    executables = set()
    for directory in os.getenv("PATH", "").split(os.pathsep):
        if not os.path.isdir(directory): continue
        try:
            for file in os.listdir(directory):
                if os.access(os.path.join(directory, file), os.X_OK):
                    executables.add(file)
        except Exception: continue
    return list(executables)

completion_options = list(built_in_commands.keys()) + get_executables_from_path()

def completer(text, state):
    matches = [cmd for cmd in completion_options if cmd.startswith(text)]
    return (matches[state] + ' ') if state < len(matches) else None

# Safe Configuration for Windows
readline.set_completer(completer)
readline.parse_and_bind('tab: complete')
if hasattr(readline, 'set_completion_display_matches_hook'):
    readline.set_completion_display_matches_hook(
        lambda substitution, matches, longest_match_length:
            print(f"\n{' '.join(matches)}\n$ {readline.get_line_buffer()}", end="", flush=True)
    )

# --- Execution Logic ---
def run_external_command(command_list, stdout=sys.stdout, stderr=sys.stderr):
    try:
        subprocess.run(command_list, stdout=stdout, stderr=stderr)
    except FileNotFoundError:
        print(f"{command_list[0]}: command not found")

def handle_redirection(command, operator):
    parts = command.split(operator)
    cmd_part, file_part = parts[0].rstrip(), parts[1].strip()
    use_stderr = False
    if cmd_part.endswith("2"):
        use_stderr, cmd_part = True, cmd_part[:-1].rstrip()
    elif cmd_part.endswith("1"):
        cmd_part = cmd_part[:-1].rstrip()

    cmd_list = shlex.split(cmd_part)
    file_mode = "a" if operator == ">>" else "w"
    
    # Path resolution for /tmp/ on Windows
    if file_part.startswith('/tmp/'):
        file_part = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), file_part[5:])
    
    os.makedirs(os.path.dirname(file_part), exist_ok=True)

    try:
        with open(file_part, file_mode) as f:
            if use_stderr:
                run_external_command(cmd_list, stdout=sys.stdout, stderr=f)
            else:
                run_external_command(cmd_list, stdout=f, stderr=sys.stderr)
    except Exception as e:
        print(f"bash: {file_part}: {e}")

def run_piped_command(cmd_args, input_fd, output_fd):
    """
    Child process target.
    input_fd: The file descriptor to read from (stdin).
    output_fd: The file descriptor to write to (stdout).
    """
    try:
        if input_fd is not None:
            os.dup2(input_fd, sys.stdin.fileno())
            os.close(input_fd) # Close original after duping

        if output_fd is not None:
            os.dup2(output_fd, sys.stdout.fileno())
            os.close(output_fd) # Close original after duping

        cmd_name = cmd_args[0]
        if cmd_name in built_in_commands:
            # Run builtin and exit
            built_in_commands[cmd_name](" ".join(cmd_args[1:]) if len(cmd_args) > 1 else None)
            sys.exit(0)
        else:
            # Use subprocess for external commands
            # shell=False is safer with shlex.split results
            subprocess.run(cmd_args)
            sys.exit(0)
    except Exception as e:
        # Don't let exceptions hang the process
        sys.exit(1)

def handle_pipeline(command_line):
    commands = [shlex.split(cmd.strip()) for cmd in command_line.split('|')]
    num_cmds = len(commands)
    
    processes = []
    # Store pipe pairs so we can manage their lifecycle
    pipe_list = []

    # Create n-1 pipes
    for _ in range(num_cmds - 1):
        pipe_list.append(os.pipe())

    for i in range(num_cmds):
        # Determine the input/output for this command
        # command 0: stdin = None, stdout = pipe[0] write
        # command 1: stdin = pipe[0] read, stdout = pipe[1] write
        # command n: stdin = pipe[n-1] read, stdout = None
        
        in_fd = pipe_list[i-1][0] if i > 0 else None
        out_fd = pipe_list[i][1] if i < num_cmds - 1 else None

        p = multiprocessing.Process(
            target=run_piped_command,
            args=(commands[i], in_fd, out_fd)
        )
        p.start()
        processes.append(p)

    # IMPORTANT: Parent MUST close all pipe ends immediately after starting processes.
    # If the parent keeps the write-end open, the 'wc' command will wait forever
    # because the pipe never signals EOF.
    for r, w in pipe_list:
        os.close(r)
        os.close(w)

    # Wait for the last command in the pipeline specifically
    for p in processes:
        p.join()

# --- Main ---
def main():
    load_history_at_startup()
    while True:
        try:
            command = input("$ ")
            if not command.strip(): continue
            if "|" in command:
                handle_pipeline(command)
                continue
            if ">>" in command:
                handle_redirection(command, ">>")
                continue
            if ">" in command:
                handle_redirection(command, ">")
                continue
            
            cmd_name, args = shlex.split(command)[0], " ".join(shlex.split(command)[1:]) if len(shlex.split(command)) > 1 else None
            if cmd_name in built_in_commands:
                built_in_commands[cmd_name](args)
            elif shutil.which(cmd_name):
                run_external_command(shlex.split(command))
            else:
                print(f"{cmd_name}: command not found")
        except (EOFError, KeyboardInterrupt):
            print(); save_history_session(); break

if __name__ == "__main__":
    main()