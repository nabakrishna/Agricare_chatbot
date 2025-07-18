
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
from dotenv import load_dotenv
import requests
import json
import re
import logging

app = Flask(__name__)
CORS(app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load OpenRouter API key
load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")

# --- Database Setup ---

def load_diseases_data():
    """Loads the initial plant diseases dataset from a local JSON file."""
    try:
        with open('plant_diseases_data.json', 'r') as file:
            data = json.load(file)
        return data.get('diseases', [])
    except FileNotFoundError:
        logger.warning("plant_diseases_data.json not found. The database will be empty.")
        return []
    except json.JSONDecodeError:
        logger.warning("Could not decode plant_diseases_data.json. The database will be empty.")
        return []

def init_db():
    """Initializes the SQLite database and populates it with data if it's empty."""
    conn = sqlite3.connect('plant_diseases.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diseases (
            id INTEGER PRIMARY KEY,
            symptom TEXT UNIQUE,
            disease TEXT,
            organic_treatment TEXT,
            chemical_treatment TEXT,
            prevention TEXT
        )
    """)
    
    cursor.execute("SELECT COUNT(id) FROM diseases")
    count = cursor.fetchone()[0]
    
    if count == 0:
        diseases = load_diseases_data()
        if diseases:
            cursor.executemany("""
                INSERT OR IGNORE INTO diseases (symptom, disease, organic_treatment, chemical_treatment, prevention) 
                VALUES (?, ?, ?, ?, ?)
            """, [(d['symptom'], d['disease'], d['organic_treatment'], d['chemical_treatment'], d['prevention']) for d in diseases])
            logger.info(f"Database initialized with {len(diseases)} records.")
    
    conn.commit()
    conn.close()

# --- AI and Logic Functions ---

def classify_input(text: str):
    """
    Uses an AI model to classify the user's input to understand their intent.
    """
    if not API_KEY:
        logger.error("No OPENROUTER_API_KEY found in .env")
        return "error"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Refined prompt to improve category distinction
    prompt = f"""
    You are an assistant that categorizes user input for a plant care chatbot. Analyze the input and classify it into EXACTLY ONE category based on the examples provided. Be precise and avoid overlapping categories.

    Categories and examples:
    - "greeting": Inputs like "hi", "hello", "helooe", "hey"
    - "morning": Inputs like "good morning", "morning", "good mrng"
    - "afternoon": Inputs like "good afternoon", "afternoon", "good aftn"
    - "evening": Inputs like "good evening", "evening", "good evng"
    - "night": Inputs like "good night", "night", "good nite"
    - "farewell": Inputs like "bye", "by", "see you", "goodbye", "goodby"
    - "thanks": Inputs like "thank you", "thanki you", "thnx", "thanx", "thanks"
    - "okay": Inputs like "ok", "okay", "k", "alright"
    - "casual_question": Inputs like "how are you?", "what's up?", "how's it going?"
    - "plant_symptom": Inputs clearly describing a plant's condition, like "yellow spots on leaves", "white powdery substance", "brown spots"
    - "unrelated": Any other input, including nonsense like "hhh", off-topic questions like "how's the weather", or unrecognizable text

    User Input: "{text}"

    Return ONLY a JSON object with the key "category" and the category name. Example: {{"category": "greeting"}}
    """
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": "mistralai/mistral-7b-instruct",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }
        )
        response.raise_for_status()
        classification_json = response.json()["choices"][0]["message"]["content"]
        category = json.loads(classification_json).get("category", "unrelated")
        logger.debug(f"Input: '{text}' -> Classified as: {category}")
        return category
    except requests.exceptions.RequestException as e:
        logger.error(f"Error classifying input '{text}': {e}")
        return "error"
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error parsing classification response for '{text}': {e}")
        return "unrelated"

def correct_spelling(text: str) -> str:
    """Uses a focused AI prompt to correct spelling specifically for plant-related terms."""
    if not API_KEY:
        logger.error("No OPENROUTER_API_KEY found in .env")
        return text

    headers = { "Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json" }
    prompt = f"""You are a plant pathology expert. Review the following user-described symptom for spelling and terminology errors related to plants, pests, and diseases. Correct ONLY these specific errors. If there are no errors or the text is not plant-related, return the original text.

Original text: "{text}"

Return JUST the corrected text, with no extra explanation."""
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": "mistralai/mistral-7b-instruct",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1
            }
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error correcting spelling for '{text}': {e}")
        return text

# --- Flask API Endpoint ---

@app.route('/api/analyze-symptoms', methods=['POST'])
def analyze_symptoms():
    """
    Main endpoint to analyze user input, classify it, and provide a diagnosis or appropriate response.
    """
    try:
        data = request.get_json()
        symptoms = data.get('symptoms', '').strip()
        logger.debug(f"Received input: '{symptoms}'")
        
        if not symptoms:
            return jsonify({"error": "Please describe plant symptoms"}), 400
        
        classification = classify_input(symptoms)
        
        casual_responses = {
            "greeting": "Hello! I'm here to help with plant disease diagnosis. Please describe any symptoms you're observing.",
            "morning": "Good morning! How can I assist you with your plant health today?",
            "afternoon": "Good afternoon! What plant health issues can I help you with?",
            "evening": "Good evening! I'm ready to assist with any plant disease questions you have.",
            "night": "Good night! If you have any plant health concerns, feel free to ask.",
            "casual_question": "I'm just a bot, but I'm ready to help with plant health issues! What symptoms are you seeing?",
            "thanks": "You're welcome! Let me know if you have any other plant health concerns.",
            "farewell": "Goodbye! Feel free to ask if you have more questions about plant diseases later.",
            "okay": "Got it! Please describe any plant symptoms you’re observing to continue."
        }
        
        if classification in casual_responses:
            logger.debug(f"Returning casual response for category: {classification}")
            return jsonify({"message": casual_responses[classification], "is_casual": True})

        if classification == "unrelated":
            logger.debug("Input classified as unrelated")
            return jsonify({
                "message": "I couldn't understand your input. Please provide valid plant symptoms, such as 'yellow spots on leaves' or 'white powdery substance'.",
                "is_casual": False
            })

        if classification == "error":
            logger.error("Classification error occurred")
            return jsonify({"error": "Could not process the request due to an internal error."}), 500

        # --- From here, we assume the input is a plant_symptom ---
        
        corrected_symptoms = correct_spelling(symptoms.lower())
        logger.debug(f"Corrected symptoms: '{corrected_symptoms}'")
        
        words = re.findall(r'\b\w+\b', corrected_symptoms)
        
        if not words:
            logger.debug("No valid words found in input")
            return jsonify({ "message": "Please provide more details about the symptoms.", "is_casual": False })

        conn = sqlite3.connect('plant_diseases.db')
        
        def regexp(expr, item):
            return re.search(expr, item, re.IGNORECASE) is not None
        conn.create_function("REGEXP", 2, regexp)
        
        cursor = conn.cursor()
        
        query_conditions = " AND ".join(["symptom REGEXP ?" for _ in words])
        query_params = [fr"\b{word}\b" for word in words]
        
        cursor.execute(f"SELECT disease, organic_treatment, chemical_treatment, prevention FROM diseases WHERE {query_conditions}", query_params)
        result = cursor.fetchone()
        conn.close()
        
        if result:
            logger.debug(f"Database match found: {result[0]}")
            return jsonify({
                "source": "database", "disease": result[0], "organic": result[1],
                "chemical": result[2], "prevention": result[3], "is_casual": False
            })
        
        # Step 4: If no DB match, consult the AI for a full diagnosis
        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        prompt = f"""Act as a plant pathologist. A user has described the following symptoms:
"{symptoms}"

Based on these symptoms, provide a likely diagnosis and treatment plan.
Return your response as a JSON object with the following keys: "disease", "organic", "chemical", "prevention".
If the symptoms are too vague to make a diagnosis, set the "disease" value to "Unknown" and explain in the "prevention" key that more details are needed.
"""
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json={
                "model": "mistralai/mistral-7b-instruct",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.3
            }
        )
        response.raise_for_status()
        
        ai_response_content = response.json()["choices"][0]["message"]["content"]
        ai_diagnosis = json.loads(ai_response_content)
        logger.debug(f"AI diagnosis: {ai_diagnosis}")
        
        return jsonify({"source": "ai", **ai_diagnosis, "is_casual": False})
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API Request Error: {e}")
        return jsonify({"error": "An error occurred while communicating with the AI service."}), 502
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

# --- Main Execution ---
if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
