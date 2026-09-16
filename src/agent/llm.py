from transformers import AutoTokenizer, AutoModelForCausalLM
import torch


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"

# CPU-only setup
DEVICE = "cpu"


# ============================================================
# LOAD TOKENIZER
# ============================================================

print("=" * 70)
print("LOADING HUGGING FACE MODEL")
print("=" * 70)

print(f"Model: {MODEL_NAME}")
print(f"Device: {DEVICE}")
print()

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME
)


# ============================================================
# LOAD MODEL
# ============================================================

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.float32
)

model.to(DEVICE)
model.eval()

print("✓ Tokenizer loaded")
print("✓ Model loaded")
print()


# ============================================================
# GENERATE RESPONSE
# ============================================================

def generate_response(
    user_message: str,
    max_new_tokens: int = 150
) -> str:

    messages = [
        {
            "role": "system",
            "content": (
                "You are an AI Business Analyst. "
                "Answer clearly and concisely. "
                "Do not invent business numbers."
            )
        },
        {
            "role": "user",
            "content": user_message
        }
    ]

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(
        prompt,
        return_tensors="pt"
    )

    inputs = {
        key: value.to(DEVICE)
        for key, value in inputs.items()
    }

    with torch.no_grad():

        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id
        )

    generated_tokens = outputs[0][inputs["input_ids"].shape[1]:]

    response = tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True
    )

    return response.strip()


# ============================================================
# SIMPLE TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("LOCAL HUGGING FACE LLM TEST")
    print("=" * 70)
    print()

    question = "Explain what ROAS means for an ecommerce business."

    print("User:")
    print(question)
    print()

    print("AI:")
    answer = generate_response(question)

    print(answer)
    print()

    print("=" * 70)
    print("LLM TEST COMPLETED")
    print("=" * 70)