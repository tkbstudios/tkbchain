import json
import sys
import time
import socket
import os
from colorama import Fore, Style
import hashlib
import random
import concurrent.futures
import psutil

pid = os.getpid()
osprocess = psutil.Process(pid)
osprocess.nice(psutil.REALTIME_PRIORITY_CLASS)

print(Fore.GREEN + "TKB CHAIN MINER" + Style.RESET_ALL)

MAX_THREADS = str(os.cpu_count())
print(Fore.CYAN + f"Amount of available threads: {MAX_THREADS}" + Style.RESET_ALL)

MINE_THREADS = input(Fore.RED + "Amount of threads to use (empty for 1): " + Style.RESET_ALL)

# if int(MINE_THREADS) > 16:
#    raise Exception("You've set more that 16 threads! \nUsing too much threads could result in performance decrease!")

if str(MINE_THREADS) == "":
    MINE_THREADS = 1

MINE_THREADS = int(MINE_THREADS)
if MINE_THREADS == 0:
    print(Fore.RED + "MINING THREADS CANNOT BE 0! (At least 1)" + Style.RESET_ALL)
    sys.exit(1)

USERNAME = input(Fore.RED + f"Enter your username (CASE SENSITIVE!): " + Style.RESET_ALL)
if USERNAME == "":
    print(Fore.RED + "USERNAME CANNOT BE EMPTY!" + Style.RESET_ALL)
    sys.exit(1)

MINE_IP = "127.0.0.1"
MINE_PORT = 5001
MINE_TIMEOUT = 5
SOCKET_BUFFER_SIZE = 32768
DIFFICULTY = 0

print("Connecting to mining pool..")
socketconn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
socketconn.connect((MINE_IP, MINE_PORT))
socketconn.settimeout(MINE_TIMEOUT)
socketconn.send(f"recipient:{USERNAME}".encode())
time.sleep(0.5)
print(Fore.GREEN + "Connected to mining pool!")

pending_transactions_response = None
pending_transactions_data = None
pending_transactions_json = {}
num_pending_transactions = 0

mined = False

difficulty_pattern = '0' * DIFFICULTY


def mine(block_data, thread_num):
    global pending_transactions_response, pending_transactions_data, pending_transactions_json
    global num_pending_transactions, mined
    start_time = time.time()

    nonce = random.randint(0, 100000)
    print(f"THREAD-{thread_num}: Starting mining block...")
    while True:
        if mined:
            break

        last_block_loaded = json.loads(block_data)

        block_attempt = {
            "index": int(last_block_loaded['index']) + 1,
            "timestamp": time.time(),
            "transactions": pending_transactions_json,
            "proof": int(last_block_loaded['proof']) + 1,
            "previous_hash": last_block_loaded['hash']
        }
        block_attempt = json.dumps(block_attempt)
        block_hash = hashlib.sha256(block_attempt.encode()).hexdigest()
        if block_hash.startswith("000"):
            mined = True
            end_time = time.time()
            print(
                Fore.GREEN + f"\nTHREAD-{thread_num}:"
                             f"Mined block with nonce {nonce} and hash {block_hash}"
                             f"in {end_time - start_time:.2f} seconds" + Style.RESET_ALL)
            data_to_send = f"mine:{str(block_hash)}"
            socketconn.send(data_to_send.encode())
            response = socketconn.recv(SOCKET_BUFFER_SIZE)
            if response.decode() == "Block added to the blockchain.":
                print(Fore.GREEN + f"\nTHREAD-{thread_num}: Server confirmed block was added!" + Style.RESET_ALL)
                break
        nonce += 1
        time.sleep(0.0005)


def get_difficulty():
    global DIFFICULTY
    socketconn.send("get_difficulty".encode())
    print("Waiting for difficulty from pool...")
    diff_response = socketconn.recv(1024)
    DIFFICULTY = int(diff_response.decode())


def get_pending_transactions():
    global pending_transactions_response, pending_transactions_data, pending_transactions_json, num_pending_transactions
    time.sleep(0.5)
    pending_transactions_message = "get_pending_transactions".encode()
    socketconn.send(pending_transactions_message)
    pending_transactions_response = socketconn.recv(SOCKET_BUFFER_SIZE)
    pending_transactions_data = pending_transactions_response.decode()
    pending_transactions_json = json.loads(pending_transactions_data)
    num_pending_transactions = len(pending_transactions_json)
    time.sleep(0.5)


def get_last_block():
    socketconn.send("get_last_block".encode())
    last_block = socketconn.recv(SOCKET_BUFFER_SIZE).decode()
    return last_block


def mine_init():
    global pending_transactions_response, pending_transactions_data, pending_transactions_json
    global num_pending_transactions, mined
    print(Fore.WHITE + "Press S to view stats." + Style.RESET_ALL)
    while True:
        try:
            get_difficulty()
            print(f"Difficulty: {DIFFICULTY}")
            get_pending_transactions()
            block_data = get_last_block()

            with concurrent.futures.ThreadPoolExecutor(max_workers=MINE_THREADS) as executor:
                futures = []
                for i in range(MINE_THREADS):
                    if not mined:
                        future = executor.submit(mine, block_data, i)
                        futures.append(future)
                for future in futures:
                    future.result()

            # Reset mined flag
            mined = False
        except Exception as e:
            raise Exception(e)


def clean_exit():
    print(Fore.YELLOW + "Stopping threads..." + Style.RESET_ALL)
    socketconn.send("exit".encode())
    socketconn.close()
    print(Fore.GREEN + "Stopped threads!" + Style.RESET_ALL)
    sys.exit(0)


try:
    mine_init()
except KeyboardInterrupt:
    clean_exit()
except Exception as e:
    print(f"EXCEPTION! \n{e}")
    clean_exit()
