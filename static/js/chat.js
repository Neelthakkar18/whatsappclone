var socket = io();
let selectedUser = null;

function selectUser(id, username) {
    selectedUser = id;
    document.getElementById("chat-header").innerText = username;
    document.getElementById("chat-box").innerHTML = "";
    // Load previous messages when selecting user
    loadMessages(id);
}

function loadMessages(userId) {
    fetch('/get_messages/' + userId)
        .then(response => response.json())
        .then(messages => {
            let box = document.getElementById("chat-box");
            box.innerHTML = "";
            messages.forEach(msg => {
                let type = msg.sender_id == currentUserId ? "sent" : "received";
                addMessage(msg.text, type, msg.timestamp);
            });
        });
}

function sendMsg() {
    let msg = document.getElementById("msg").value;

    if (!msg || !selectedUser) return;

    // ✅ Send message WITHOUT timestamp - let backend create it
    let data = {
        message: msg,
        receiver: selectedUser
    };

    socket.emit("send_message", data);

    // Show message instantly with "Sending..." status
    addMessage(msg, "sent", "Sending...");

    document.getElementById("msg").value = "";
}

socket.on("receive_message", function(data) {
    // ✅ Use timestamp from backend
    let displayTime = formatTimestamp(data.timestamp);
    addMessage(data.message, "received", displayTime);
});

// ✅ Listen for message sent confirmation with timestamp
socket.on("message_sent", function(data) {
    // Update the last message with correct timestamp
    let messages = document.querySelectorAll('.message.sent');
    let lastMsg = messages[messages.length - 1];
    if (lastMsg) {
        let timeDiv = lastMsg.querySelector('.message-time');
        if (timeDiv) {
            timeDiv.innerText = formatTimestamp(data.timestamp);
        }
    }
});

function addMessage(msg, type, time) {
    let box = document.getElementById("chat-box");

    let div = document.createElement("div");
    div.classList.add("message", type);

    div.innerHTML = `
        <div>${escapeHtml(msg)}</div>
        <div class="message-time" style="
            font-size:10px;
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

// ✅ Helper function to format timestamp from backend
function formatTimestamp(timestamp) {
    if (!timestamp) return "Just now";
    let date = new Date(timestamp);
    return date.toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
}

function escapeHtml(text) {
    let div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
