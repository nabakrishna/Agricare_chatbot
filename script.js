// DOM Elements
const chatbox = document.getElementById('chatbox');
const userInput = document.getElementById('user-input');
const imageUpload = document.getElementById('image-upload');

// Add message to chat
function addMessage(content, isUser = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = content;
    
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = getCurrentTime();
    
    messageDiv.appendChild(contentDiv);
    messageDiv.appendChild(timeDiv);
    chatbox.appendChild(messageDiv);
    
    // Scroll to bottom
    chatbox.scrollTop = chatbox.scrollHeight;
}

// Format diagnosis response for display
function formatDiagnosisResponse(response) {
    // Handle casual responses
    if (response.is_casual) {
        return response.message || "I'm here to help with plant health! Please describe your plant's symptoms.";
    }
    
    // Handle errors
    if (response.error) {
        return `Error: ${response.error}`;
    }
    
    // Handle invalid or incomplete diagnosis (e.g., undefined values)
    if (!response.disease || response.disease === "Unknown" || !response.organic || !response.chemical || !response.prevention) {
        return response.message || "I couldn't understand your input. Please provide valid plant symptoms, such as 'yellow spots on leaves' or 'white powdery substance'.";
    }
    
    // Format valid diagnosis
    return `
        <strong>Diagnosis: ${response.disease}</strong><br>
        <strong>Organic Treatment:</strong> ${response.organic}<br>
        <strong>Chemical Treatment:</strong> ${response.chemical}<br>
        <strong>Prevention:</strong> ${response.prevention}<br>
        <small>(Source: ${response.source})</small>
    `;
}

// Get current time in HH:MM format
function getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Show typing indicator
function showTyping() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content typing-indicator';
    contentDiv.innerHTML = `
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
    `;
    
    typingDiv.appendChild(contentDiv);
    chatbox.appendChild(typingDiv);
    chatbox.scrollTop = chatbox.scrollHeight;
    
    return typingDiv;
}

// Handle text input
async function handleSubmit() {
    const text = userInput.value.trim();
    if (!text) return;
    
    // Add user message
    addMessage(text, true);
    userInput.value = '';
    
    // Show typing indicator
    const typingElement = showTyping();
    
    try {
        // Make API call to Flask backend
        const response = await fetch('http://localhost:5000/api/analyze-symptoms', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ symptoms: text }),
        });
        
        const data = await response.json();
        console.log("API Response:", data); // Debug: Log the API response
        
        // Remove typing indicator
        chatbox.removeChild(typingElement);
        
        // Handle the response
        if (!response.ok) {
            throw new Error(data.error || 'Failed to process the request.');
        }
        
        // Format and display the response
        const messageContent = formatDiagnosisResponse(data);
        addMessage(messageContent);
    } catch (error) {
        console.error("API Error:", error); // Debug: Log any errors
        chatbox.removeChild(typingElement);
        addMessage("Sorry, I'm having trouble connecting. Please try again later.");
    }
}

// Handle image upload
function handleImageUpload() {
    const file = imageUpload.files[0];
    if (!file) {
        alert('Please select an image first');
        return;
    }
    
    // Add user message
    addMessage(`<i class="fas fa-image"></i> Image uploaded: ${file.name}`, true);
    
    // Show typing indicator
    const typingElement = showTyping();
    
    // Simulate image analysis
    setTimeout(() => {
        chatbox.removeChild(typingElement);
        addMessage("Image analysis is not yet supported by the backend. Please describe symptoms in text for now.");
    }, 1500);
}

// Event listeners
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleSubmit();
});
