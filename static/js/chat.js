document.addEventListener('DOMContentLoaded', () => {
    const newChatButton = document.getElementById('new-chat-btn');
    const chatList = document.getElementById('chat-list');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-btn');
    const chatWindow = document.querySelector('.chat-window');

    function escapeHtml(unsafe) {
        const div = document.createElement('div');
        div.textContent = unsafe;
        return div.innerHTML;
    }

    function scrollToBottom() {
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    function loadChat(chatId) {
        if (!chatId) {
            chatWindow.innerHTML = "<p>Please select a chat to view the conversation.</p>";
            return;
        }

        fetch(`/get_chat/${chatId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.chat_history) {
                    const lines = data.chat_history.split('\n');
                    chatWindow.innerHTML = lines.map(line => {
                        if (line.startsWith('User:')) {
                            return `<div class="user-message">${escapeHtml(line.replace('User: ', ''))}</div>`;
                        } else if (line.startsWith('Bot:')) {
                            return `<div class="bot-response">${escapeHtml(line.replace('Bot: ', ''))}</div>`;
                        }
                        return '';
                    }).join('');
                } else {
                    chatWindow.innerHTML = "<p>No conversation history yet.</p>";
                }
                scrollToBottom();
            })
            .catch(err => {
                console.error('Error loading chat:', err);
                chatWindow.innerHTML = "<p>Failed to load chat. Please try again later.</p>";
            });
    }

    chatList.addEventListener('click', event => {
        if (event.target.tagName === 'LI' || event.target.tagName === 'SPAN') {
            const listItem = event.target.closest('li');
            document.querySelectorAll('.selected-chat').forEach(item => item.classList.remove('selected-chat'));
            listItem.classList.add('selected-chat');
            const chatId = listItem.dataset.chatId;
            loadChat(chatId);
        }
    });

    newChatButton.addEventListener('click', () => {
        const chatName = prompt("Enter a name for the new chat:");
        if (chatName) {
            fetch('/new_chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chat_name: chatName })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert("Failed to create a new chat. Please try again.");
                }
            });
        }
    });

    sendButton.addEventListener('click', () => {
        const message = userInput.value.trim();
        const selectedChat = document.querySelector('.selected-chat');
        const chatId = selectedChat ? selectedChat.dataset.chatId : null;

        if (!chatId) {
            alert("Please select a chat.");
            return;
        }

        if (!message) {
            alert("Message cannot be empty.");
            return;
        }

        fetch('/send_message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chat_id: chatId, message })
        })
        .then(response => response.json())
        .then(data => {
            if (data.bot_response) {
                chatWindow.innerHTML += `
                    <div class="user-message">${escapeHtml(message)}</div>
                    <div class="bot-response">${escapeHtml(data.bot_response)}</div>`;
                userInput.value = '';
                scrollToBottom();
            } else {
                alert("Error: Bot response not received.");
            }
        })
        .catch(err => {
            console.error('Error:', err);
            alert("Failed to send the message. Please try again.");
        });
    });

    chatList.addEventListener('click', event => {
        if (event.target.classList.contains('delete-chat-btn')) {
            const chatId = event.target.dataset.chatId;
            if (confirm("Are you sure you want to delete this chat?")) {
                fetch(`/delete_chat/${chatId}`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        location.reload();
                    } else {
                        alert("Failed to delete chat. Please try again.");
                    }
                })
                .catch(err => {
                    console.error('Error:', err);
                    alert("Failed to delete chat. Please try again.");
                });
            }
        }
    });

    userInput.addEventListener('keypress', event => {
        if (event.key === 'Enter') {
            sendButton.click();
            event.preventDefault();
        }
    });
});
