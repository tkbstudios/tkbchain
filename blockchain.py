import json
import time
from urllib.parse import urlparse
from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin
import requests
import math
import socket
import threading
import string
import random
import hashlib
import sys
from flask_socketio import SocketIO, Namespace

try:
    with open('settings.json', 'r') as settsfile:
        settings = json.load(settsfile)
        SOCKET_BIND_IP = settings['SOCKET_BIND_IP']
        SOCKET_BIND_PORT = settings['SOCKET_BIND_PORT']
        DEFAULT_DIFFICULTY = settings['DEFAULT_DIFFICULTY']
        BLOCK_MINED_DEFAULT_REWARD_AMOUNT = settings['BLOCK_MINED_DEFAULT_REWARD_AMOUNT']
        BASE_TRANSACTION_FEE = settings['BASE_TRANSACTION_FEE']

except Exception as e:
    print(str(e))
    sys.exit(1)


class Blockchain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.genesis_block_found = False
        self.difficulty = DEFAULT_DIFFICULTY
        self.difficulty_pattern = '0' * self.difficulty

        try:
            with open('blockchain.json', 'r') as f:
                chain_data = json.load(f)
                self.chain = chain_data['chain']
                self.current_transactions = chain_data['current_transactions']
                if self.valid_chain(self.chain) is False:
                    raise Exception("Invalid chain!")

        except (IOError, ValueError):
            self.new_block(previous_hash='1', proof=100)

    def load_chain_from_file(self):
        try:
            with open('blockchain.json', 'r') as file:
                chain_data = json.load(file)
                self.chain = chain_data['chain']
                self.current_transactions = chain_data['current_transactions']
                self.nodes = set(chain_data['nodes'])
                self.difficulty = chain_data['difficulty']
        except FileNotFoundError:
            pass

    def get_balance(self, address):
        balance = 0
        for block in self.chain:
            for tx in block['transactions']:
                if tx['sender'] == address:
                    balance -= tx['amount']
                if tx['recipient'] == address:
                    balance += tx['amount']
        return balance

    def get_all_transactions(self):
        transactions = []
        for block in self.chain:
            transactions.extend(block['transactions'])
        return transactions

    def get_pending_transactions(self):
        all_pending_transactions = []
        for transaction in self.current_transactions:
            all_pending_transactions.append(transaction)

        return all_pending_transactions

    def new_block(self, proof, previous_hash=None, recieved_hash=""):
        if self.genesis_block_found:
            if not self.valid_chain(self.chain):
                return {
                    'message': "Invalid block!"
                }
        if recieved_hash == "":
            block = {
                'index': len(self.chain) + 1,
                'timestamp': time.time(),
                'transactions': self.current_transactions,
                'proof': proof,
                'previous_hash': previous_hash or self.chain[-1]['hash'],
                'difficulty': self.difficulty,
                'hash': "1"
            }
        else:
            block = {
                'index': len(self.chain) + 1,
                'timestamp': time.time(),
                'transactions': self.current_transactions,
                'proof': proof,
                'previous_hash': previous_hash or self.chain[-1]['hash'],
                'difficulty': self.difficulty,
                'hash': recieved_hash
            }
        self.current_transactions = []
        self.chain.append(block)
        self.save_chain_to_file()
        return block

    def get_block_by_index(self, index):
        if index >= len(self.chain):
            return None
        return self.chain[index]

    def get_transaction_by_id(self, transaction_id):
        for block in self.chain:
            for transaction in block['transactions']:
                if transaction['id'] == transaction_id:
                    return transaction
        return None

    def new_transaction(self, sender, recipient, amount):
        while True:
            transaction_id = ''.join(random.choices(string.ascii_letters + string.digits, k=24))

            if transaction_id in [txn['id'] for txn in self.current_transactions]:
                continue
            for block in self.chain:
                for txn in block['transactions']:
                    if txn['id'] == transaction_id:
                        continue
            break

        if sender != "blockmined":
            transaction_fee = BASE_TRANSACTION_FEE * len(self.current_transactions)
            amount = amount - transaction_fee
            self.current_transactions.append({
                'id': transaction_id,
                'sender': sender,
                'recipient': recipient,
                'amount': amount,
                'transaction_fee': transaction_fee,
                'timestamp': time.time()
            })
        elif sender == "blockmined":
            self.current_transactions.append({
                'id': transaction_id,
                'sender': "MinerNetwork",
                'recipient': recipient,
                'amount': amount,
                'transaction_fee': 0,
                'timestamp': time.time()
            })

        self.save_chain_to_file()
        return self.last_block['index'] + 1

    def get_last_block(self):
        if len(self.chain) > 0:
            return self.chain[-1]
        else:
            return None

    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, last_proof=0):
        if last_proof == 0:
            self.last_block['proof']
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()  # type: ignore
        return guess_hash[:blockchain.difficulty] == blockchain.difficulty_pattern

    def register_node(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != last_block['hash']:
                return False

            #            if not self.valid_proof(last_block['proof'], block['proof']):
            #                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        neighbors = self.nodes
        new_chain = None
        max_length = len(self.chain)

        for node in neighbors:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True

        return False

    def save_chain_to_file(self):
        with open('blockchain.json', 'w') as f:
            chain_data = {
                'chain': self.chain,
                'current_transactions': self.current_transactions,
                'nodes': list(self.nodes),
                'difficulty': self.difficulty
            }
            write_data = json.dumps(chain_data)
            f.write(write_data)


blockchain = Blockchain()
app = Flask(__name__)
app.config['SECRET_KEY'] = "changethis"
websocket = SocketIO(app)

login_manager = LoginManager()
login_manager.init_app(app)

with open('settings.json', 'r') as f:
    settings = json.load(f)


class AdminUser(UserMixin):
    def __init__(self, new_id):
        self.id = new_id


@login_manager.user_loader
def admin_user_loader(username):
    if username != settings['ADMIN_USER']:
        return None

    user = AdminUser(username)
    return user


@app.route('/', methods=['GET'])
def index_page():
    return render_template('index.html')


@app.route('/api/transactions/new', methods=['POST'])
def new_transaction_api():
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
    response = {
        'confirmation': "OK",
        'index': index
    }
    return jsonify(response), 201


@app.route('/api/chain', methods=['GET'])
def get_chain_api():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


@app.route('/api/balance/<address>')
def get_balance_api(address):
    balance = blockchain.get_balance(address)
    response = {
        'address': address,
        'balance': balance
    }
    return jsonify(response), 200


@app.route('/explorer')
def explorer_page():
    # Get all transactions
    transactions = blockchain.get_all_transactions()

    pending_transactions = blockchain.get_pending_transactions()

    # Get page number from query parameter
    page = request.args.get('page', default=1, type=int)

    # Set the number of transactions to show per page
    transactions_per_page = 20

    # Calculate the start and end index of transactions to show on the current page
    start_index = (page - 1) * transactions_per_page
    end_index = start_index + transactions_per_page

    # Get transactions for the current page
    current_transactions = list(transactions)[start_index:end_index]

    # Calculate the total number of pages
    total_pages = math.ceil(len(transactions) / transactions_per_page)

    return render_template('explorer.html',
                           transactions=reversed(current_transactions),
                           pending_transactions=reversed(pending_transactions),
                           page=page,
                           total_pages=total_pages)


@app.route('/api/viewtransactions', methods=['GET'])
def view_transactions_api():
    transactions = blockchain.get_all_transactions()
    # file deepcode ignore XSS: False positive
    return transactions


@app.route('/api/viewpendingtransactions', methods=['GET'])
def view_pending_transactions_api():
    pending_transactions = blockchain.get_pending_transactions()
    return pending_transactions


@app.route('/api/block/<int:index>', methods=['GET'])
def get_block_api(index):
    block = blockchain.get_block_by_index(index)
    if block is None:
        response = {'message': 'Block not found'}
        return jsonify(response), 404
    return jsonify(block), 200


@app.route('/block/<int:index>', methods=['GET'])
def get_block_page(index):
    block = blockchain.get_block_by_index(index)
    if block is None:
        response = {'message': 'Block not found'}
        return jsonify(response), 404

    return render_template('block.html', block=block), 200


@app.route('/transaction/<string:transaction_id>', methods=['GET'])
def view_transaction_page(transaction_id):
    transaction = blockchain.get_transaction_by_id(transaction_id)
    if transaction is None:
        response = {'message': 'Transaction not found'}
        return jsonify(response), 404
    return render_template('transaction.html', transaction=transaction)


@app.route('/api/transaction/<string:transaction_id>', methods=['GET'])
def view_transaction_api(transaction_id):
    transaction = blockchain.get_transaction_by_id(transaction_id)
    return jsonify(transaction), 200


@app.route('/webminer')
def webminer_page():
    return render_template("webminer.html")


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == settings['ADMIN_USER'] and password == settings['ADMIN_PASSWORD']:
            user = AdminUser(username)
            login_user(user)
            return redirect(url_for('admin_page'))

        return render_template('admin-login.html', error='Invalid username or password')

    return render_template('admin-login.html')


@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin_page'))


@app.route('/admin')
@login_required
def admin_page():
    with open('blockchain.json') as f:
        blockchain_data_json = json.load(f)

    blockchain_data = json.dumps(blockchain_data_json, indent=4)

    return render_template('admin.html', blockchain_data=blockchain_data)


websocket.on_namespace(Namespace('/webminer'))


@websocket.on("webminer_event", '/webminer')
def websocket_webminer_message_handler(message):
    if message == "get_last_block":
        last_block = blockchain.get_last_block()
        last_block_dumped = json.dumps(last_block)
        websocket.emit('last_block', last_block_dumped, namespace='/webminer')

    elif message == "get_difficulty":
        websocket.emit('difficulty', str(blockchain.difficulty), namespace='/webminer')

    elif message == "get_pending_transactions":
        pending_transactions = blockchain.get_pending_transactions()
        pending_transactions_dumped = json.dumps(pending_transactions)
        websocket.emit('pending_transactions', pending_transactions_dumped, namespace='/webminer')


@websocket.on('hashed', '/webminer')
def websocket_webminer_mined(message):
    recipient = message.split(":")[0]
    block_hash = message.split(":")[1]
    if block_hash.startswith("000"):
        blockchain.new_block(proof=(blockchain.proof_of_work() + 1), recieved_hash=block_hash)
        blockchain.new_transaction(sender="MinerNetwork", recipient=recipient, amount=BLOCK_MINED_DEFAULT_REWARD_AMOUNT)
        websocket.emit('added_to_chain', "Block added to the blockchain.", namespace='/webminer')
    else:
        websocket.emit('hash_invalid', "Hash not meeting requirements!", namespace='/webminer')


class TcpServer:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((SOCKET_BIND_IP, SOCKET_BIND_PORT))
        self.server_socket.listen()
        print(f"TCP socket listening on {SOCKET_BIND_IP}:{str(SOCKET_BIND_PORT)}")

    def handle_client(self, client_socket, address):
        # Handle client connection here
        print(f"New client connected: {address}")
        recipient = "MinerNetwork"

        while True:
            try:
                data = client_socket.recv(1024)
            except Exception:
                break
            if not data:
                break

            decoded_data = data.decode()

            if decoded_data == "exit":
                break

            if decoded_data == "get_difficulty":
                client_socket.send(str(blockchain.difficulty).encode())

            if decoded_data.startswith("recipient:"):
                recipient = decoded_data.replace("recipient:", "").strip()

            if decoded_data == "get_pending_transactions":
                pending_transactions = blockchain.get_pending_transactions()
                pending_transactions_data = json.dumps(pending_transactions)
                client_socket.send(pending_transactions_data.encode())

            if decoded_data == "get_last_block":
                last_block = blockchain.get_last_block()
                last_block_dumped = json.dumps(last_block)
                client_socket.send(last_block_dumped.encode())

            if decoded_data.startswith("mine:"):
                block_hash = decoded_data.split(":")[1]
                if block_hash.startswith("000"):
                    blockchain.new_block(proof=(blockchain.proof_of_work() + 1), recieved_hash=block_hash)
                    blockchain.new_transaction(sender="MinerNetwork", recipient=recipient,
                                               amount=BLOCK_MINED_DEFAULT_REWARD_AMOUNT)
                    client_socket.send("Block added to the blockchain.".encode())
                else:
                    client_socket.send("Hash not meeting requirements!".encode())

        print(f"Client disconnected")
        client_socket.close()

    def start(self):
        while True:
            client_socket, address = self.server_socket.accept()
            # Start a new thread to handle the client connection
            client_thread = threading.Thread(target=self.handle_client, args=(client_socket, address))
            client_thread.name = f"TCP-{str(address[0])}:{str(address[1])}"
            client_thread.start()


if __name__ == '__main__':
    # Create a TCP server object
    tcp_server = TcpServer()

    # Start the TCP server in a new thread
    tcp_server_thread = threading.Thread(target=tcp_server.start)
    tcp_server_thread.name = "TCP_Server"
    tcp_server_thread.daemon = True
    tcp_server_thread.start()
    # Start the Flask app
    websocket.run(app, '0.0.0.0', 5000)
