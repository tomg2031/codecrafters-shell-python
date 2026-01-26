import sys, os

SHELL_BUILTIN = ["echo","exit","type"]
PATH = os.getenv("PATH", "")
paths = PATH.split(":")

def find_exec(cmd):
    for path in paths:
        full_path = f"{path}/{cmd}"
        try:
            with open(full_path):
                if os.access(full_path, os.X_OK):
                    return full_path
        except FileNotFoundError:
            continue
    return None

def main():
    sys.stdout.write("$ ")
    command = input()
    if command == "exit":
        sys.exit()
    elif command.split(" ")[0] == "echo":
        print(command[5:])
    elif command.split(" ")[0] == "type":
        if command[5:] in SHELL_BUILTIN:
            print(f"{command[5:]} is a shell builtin")
        elif find_exec(command[5:]):
            print(f"{command[5:]} is {find_exec(command[5:])}")
        else:
            print(f"{command[5:]}: not found")
    elif find_exec(command.split(" ")[0]):
        os.system(command)
    else:
        print(f"{command}: command not found")

    
if __name__ == "__main__":
    while True:
        main()