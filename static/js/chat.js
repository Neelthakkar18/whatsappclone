var socket = io();
let selectedUser = null;

function selectUser(id, username) {
    selectedUser = id;
    document.getElementById("chat-header").innerText = username;
    document.getElementById("chat-box").innerHTML = "";
}

function sendMsg() {
    let msg = document.getElementById("msg").value;

    if (!msg || !selectedUser) return;

    socket.emit("send_message", {
        message: msg,
        receiver: selectedUser
    });

    addMessage(msg, "sent");
    document.getElementById("msg").value = "";
}

socket.on("receive_message", function(data) {
    addMessage(data.message, "received");
});

function addMessage(msg, type) {
    let box = document.getElementById("chat-box");

    let div = document.createElement("div");
    div.classList.add("message", type);
    div.innerText = msg;

    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}
