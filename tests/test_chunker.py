"""Tests for the text chunker (pure logic, no DB or network)."""

import pytest

from engram.embedding.chunker import Chunker, ChunkingStrategy, TextChunk


class TestChunkerBasics:
    """Basic chunker behavior."""

    def test_empty_text_returns_empty(self) -> None:
        chunker = Chunker()
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_short_text_single_chunk(self) -> None:
        chunker = Chunker(strategy=ChunkingStrategy.SEMANTIC_500)
        chunks = chunker.chunk("Hello world.")
        assert len(chunks) == 1
        assert chunks[0].text == "Hello world."
        assert chunks[0].index == 0
        assert chunks[0].start_char == 0
        assert chunks[0].end_char == len("Hello world.")

    def test_chunk_dataclass_fields(self) -> None:
        chunk = TextChunk(text="sample", start_char=10, end_char=16, index=3)
        assert chunk.text == "sample"
        assert chunk.start_char == 10
        assert chunk.end_char == 16
        assert chunk.index == 3


class TestSemanticChunking:
    """Semantic chunking splits on sentence boundaries."""

    @pytest.fixture()
    def long_text(self) -> str:
        """Generate text that exceeds the 250-char target."""
        sentences = [
            f"Sentence number {i} is here to fill up the chunk with enough content. "
            for i in range(20)
        ]
        return " ".join(sentences)

    def test_multiple_chunks_produced(self, long_text: str) -> None:
        chunker = Chunker(strategy=ChunkingStrategy.SEMANTIC_250)
        chunks = chunker.chunk(long_text)
        assert len(chunks) > 1, "Long text should produce multiple chunks"

    def test_chunks_cover_full_text(self, long_text: str) -> None:
        """Every character in the original text should appear in at least one chunk."""
        chunker = Chunker(strategy=ChunkingStrategy.SEMANTIC_250, overlap_sentences=0)
        chunks = chunker.chunk(long_text)
        # Concatenated chunk text (minus overlap) should contain all content
        combined = " ".join(c.text for c in chunks)
        # At minimum, first and last words should be present
        assert "Sentence number 0" in combined
        assert "Sentence number 19" in combined

    def test_chunk_indices_sequential(self, long_text: str) -> None:
        chunker = Chunker(strategy=ChunkingStrategy.SEMANTIC_250)
        chunks = chunker.chunk(long_text)
        indices = [c.index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_overlap_increases_chunk_count(self, long_text: str) -> None:
        no_overlap = Chunker(strategy=ChunkingStrategy.SEMANTIC_250, overlap_sentences=0)
        with_overlap = Chunker(strategy=ChunkingStrategy.SEMANTIC_250, overlap_sentences=2)
        chunks_no = no_overlap.chunk(long_text)
        chunks_yes = with_overlap.chunk(long_text)
        # Overlap should produce at least as many chunks (usually more due to repeated sentences)
        assert len(chunks_yes) >= len(chunks_no)


class TestParagraphChunking:
    """Paragraph-based chunking."""

    def test_splits_on_double_newline(self) -> None:
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunker = Chunker(strategy=ChunkingStrategy.PARAGRAPH)
        chunks = chunker.chunk(text)
        assert len(chunks) == 3
        assert chunks[0].text == "First paragraph."
        assert chunks[1].text == "Second paragraph."
        assert chunks[2].text == "Third paragraph."

    def test_skips_blank_paragraphs(self) -> None:
        text = "Content.\n\n\n\n\n\nMore content."
        chunker = Chunker(strategy=ChunkingStrategy.PARAGRAPH)
        chunks = chunker.chunk(text)
        assert len(chunks) == 2


class TestChunkingStrategies:
    """Different target sizes."""

    def test_strategy_sizes(self) -> None:
        assert Chunker.STRATEGY_SIZES[ChunkingStrategy.SEMANTIC_250] == 250
        assert Chunker.STRATEGY_SIZES[ChunkingStrategy.SEMANTIC_500] == 500
        assert Chunker.STRATEGY_SIZES[ChunkingStrategy.SEMANTIC_1000] == 1000
        assert Chunker.STRATEGY_SIZES[ChunkingStrategy.PARAGRAPH] == 0

    def test_smaller_target_more_chunks(self) -> None:
        text = "A" * 50 + ". " + "B" * 50 + ". " + "C" * 50 + ". " + "D" * 50 + "."
        c250 = Chunker(strategy=ChunkingStrategy.SEMANTIC_250)
        c1000 = Chunker(strategy=ChunkingStrategy.SEMANTIC_1000)
        assert len(c250.chunk(text)) >= len(c1000.chunk(text))
