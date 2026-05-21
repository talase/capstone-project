from functools import lru_cache
from pathlib import Path

import torch
from fastapi import APIRouter
from peft import PeftConfig, PeftModel
from pydantic import BaseModel, Field
from transformers import AutoModelForSequenceClassification, AutoTokenizer

router = APIRouter(prefix="/model-pred", tags=["model-pred"])

MODEL_DIR = Path(__file__).resolve().parent / "model_weights"


class ClassifyMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ClassifyMessageResponse(BaseModel):
    message: str
    predicted_label: str
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
            torch_dtype=torch.bfloat16,
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
        
        # Define emotion labels
        self.emotion_labels = ['agreement_confirmation', 'book_or_reschedule_meeting', 'emergency_response', 'money_request', 'request_sending_non_sensitive_file', 'request_sending_sensitive_file', 'request_to_send_message_to_someone_else']

    def predict_emotion_from_text(self, text):
        """
        Predict emotion from input text
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


@lru_cache(maxsize=1)
def get_detector() -> TextEmotionDetector:
    return TextEmotionDetector()


@router.post("/classify", response_model=ClassifyMessageResponse)
def classify_message(payload: ClassifyMessageRequest) -> ClassifyMessageResponse:
    detector = get_detector()
    categories, probabilities = detector.predict_emotion_from_text(payload.message)
    probs = probabilities[0].float().tolist()
    probability_by_label = dict(zip(categories, probs))
    predicted_label, confidence = max(
        probability_by_label.items(),
        key=lambda item: item[1],
    )

    return ClassifyMessageResponse(
        message=payload.message,
        predicted_label=predicted_label,
        confidence=confidence,
        probabilities=probability_by_label,
    )
