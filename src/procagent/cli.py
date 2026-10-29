"""Terminal chat: python -m procagent.cli [procedure.yaml]"""
import sys

from .agent import Agent
from .procedure import load_procedure


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "procedures/collections_v1.yaml"
    agent = Agent(load_procedure(path))
    print("agent>", agent.start().text)
    while agent.state != "done":
        try:
            said = input("you> ")
        except EOFError:
            break
        print("agent>", agent.respond(said).text)


if __name__ == "__main__":
    main()
