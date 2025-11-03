import sys


def main():
    # TODO: Uncomment the code below to pass the first stage
    sys.stdout.write("$ ")
    errorMessage()
    main()

    
def errorMessage():
    # Wait for user input
    command = input()
    print(f"{command}: command not found")


if __name__ == "__main__":
    main()
