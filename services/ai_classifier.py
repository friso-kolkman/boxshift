"""AI-powered transaction classifier using Claude API."""

import os
import json


def classify_transactions(transactions: list[dict]) -> list[dict]:
    """Classify a batch of transactions using Claude API.

    Each transaction dict should have: description, amount, quantity, price.
    Returns the same list with 'type' field added/updated.

    Falls back to rule-based classification if API is unavailable.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    if not api_key or api_key.startswith("sk-ant-..."):
        return _rule_based_classify(transactions)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # Batch transactions for efficiency
        tx_descriptions = []
        for i, tx in enumerate(transactions):
            tx_descriptions.append(
                f"{i}: desc=\"{tx.get('description', '')}\", "
                f"amount={tx.get('amount', 0)}, "
                f"qty={tx.get('quantity', '')}, "
                f"price={tx.get('price', '')}"
            )

        prompt = f"""Classify these broker transactions into types.
Valid types: buy, sell, dividend, interest, cost, deposit, withdrawal

Transactions:
{chr(10).join(tx_descriptions)}

Return JSON array with objects having "index" and "type" fields. Only return the JSON, nothing else."""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        result = json.loads(message.content[0].text)
        for item in result:
            idx = item["index"]
            if 0 <= idx < len(transactions):
                transactions[idx]["type"] = item["type"]

    except Exception:
        return _rule_based_classify(transactions)

    return transactions


def _rule_based_classify(transactions: list[dict]) -> list[dict]:
    """Simple rule-based fallback classifier."""
    for tx in transactions:
        desc = tx.get("description", "").lower()
        amount = tx.get("amount", 0)
        qty = tx.get("quantity")
        price = tx.get("price")

        if qty and price:
            if amount < 0:
                tx["type"] = "buy"
            else:
                tx["type"] = "sell"
        elif "dividend" in desc:
            tx["type"] = "dividend"
        elif "rente" in desc or "interest" in desc:
            tx["type"] = "interest"
        elif "kosten" in desc or "fee" in desc or "commission" in desc:
            tx["type"] = "cost"
        elif "storting" in desc or "deposit" in desc:
            tx["type"] = "deposit"
        elif "opname" in desc or "withdrawal" in desc:
            tx["type"] = "withdrawal"
        elif amount > 0:
            tx["type"] = "deposit"
        else:
            tx["type"] = "cost"

    return transactions
