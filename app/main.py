import sys


def main():
    # TODO: Uncomment the code below to pass the first stage
    sys.stdout.write("$ ")
    errorMessage()
    main()

    
def errorMessage():
    # Wait for user input
    command = input()
    if command.startswith("exit"): 
        sys.exit(0)
    command_list = command.split(" ")
    if command_list[0] == "echo":
        output = " ".join(command_list[1:]) + "\n"
        sys.stdout.write(output)
    if command_list[0] == "type":
        output = f"{command_list[3:8]}is a shell builtin\n"
        sys.stdout.write(output)
    else:
        # prints the "<command>: command not found" message
        sys.stdout.write(f"{command}: command not found\n")


if __name__ == "__main__":
    main()
