from .baidumap import run, list_tools

def main() -> None:
    import os
    import sys
    if len(sys.argv) == 2 and sys.argv[1] == "list-tools":
        list_tools()
        return
    if os.getenv("PC_DEBUG"):
        with open("phone_ip.txt", "r") as f:
            phone_ip = f.read().strip()
        if phone_ip == "":
            raise Exception("phone_ip.txt is empty")
        os.environ["RPC_HOST"] = phone_ip
        os.environ["THING_HOST"] = phone_ip
        os.environ["PLAYER_HOST"] = phone_ip
        os.environ["RPC_PORT"] = "30923"
        os.environ["THING_PORT"] = "30926"
        os.environ["PLAYER_PORT"] = "30930"
    run()
