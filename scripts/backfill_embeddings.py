"""Backfill pending embeddings."""
import asyncio
from engram.storage import get_storage
from engram.embedding import Embedder

async def backfill():
    storage = get_storage()
    embedder = Embedder()

    while True:
        # Get batch of pending chunks
        pending = await storage.get_chunks_by_status('pending', limit=50)
        if not pending:
            break

        texts = [c.text for c in pending]
        embeddings = embedder.embed_batch(texts)

        if embeddings is None:
            print("Embed service unavailable, stopping")
            break

        for chunk, embedding in zip(pending, embeddings):
            await storage.update_chunk_embedding(chunk.id, embedding)

        print(f"Backfilled {len(pending)} chunks")

if __name__ == "__main__":
    asyncio.run(backfill())
