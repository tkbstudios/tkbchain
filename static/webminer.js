var socket = io('http://localhost:5000/webminer');

const startButton = document.getElementById('startButton');
const stopButton = document.getElementById('stopButton');
const output = document.getElementById('output');
const exportButton = document.getElementById('exportButton');
const usernameInput = document.getElementById('username');
const attemptsPerSecondLabel = document.getElementById('attemptsPerSecond');
const threadsInput = document.getElementById('threadsInput');

mining = false;
difficulty = 1;
pending_transactions = {};
last_block = {};
username = "";

elapsedTime = 0.00;
attemptsPerSecond = 0.00;


function addOutput(newOutput){
    output.innerHTML += newOutput + "<br>";
    output.scrollTop = output.scrollHeight;
}


function mined(mined_hash){
    socket.emit("hashed", `${username}:${mined_hash}`);
}

function mine(){
    if (mining == false){return}
    let nonce = 0;
    let attempts = 0;
    let startTime = Date.now();
    function mineBlock() {
        let block_attempt = {
            index: last_block.index + 1,
            transactions: pending_transactions,
            previous_hash: last_block.hash,
            difficulty: difficulty,
            timestamp: Date.now(),
            proof: last_block.proof
        }.toString() + nonce.toString()
        let block_hash = CryptoJS.SHA256(JSON.stringify(block_attempt)).toString();
        attempts++;
        if (block_hash.startsWith("000")) {
            addOutput("Successfully mined block with nonce " + nonce + "! Hash: " + block_hash);
            mined(block_hash);
        }
        nonce++;
        if (mining) {
            setTimeout(mineBlock, 5);
        } else {
            elapsedTime = (Date.now() - startTime) / 1000;
            attemptsPerSecond = attempts / elapsedTime;
            attempts = 0;
            startTime = Date.now();
        }
        attemptsPerSecondLabel.innerText = attemptsPerSecond.toFixed(2);
    }    
    mineBlock();
}

socket.on('connect', function(){
    addOutput("Connected to socket!");
})

socket.on('last_block', function(message){
    addOutput("Got bock to mine!");
    last_block = JSON.parse(message);
    socket.emit('webminer_event', 'get_pending_transactions');
})

socket.on('difficulty', function(message){
    difficulty = parseInt(message);
    addOutput("difficulty: " + message);
    socket.emit('webminer_event', 'get_last_block');
})

socket.on('pending_transactions', function(message){
    addOutput("Pending transactions: " + JSON.parse(message).length);
    pending_transactions = JSON.parse(message);
    addOutput("Starting to mine...");
    mine();
})

socket.on('added_to_chain', function(message){
    addOutput(message);
})

socket.on('hash_invalid', function(message){
    addOutput(message);
})

startButton.addEventListener('click', function(){
    mining = true;
    username = usernameInput.value;
    console.log(username)
    output.innerHTML = "";
    startButton.style.backgroundColor = "green";
    startButton.disabled = true;
    stopButton.disabled = false;
    usernameInput.disabled = true;
    socket.emit('webminer_event', 'get_difficulty');
});

stopButton.addEventListener('click', function(){
    mining = false;
    startButton.style.backgroundColor = "";
    stopButton.style.backgroundColor = "red";
    stopButton.disabled = true;
    usernameInput.disabled = false;
    socket.emit('webminer_event', 'stop');
    setTimeout(function() {
        stopButton.style.backgroundColor = "";
        startButton.disabled = false;
    }, 2000);
})

exportButton.addEventListener('click', function(){
    var outputContent = output.innerText;
    var element = document.createElement('a');
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(outputContent));
    element.setAttribute('download', 'output.txt');
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
})
