var socket = io();
let selectedUser = null;
let currentUserId = null;

// Get current user ID from body
if (document.body) {
    currentUserId = parseInt(document.body.getAttribute('data-user-id'));
}

function selectUser(id, username) {
    selectedUser = id;
    document.getElementById("chat-header").innerHTML = `<i class="fas fa-user"></i> ${username}`;
    document.getElementById("chat-box").innerHTML = "";
    
    // Load messages
    fetch('/get_messages/' + id)
        .then(response => response.json())
        .then(messages => {
            if (messages.error) return;
            messages.forEach(msg => {
                let type = msg.sender_id == currentUserId ? "sent" : "received";
                let time = new Date(msg.timestamp).toLocaleTimeString();
                addMessage(msg.text, type, time);
            });
        });
}

function sendMsg() {
    let msg = document.getElementById("msg").value.trim();
    if (!msg || !selectedUser) return;
    
    socket.emit("send_message", {
        receiver: selectedUser,
        message: msg
    });
    
    addMessage(msg, "sent", "Sending...");
    document.getElementById("msg").value = "";
}

socket.on("receive_message", function(data) {
    let time = new Date(data.timestamp).toLocaleTimeString();
    addMessage(data.message, "received", time);
});

socket.on("message_sent", function(data) {
    let messages = document.querySelectorAll('.message.sent');
    let lastMsg = messages[messages.length - 1];
    if (lastMsg) {
        let timeDiv = lastMsg.querySelector('.message-time');
        if (timeDiv) {
            let newTime = new Date(data.timestamp).toLocaleTimeString();
            timeDiv.innerHTML = newTime;
        }
    }
});

function addMessage(msg, type, time) {
    let box = document.getElementById("chat-box");
    let div = document.createElement("div");
    div.classList.add("message", type);
    div.innerHTML = `
        <div>${escapeHtml(msg)}</div>
        <div class="message-time" style="font-size:11px; margin-top:5px; text-align:right; opacity:0.7;">${time}</div>
    `;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function escapeHtml(text) {
    let div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Enter key to send
document.addEventListener('DOMContentLoaded', function() {
    let input = document.getElementById("msg");
    if (input) {
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') sendMsg();
        });
    }
});
