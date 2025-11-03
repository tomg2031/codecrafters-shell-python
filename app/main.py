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
    
    else:
        # prints the "<command>: command not found" message
        print(f"{command}: command not found")


if __name__ == "__main__":
    main()
