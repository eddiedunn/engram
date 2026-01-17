"""Text chunking utilities with semantic awareness."""

import re
from dataclasses import dataclass
from enum import StrEnum


class ChunkingStrategy(StrEnum):
    """Available chunking strategies."""

    SEMANTIC_250 = "semantic_250"
    SEMANTIC_500 = "semantic_500"
    SEMANTIC_1000 = "semantic_1000"
    PARAGRAPH = "paragraph"


@dataclass
class TextChunk:
    """A chunk of text with position information."""

    text: str
    start_char: int
    end_char: int
    index: int


class Chunker:
    """Semantic text chunker that respects sentence boundaries."""

    # Sentence boundary pattern
    SENTENCE_PATTERN = re.compile(
        r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\s*\n+|(?<=\n)\n+'
    )

    STRATEGY_SIZES = {
        ChunkingStrategy.SEMANTIC_250: 250,
        ChunkingStrategy.SEMANTIC_500: 500,
        ChunkingStrategy.SEMANTIC_1000: 1000,
        ChunkingStrategy.PARAGRAPH: 0,  # Special handling
    }

    def __init__(
        self,
        strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC_500,
        overlap_sentences: int = 1,
    ):
        """Initialize chunker with strategy.

        Args:
            strategy: Chunking strategy to use
            overlap_sentences: Number of sentences to overlap between chunks
        """
        self.strategy = strategy
        self.overlap_sentences = overlap_sentences
        self.target_size = self.STRATEGY_SIZES[strategy]

    def chunk(self, text: str) -> list[TextChunk]:
        """Split text into semantic chunks.

        Args:
            text: Full text to chunk

        Returns:
            List of TextChunk objects with position information
        """
        if not text.strip():
            return []

        if self.strategy == ChunkingStrategy.PARAGRAPH:
            return self._chunk_by_paragraph(text)

        return self._chunk_semantic(text)

    def _chunk_semantic(self, text: str) -> list[TextChunk]:
        """Chunk text by sentence boundaries respecting target size."""
        sentences = self._split_sentences(text)
        if not sentences:
            return [TextChunk(text=text, start_char=0, end_char=len(text), index=0)]

        chunks: list[TextChunk] = []
        current_sentences: list[tuple[str, int, int]] = []
        current_size = 0

        for sentence, start, end in sentences:
            sentence_len = len(sentence)

            # If adding this sentence exceeds target and we have content, finalize chunk
            if current_size + sentence_len > self.target_size and current_sentences:
                chunk = self._create_chunk(current_sentences, len(chunks))
                chunks.append(chunk)

                # Keep overlap sentences for context
                if self.overlap_sentences > 0:
                    current_sentences = current_sentences[-self.overlap_sentences :]
                    current_size = sum(len(s[0]) for s in current_sentences)
                else:
                    current_sentences = []
                    current_size = 0

            current_sentences.append((sentence, start, end))
            current_size += sentence_len

        # Don't forget the last chunk
        if current_sentences:
            chunks.append(self._create_chunk(current_sentences, len(chunks)))

        return chunks

    def _chunk_by_paragraph(self, text: str) -> list[TextChunk]:
        """Chunk text by paragraph boundaries."""
        paragraphs = re.split(r'\n\s*\n', text)
        chunks: list[TextChunk] = []
        pos = 0

        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue

            # Find actual position in original text
            start = text.find(para, pos)
            if start == -1:
                start = pos
            end = start + len(para)
            pos = end

            chunks.append(TextChunk(text=para, start_char=start, end_char=end, index=i))

        return chunks

    def _split_sentences(self, text: str) -> list[tuple[str, int, int]]:
        """Split text into sentences with position tracking."""
        sentences: list[tuple[str, int, int]] = []
        last_end = 0

        for match in self.SENTENCE_PATTERN.finditer(text):
            sentence = text[last_end : match.start()].strip()
            if sentence:
                sentences.append((sentence, last_end, match.start()))
            last_end = match.end()

        # Last sentence
        remaining = text[last_end:].strip()
        if remaining:
            sentences.append((remaining, last_end, len(text)))

        return sentences

    def _create_chunk(
        self, sentences: list[tuple[str, int, int]], index: int
    ) -> TextChunk:
        """Create a TextChunk from a list of sentences."""
        text = " ".join(s[0] for s in sentences)
        start_char = sentences[0][1]
        end_char = sentences[-1][2]
        return TextChunk(text=text, start_char=start_char, end_char=end_char, index=index)
