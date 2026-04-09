"""In-memory per-user chat history (last 5 turns)."""

_store: dict[str, list] = {}


def get_memory(user_id: str) -> list:
    return _store.get(user_id, [])


def update_memory(user_id: str, query: str, answer: str) -> None:
    if user_id not in _store:
        _store[user_id] = []
    _store[user_id].append({"query": query, "answer": answer})
    _store[user_id] = _store[user_id][-5:]
