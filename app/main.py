import sys

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

    if cmd == "echo":
        output = " ".join(parts[1:]) + "\n"
        sys.stdout.write(output)
    elif cmd == "type":
        # if user typed "type echo" -> we should report "echo is a shell builtin"
        if len(parts) >= 2:
            sys.stdout.write(f"{parts[1]} is a shell builtin\n")
        else:
            sys.stdout.write("type: missing operand\n")
    else:
        # prints the "<command>: command not found" message
        sys.stdout.write(f"{command}: command not found\n")

    return True  # keep looping


if __name__ == "__main__":
    main()
