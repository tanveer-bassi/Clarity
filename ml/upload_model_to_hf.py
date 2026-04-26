from transformers import AutoTokenizer, AutoModelForSequenceClassification

LOCAL_MODEL_DIR = "./clearconsent-distilbert-v2"
HF_REPO_ID = "1Ghoul1/clearconsent-distilbert-v2"

tokenizer = AutoTokenizer.from_pretrained(LOCAL_MODEL_DIR)
model = AutoModelForSequenceClassification.from_pretrained(LOCAL_MODEL_DIR)

model.push_to_hub(HF_REPO_ID)
tokenizer.push_to_hub(HF_REPO_ID)

print(f"Uploaded model and tokenizer to https://huggingface.co/{HF_REPO_ID}")