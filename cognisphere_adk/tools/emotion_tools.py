# cognisphere_adk/tools/emotion_tools.py

from google.adk.tools.tool_context import ToolContext


def analyze_emotion(text: str, tool_context: ToolContext = None) -> dict:
    """
    Analyzes the emotional content of text.

    Args:
        text: The text to analyze
        tool_context: Tool context for accessing session state

    Returns:
        dict: Emotional analysis of the text
    """
    # This is a simplified implementation
    # In a full system, you would connect to a real emotion classifier

    # List of emotions to check for
    emotions = {
        "joy": ["happy", "delighted", "excited", "pleased", "glad"],
        "sadness": ["sad", "unhappy", "disappointed", "depressed", "upset"],
        "anger": ["angry", "furious", "irritated", "annoyed", "mad"],
        "fear": ["afraid", "scared", "frightened", "anxious", "worried"],
        "surprise": ["surprised", "amazed", "astonished", "shocked", "stunned"],
        "curiosity": ["curious", "interested", "intrigued", "wondering", "fascinated"]
    }

    # Simple word-based detection
    text_lower = text.lower()
    detected_emotions = {}

    for emotion, keywords in emotions.items():
        score = 0
        for keyword in keywords:
            if keyword in text_lower:
                score += 0.2  # Simple scoring

        if score > 0:
            detected_emotions[emotion] = min(score, 1.0)

    # Determine primary emotion
    if detected_emotions:
        primary_emotion = max(detected_emotions.items(), key=lambda x: x[1])
        emotion_type, emotion_score = primary_emotion
    else:
        emotion_type, emotion_score = "neutral", 0.5

    # Calculate valence (positive/negative)
    positive_emotions = ["joy", "curiosity", "surprise"]
    negative_emotions = ["sadness", "anger", "fear"]

    if emotion_type in positive_emotions:
        valence = 0.5 + (emotion_score / 2)
    elif emotion_type in negative_emotions:
        valence = 0.5 - (emotion_score / 2)
    else:
        valence = 0.5

    # Calculate arousal (intensity)
    high_arousal = ["anger", "fear", "surprise", "joy"]
    low_arousal = ["sadness"]

    if emotion_type in high_arousal:
        arousal = 0.5 + (emotion_score / 2)
    elif emotion_type in low_arousal:
        arousal = 0.5 - (emotion_score / 2)
    else:
        arousal = 0.5

    return {
        "emotion_type": emotion_type,
        "score": emotion_score,
        "valence": valence,
        "arousal": arousal,
        "detected_emotions": detected_emotions
    }