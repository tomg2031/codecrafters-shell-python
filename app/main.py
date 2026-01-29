import sys, shutil, subprocess, os, shlex, readline

a = shutil.which
built_in_commands = {
    "echo": print,
    "type": lambda cmd: print(f"{cmd} is a shell builtin" if cmd in built_in_commands else f"{cmd} is {a(cmd)}" if a(cmd) else f"{cmd}: not found"),
    "exit": lambda _ : sys.exit(0),
    "pwd": lambda _ : print(os.getcwd()),
    "cd": lambda path: os.chdir(os.getenv("HOME")) if path=="~" else os.chdir(path) if os.path.isdir(path) else print(f"cd: {path}: No such file or directory"),
    # Updated history command to check for -r flag
    "history": lambda args: handle_history_command(args),
}

def handle_history_command(args):
    if not args:
        # Standard: list history
        print(inputHistory(args)[0], end="")
        return

    # Split args to handle flags easily
    arg_list = args.split()
    flag = arg_list[0]
    
    if flag == "-r" and len(arg_list) > 1:
        # Load from file
        file_path = arg_list[1]
        load_history(file_path)
        
    elif flag == "-w" and len(arg_list) > 1:
        # Save to file
        file_path = arg_list[1]
        save_history(file_path)
        
    else:
        # Fallback to listing history if args is just a number
        print(inputHistory(args)[0], end="")

def save_history(file_path):
    try:
        path = os.path.expanduser(file_path.strip())
        # Python's readline makes this very easy
        readline.write_history_file(path)
    except Exception as e:
        print(f"history: -w: {e}")

def parse_args(shell_input: str):
    shell_input_list = shlex.split(shell_input)
    command = shell_input_list[0]
    args = " ".join(shell_input_list[1:]) if len(shell_input_list) > 1 else None
    return command, args

def get_executables_from_path():
    executables = []
    for directory in os.getenv("PATH", "").split(os.pathsep):
        if not os.path.isdir(directory):
            continue
        try:
            for file in os.listdir(directory):
                full_path = os.path.join(directory, file)
                if os.access(full_path, os.X_OK) and not os.path.isdir(full_path):
                    executables.append(file)
        except PermissionError:
            continue
    return executables

lasagna = list(built_in_commands.keys()) + get_executables_from_path()
def completer(text, state):
    options = [cmd for cmd in lasagna if cmd.startswith(text)]
    if state < len(options):
        return options[state] + ' '
    else:
        return None

readline.set_completer(completer)
readline.parse_and_bind('tab: complete')
readline.set_completion_display_matches_hook(
    lambda substitution, matches, longest_match_length:
        print(f"\n{' '.join(matches)}\n$ {readline.get_line_buffer()}", end="", flush=True)
)

def handle_redirection(command, mode):
    parts = command.split(mode)
    left = parts[0].strip()
    right = parts[1].strip()
    out = 1
    if left[-1]=='2':
        out = 2
    if left[-1] == "1" or left[-1] == "2":
        left = left[:-1].strip()

    cmd_list = shlex.split(left)
    file_mode = "a" if mode == ">>" else "w"

    if out==1:
        try:
            with open(right, file_mode) as f:
                subprocess.run(cmd_list, stdout=f, stderr=sys.stderr)
        except FileNotFoundError:
            print(f"{cmd_list[0]}: command not found")
    else:
        try:
            with open(right, file_mode) as f:
                subprocess.run(cmd_list, stdout=sys.stdout, stderr=f)
        except FileNotFoundError:
            print(f"{cmd_list[0]}: command not found")

def handle_pipeline(command_line):
    # Split into component commands
    commands = [shlex.split(cmd.strip()) for cmd in command_line.split('|')]
    n = len(commands)
    if n < 2:
        print("Pipeline requires at least two commands.")
        return

    # Create N-1 pipes
    pipes = [os.pipe() for _ in range(n - 1)]
    pids = []

    for i, cmd_args in enumerate(commands):
        pid = os.fork()
        if pid == 0:
            # Child process
            if i > 0:
                os.dup2(pipes[i - 1][0], sys.stdin.fileno())
            if i < n - 1:
                os.dup2(pipes[i][1], sys.stdout.fileno())

            # Close all pipe fds in child
            for r, w in pipes:
                try:
                    os.close(r)
                    os.close(w)
                except OSError:
                    pass

            # Execute built-in or external
            if cmd_args[0] in built_in_commands:
                try:
                    built_in_commands[cmd_args[0]](" ".join(cmd_args[1:]) if len(cmd_args) > 1 else None)
                except Exception as e:
                    print(f"{cmd_args[0]}: error {e}")
                os._exit(0)
            else:
                try:
                    os.execvp(cmd_args[0], cmd_args)
                except FileNotFoundError:
                    print(f"{cmd_args[0]}: command not found")
                    os._exit(1)
        else:
            pids.append(pid)

    # Parent closes all pipe fds
    for r, w in pipes:
        try:
            os.close(r)
            os.close(w)
        except OSError:
            pass

    # Wait for all children
    for pid in pids:
        os.waitpid(pid, 0)

def inputHistory(args):
    result = ""
    # Get the current length
    end = readline.get_current_history_length()
    
    # We subtract 1 because the 'history' command itself 
    # has already been added to the buffer by readline
    start = 1
    if args and str(args).isdigit():
        n = int(args)
        start = max(1, end - n + 1)

    # Loop only up to display_end
    for i in range(start, end + 1):
        cmd = readline.get_history_item(i)
        if cmd:
            # The tester is strict about spacing. 
            # Usually, it's 4 spaces, then the index, then 2 spaces.
            # Adjust this format string to match the 'Expected' exactly.
            result += f"   {i}  {cmd}\n"
            
    return result, ""

def load_history(file_path):
    try:
        # Resolve ~ if the user provides a home path
        expanded_path = os.path.expanduser(file_path.strip())
        with open(expanded_path, "r") as file:
            for line in file:
                # Use rstrip() as requested to clean the line
                cleaned_line = line.rstrip()
                if cleaned_line:  # Avoid adding empty lines to history
                    readline.add_history(cleaned_line)
    except FileNotFoundError:
        print(f"history: {file_path}: No such file or directory")
    except Exception as e:
        print(f"history: error loading file: {e}")

def main():
    while True:
        command = input("$ ")
        if not command.strip():
            continue

        # --- Handle pipelines ---
        if "|" in command:
            handle_pipeline(command)
            continue

        # --- Handle redirection ---
        if ">>" in command:
            handle_redirection(command, ">>")
            continue

        if ">" in command:
            handle_redirection(command, ">")
            continue

        # --- Normal execution ---
        cmd, args = parse_args(command)
        if a(cmd) and cmd not in built_in_commands:
            subprocess.run(shlex.split(command))
            continue
        try:
            built_in_commands[cmd](args)
        except KeyError:
            print(f"{cmd}: command not found")

if __name__ == "__main__":
    main()