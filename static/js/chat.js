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

    // ✅ Create proper timestamp
    let currentTime = new Date().toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });

    let data = {
        message: msg,
        receiver: selectedUser,
        time: currentTime
    };

    socket.emit("send_message", data);

    addMessage(msg, "sent", currentTime);

    document.getElementById("msg").value = "";
}

socket.on("receive_message", function(data) {
    addMessage(data.message, "received", data.time);
});

function addMessage(msg, type, time) {
    let box = document.getElementById("chat-box");

    let div = document.createElement("div");
    div.classList.add("message", type);

    div.innerHTML = `
        <div>${msg}</div>
        <div style="
            font-size:11px;
            margin-top:5px;
            text-align:right;
            opacity:0.7;
        ">
            ${time}
        </div>
    `;

    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}
