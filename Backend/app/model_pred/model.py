from functools import lru_cache
import logging
from pathlib import Path
import threading
import time

# Suppress verbose warnings from transformers library
logging.getLogger("transformers").setLevel(logging.ERROR)

import torch
from fastapi import APIRouter, HTTPException
from peft import PeftConfig, PeftModel
from pydantic import BaseModel, Field
from transformers import AutoModelForSequenceClassification, AutoTokenizer

router = APIRouter(prefix="/model-pred", tags=["model-pred"])

MODEL_DIR = Path(__file__).resolve().parent / "model_weights_6"
PREDICTION_THRESHOLD = 0.80


class ClassifyMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ClassifyMessageResponse(BaseModel):
    message: str
    predicted_labels: list[str]
    confidence: float
    probabilities: dict[str, float]


class TextEmotionDetector:
    def __init__(self, model_path=MODEL_DIR):
        # Initialize tokenizer and model
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_path))

        
        # Load PEFT config first
        peft_config = PeftConfig.from_pretrained(str(model_path))

        # Load the base model WITHOUT quantization or device_map for now
        base_model = AutoModelForSequenceClassification.from_pretrained(
            peft_config.base_model_name_or_path,
            problem_type="multi_label_classification",
            dtype=torch.bfloat16,
            num_labels=7,
        )

        # Replace the base model's score layer with a new one that has the correct number of labels
        base_model.score = torch.nn.Linear(
            base_model.score.in_features,
            7,
            bias=False
        ).to(dtype=torch.bfloat16)

        # Load the adapter on top of the base model
        self.model = PeftModel.from_pretrained(base_model, str(model_path)).to(dtype=torch.bfloat16)
        self.model.eval()
        
        # Define labels
        self.emotion_labels = ['agreement_confirmation', 'book_or_reschedule_meeting', 'emergency_response', 'money_request', 'request_sending_non_sensitive_file', 'request_sending_sensitive_file', 'request_to_send_message_to_someone_else']

    def predict_action_from_text(self, text):
        """
        Predict action from input text
        Args:
            text (str): Input text to analyze
        Returns:
            tuple: (predicted_emotion, confidence_score)
        """
        # Tokenize input text
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=128)
        
        # Get prediction
        with torch.no_grad():
            outputs = self.model(**inputs)
            predictions = outputs.logits
            

        probabilities = torch.sigmoid(predictions)
        
        return self.emotion_labels, probabilities


# Thread-safe global variables for async loading
_detector: TextEmotionDetector | None = None
_is_loading = False
_lock = threading.Lock()

def load_detector_in_background():
    global _detector, _is_loading
    with _lock:
        if _detector is not None or _is_loading:
            return
        _is_loading = True
    
    def _load():
        global _detector, _is_loading
        try:
            print("Warming up/loading the text action detector model in the background...")
            loaded_detector = TextEmotionDetector()
            with _lock:
                _detector = loaded_detector
            print("Model loaded successfully and API is ready!")
        except Exception as e:
            print(f"Error loading model: {e}")
        finally:
            with _lock:
                _is_loading = False

    thread = threading.Thread(target=_load, daemon=True)
    thread.start()


def get_detector() -> TextEmotionDetector:
    global _detector
    if _detector is None:
        # Load synchronously if requested outside of routes
        _detector = TextEmotionDetector()
    return _detector


@router.post("/classify", response_model=ClassifyMessageResponse)
def classify_message(payload: ClassifyMessageRequest) -> ClassifyMessageResponse:
    global _detector, _is_loading
    
    # If not loaded and not currently loading, trigger background load
    if _detector is None and not _is_loading:
        load_detector_in_background()
        
    # Wait for up to 30 seconds if the model is currently loading
    start_time = time.time()
    while _detector is None and _is_loading:
        if time.time() - start_time > 30:
            raise HTTPException(
                status_code=503,
                detail="Model is still loading, please try again shortly."
            )
        time.sleep(0.5)
        
    if _detector is None:
        raise HTTPException(
            status_code=503,
            detail="Model is not ready. Please verify server status/logs."
        )
        
    categories, probabilities = _detector.predict_action_from_text(payload.message)
    probs = probabilities[0].float().tolist()
    probability_by_label = dict(zip(categories, probs))
    predicted_labels = [
        label
        for label, probability in probability_by_label.items()
        if probability > PREDICTION_THRESHOLD
    ]
    confidence = max(probability_by_label.values()) if probability_by_label else 0.0

    return ClassifyMessageResponse(
        message=payload.message,
        predicted_labels=predicted_labels,
        confidence=confidence,
        probabilities=probability_by_label,
    )


print("MODEL_DIR =", MODEL_DIR)
print("EXISTS =", MODEL_DIR.exists())

# Trigger async model load on startup so it runs in the background
load_detector_in_background()