import sys
import shutil

def main():
    while True:
        # prompt
        sys.stdout.write("$ ")
        sys.stdout.flush()

        try:
            if not error_message():
                # error_message returns False when we should exit loop
                break
        except EOFError:
            # Ctrl-D / end-of-input => exit
            break


def error_message():
    # Wait for user input
    command = input().strip()
    if not command:
        return True  # empty line, just re-prompt

    if command.startswith("exit"):
        return False  # signal to caller to stop

    parts = command.split()
    cmd = parts[0]
    # condition if echo is entered
    if cmd == "echo":
        output = " ".join(parts[1:]) + "\n"
        sys.stdout.write(output)
    # condition if type is entered 
    elif cmd == "type":
        if len(parts) < 2:
            sys.stdout.write("type: missing operand\n")
        else:
            target = parts[1]
            builtins = {"echo", "type", "exit"}  # add more as you implement them
            if target in builtins:
                sys.stdout.write(f"{target} is a shell builtin\n")
            elif full_path := shutil.which(target):
                 sys.stdout.write(f"{target} is {full_path}\n")
            else:
                sys.stdout.write(f"{target}: not found\n")

    else:
        # prints the "<command>: command not found" message
        sys.stdout.write(f"{command}: command not found\n")

    return True  # keep looping


if __name__ == "__main__":
    main()
