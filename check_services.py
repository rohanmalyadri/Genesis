import socket
import urllib.request

def check_port(host, port, name):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        if result == 0:
            print(f"[OK] {name} is running on {host}:{port}")
        else:
            print(f"[FAILED] {name} is NOT reachable on {host}:{port}")
        sock.close()
    except Exception as e:
        print(f"[ERROR] Could not check {name}: {e}")

print("--- Service Health Check ---")
check_port('localhost', 6379, 'Redis')
check_port('localhost', 7687, 'Neo4j (Bolt)')
check_port('localhost', 7474, 'Neo4j (HTTP)')
check_port('localhost', 8000, 'FastAPI App')
check_port('localhost', 3000, 'Next.js Frontend')
