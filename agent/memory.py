import uuid

import chromadb
from rich.console import Console

console = Console()

INNOCENT_MEMORIES = [
    (
        "seed_0",
        "User prefers bullet-point summaries when presenting data or reports.",
        {"type": "preference", "source": "system"},
    ),
    (
        "seed_1",
        "Q4 report is stored in ./demo/documents/q4_report.txt",
        {"type": "document_location", "source": "system"},
    ),
    (
        "seed_2",
        "Always respond in English unless the user writes in another language.",
        {"type": "preference", "source": "system"},
    ),
    (
        "seed_3",
        "User is a financial analyst working on quarterly performance reviews.",
        {"type": "user_context", "source": "system"},
    ),
]


class AgentMemory:
    def __init__(self, path: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(name="agent_memory")
        self._seed_if_empty()

    def _seed_if_empty(self) -> None:
        if self.collection.count() == 0:
            console.print("[dim]  Seeding agent memory with initial context...[/dim]")
            for doc_id, text, metadata in INNOCENT_MEMORIES:
                self.collection.add(
                    documents=[text],
                    ids=[doc_id],
                    metadatas=[metadata],
                )

    def add_memory(self, text: str, metadata: dict) -> None:
        self.collection.add(
            documents=[text],
            ids=[str(uuid.uuid4())],
            metadatas=[metadata],
        )

    def retrieve_relevant(self, query: str, n_results: int = 5) -> list[str]:
        count = self.collection.count()
        if count == 0:
            return []
        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, count),
        )
        return results["documents"][0] if results["documents"] else []

    def clear_memories(self) -> None:
        self.client.delete_collection("agent_memory")
        self.collection = self.client.get_or_create_collection(name="agent_memory")
        self._seed_if_empty()
