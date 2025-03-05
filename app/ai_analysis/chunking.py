"""
Intelligent text chunking utilities for large documents.
"""

import re
import logging
from typing import List, Tuple, Any

from .errors import ContentProcessingError

logger = logging.getLogger(__name__)

class TextChunker:
    """
    Handles intelligent splitting of large text documents into manageable chunks.
    Preserves context and document structure where possible.
    """

    def __init__(self, token_counter):
        """
        Initialize the text chunker.

        Args:
            token_counter: TokenCounter instance for measuring token counts
        """
        self.token_counter = token_counter

    def chunk_text(self, text: str, max_tokens: int) -> Tuple[List[str], bool]:
        """
        Intelligently split text into chunks based on document structure.
        Attempts to preserve coherent sections and maintain context.

        Args:
            text: Full text to split
            max_tokens: Maximum tokens allowed per chunk

        Returns:
            Tuple of (list of text chunks, whether document has clear structure)

        Raises:
            ContentProcessingError: If text cannot be split properly
        """
        if not text:
            return ([""], False)

        try:
            # If text fits in one chunk, return it directly
            if self.token_counter.count_tokens(text) <= max_tokens:
                return ([text], False)

            # Look for section markers that indicate document structure
            section_patterns = [
                # Common section patterns in legislation
                r'(?:^|\n)(?:Section|SEC\.|SECTION|Article|ARTICLE|Title|TITLE)\s+\d+\.?',
                r'(?:^|\n)§+\s*\d+',  # Section symbol
                r'(?:^|\n)\d+\.\s+[A-Z]',  # Numbered sections
                r'(?:^|\n)[A-Z][A-Z\s]+\n',  # ALL CAPS headers
                r'(?:^|\n)\*\*\*.*?\*\*\*',  # Special markers
            ]

            # Detect if document has clear structure
            has_structure = False
            for pattern in section_patterns:
                if len(re.findall(pattern, text)) > 3:  # At least 3 matches indicate structure
                    has_structure = True
                    break

            chunks = []

            if has_structure:
                # Split based on document structure
                logger.info("Document has clear structure, splitting by sections")
                chunks = self._split_by_structure(text, max_tokens, section_patterns)
            else:
                # Fallback to paragraph-based splitting
                logger.info("Document lacks clear structure, splitting by paragraphs")
                chunks = self._split_by_paragraphs(text, max_tokens)

            # If we still don't have any chunks (rare case), use basic splitting
            if not chunks:
                logger.warning("Falling back to basic token-based splitting")
                chunks = self._basic_token_split(text, max_tokens)

            # Validate the chunks
            if not chunks:
                raise ContentProcessingError("Failed to split text into chunks")

            # Log split information
            logger.info(f"Split text into {len(chunks)} chunks, has_structure={has_structure}")
            for i, chunk in enumerate(chunks):
                logger.debug(f"Chunk {i+1}: ~{self.token_counter.count_tokens(chunk)} tokens")

            return (chunks, has_structure)

        except Exception as e:
            error_msg = f"Error splitting text into chunks: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ContentProcessingError(error_msg) from e

    def _split_by_structure(self, text: str, max_tokens: int, patterns: List[str]) -> List[str]:
        """
        Split text based on document structure using section patterns.

        Args:
            text: Text to split
            max_tokens: Maximum tokens per chunk
            patterns: List of regex patterns identifying structural elements

        Returns:
            List of text chunks maintaining structural integrity
        """
        # Combine all patterns into one regex for splitting
        combined_pattern = '|'.join(f'({p})' for p in patterns)

        # Get all potential split points while preserving the delimiter
        parts = re.split(f'(?=({combined_pattern}))', text)

        # Remove empty parts
        parts = [p for p in parts if p.strip()]

        chunks = []
        current_chunk = ""

        for part in parts:
            # Calculate tokens in current chunk + new part
            temp_chunk = current_chunk + part
            tokens = self.token_counter.count_tokens(temp_chunk)

            if tokens <= max_tokens:
                # Add to current chunk if we're within limits
                current_chunk = temp_chunk
            else:
                # Save current chunk and start a new one
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = part

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _split_by_paragraphs(self, text: str, max_tokens: int) -> List[str]:
        """
        Split text by paragraphs for documents without clear section structure.

        Args:
            text: Text to split
            max_tokens: Maximum tokens per chunk

        Returns:
            List of text chunks split by paragraphs
        """
        paragraphs = re.split(r'\n\s*\n', text)

        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Calculate tokens in current chunk + new paragraph
            temp_chunk = current_chunk + ("\n\n" if current_chunk else "") + para
            tokens = self.token_counter.count_tokens(temp_chunk)

            if tokens <= max_tokens:
                # Add to current chunk if we're within limits
                current_chunk = temp_chunk
            else:
                # Check if this single paragraph is too big
                if not current_chunk:
                    # Single paragraph is too large, split by sentences
                    logger.warning("Found paragraph exceeding token limit, splitting by sentences")
                    para_chunks = self._split_paragraph_by_sentences(para, max_tokens)
                    chunks.extend(para_chunks)
                    current_chunk = ""
                    continue

                # Save current chunk and start a new one with this paragraph
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _split_paragraph_by_sentences(self, paragraph: str, max_tokens: int) -> List[str]:
        """
        Split a large paragraph by sentences when needed.

        Args:
            paragraph: Text of the paragraph
            max_tokens: Maximum tokens per chunk

        Returns:
            List of text chunks at the sentence level
        """
        # Use regex for sentence boundaries (handles periods in abbreviations better)
        sentence_pattern = r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s'
        sentences = re.split(sentence_pattern, paragraph)

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if this sentence alone exceeds the limit
            sentence_tokens = self.token_counter.count_tokens(sentence)
            if sentence_tokens > max_tokens:
                # Extremely long sentence, split by character count as last resort
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""

                logger.warning(f"Found extremely long sentence ({sentence_tokens} tokens), splitting by character count")

                # Approximately how many characters per token
                chars_per_token = len(sentence) / sentence_tokens
                max_chars = int(max_tokens * chars_per_token) * 0.9  # 90% to be safe

                # Split into roughly equal parts
                for i in range(0, len(sentence), int(max_chars)):
                    chunks.append(sentence[i:i+int(max_chars)])
            else:
                # Calculate tokens in current chunk + new sentence
                temp_chunk = current_chunk + (" " if current_chunk else "") + sentence
                tokens = self.token_counter.count_tokens(temp_chunk)

                if tokens <= max_tokens:
                    # Add to current chunk if we're within limits
                    current_chunk = temp_chunk
                else:
                    # Save current chunk and start a new one with this sentence
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = sentence

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _basic_token_split(self, text: str, max_tokens: int) -> List[str]:
        """
        Basic fallback method to split text by estimated token counts.

        Args:
            text: Text to split
            max_tokens: Maximum tokens per chunk

        Returns:
            List of text chunks of roughly equal size
        """
        # Get rough token estimate to determine total chunks needed
        total_tokens = self.token_counter.count_tokens(text)

        # If single paragraph or can't detect sections, split by approximate token count
        chunk_count = (total_tokens // max_tokens) + 1

        if chunk_count <= 1:
            return [text]

        # Estimate characters per chunk (approximate)
        chars_per_token = len(text) / total_tokens
        chars_per_chunk = int(max_tokens * chars_per_token) * 0.9  # 90% to be safe

        chunks = []
        # Split into roughly equal parts
        for i in range(0, len(text), int(chars_per_chunk)):
            chunks.append(text[i:i+int(chars_per_chunk)])

        return chunks