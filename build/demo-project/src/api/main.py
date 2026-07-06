"""payments-api: create and confirm payment intents."""
from fastapi import FastAPI

app = FastAPI(title="payments-api")


@app.post("/v1/payment-intents")
def create_intent(amount_cents: int, currency: str = "EUR"):
    return {"status": "requires_confirmation", "amount": amount_cents}


@app.get("/healthz")
def health():
    return {"ok": True}
