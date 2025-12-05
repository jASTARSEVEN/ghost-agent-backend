import asyncio
import re
import aiofiles
import mimetypes
import docx
import PyPDF2
import io
from fastapi import UploadFile


async def save_uploaded_file(file, destination: str):
    """Save uploaded file asynchronously to the specified destination."""
    async with aiofiles.open(destination, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
    return destination


async def extract_text_from_file(path: str) -> str:
    """
    Extract text from a file asynchronously.
    Supports PDF, DOCX, and TXT files.
    
    Args:
        path: Path to the file
        
    Returns:
        Extracted text content
        
    Raises:
        ValueError: If file type is not supported
        FileNotFoundError: If file doesn't exist
    """
    if path.endswith(".pdf"):
        return await extract_from_pdf(path)
    elif path.endswith(".docx"):
        return await extract_from_docx(path)
    elif path.endswith(".txt"):
        return await extract_from_text(path)
    else:
        # Try to guess from mimetype
        mime, _ = mimetypes.guess_type(path)
        if mime == "application/pdf":
            return await extract_from_pdf(path)
        elif mime in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
            return await extract_from_docx(path)
        else:
            # Default to text extraction
            return await extract_from_text(path)


async def extract_from_pdf(path: str) -> str:
    """
    Extract text from PDF file asynchronously.
    Runs synchronous PyPDF2 operations in a thread executor.
    """
    def _extract_sync():
        text = ""
        try:
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ""
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")
        return text
    
    return await asyncio.to_thread(_extract_sync)


async def extract_from_docx(path: str) -> str:
    """
    Extract text from DOCX file asynchronously.
    Runs synchronous python-docx operations in a thread executor.
    """
    def _extract_sync():
        try:
            doc = docx.Document(path)
            return "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            raise ValueError(f"Failed to extract text from DOCX: {str(e)}")
    
    return await asyncio.to_thread(_extract_sync)


async def extract_from_text(path: str) -> str:
    """
    Extract text from plain text file asynchronously.
    """
    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            return await f.read()
    except UnicodeDecodeError:
        # Try with different encoding
        try:
            async with aiofiles.open(path, "r", encoding="latin-1") as f:
                return await f.read()
        except Exception as e:
            raise ValueError(f"Failed to extract text from file: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to read text file: {str(e)}")


def clean_and_concatenate_text(text_sources: list[str], separator: str = "\n\n") -> str:
    """
    Clean and concatenate multiple text sources into a single cleaned string.
    
    Args:
        text_sources: List of text strings to clean and concatenate
        separator: String to use between concatenated texts (default: double newline)
        
    Returns:
        Cleaned and concatenated text
    """
    if not text_sources:
        return ""
    
    cleaned_texts = []
    for text in text_sources:
        if text:
            cleaned = clean_text(text)
            if cleaned.strip():  # Only add non-empty cleaned text
                cleaned_texts.append(cleaned)
    
    return separator.join(cleaned_texts)


def clean_text(text: str) -> str:
    """
    Clean and normalize text content.
    
    - Removes excessive whitespace
    - Normalizes line breaks
    - Removes control characters (except newlines and tabs)
    - Handles encoding issues
    
    Args:
        text: Raw text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove null bytes and other problematic control characters
    text = text.replace("\x00", "")
    
    # Normalize line breaks (handle Windows \r\n, Mac \r, Unix \n)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # Remove excessive blank lines (more than 2 consecutive newlines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # Remove trailing whitespace from each line
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    
    # Remove leading/trailing whitespace from entire text
    text = text.strip()
    
    # Remove excessive spaces (more than 2 consecutive spaces)
    text = re.sub(r" {3,}", "  ", text)
    
    return text


async def extract_text_from_upload(file: UploadFile) -> str:
    """
    Extract text from an UploadFile object in-memory without saving to disk.
    Supports PDF, DOCX, and TXT files.
    
    Args:
        file: FastAPI UploadFile object
        
    Returns:
        Extracted text content
        
    Raises:
        ValueError: If file type is not supported or extraction fails
    """
    content = await file.read()
    await file.seek(0)  # Reset file pointer for potential reuse
    
    filename = file.filename.lower()
    
    if filename.endswith(".txt"):
        try:
            return content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return content.decode('latin-1')
            except Exception as e:
                raise ValueError(f"Failed to decode text file: {str(e)}")
    
    elif filename.endswith(".pdf"):
        try:
            pdf_file = io.BytesIO(content)
            reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")
    
    elif filename.endswith(".docx"):
        try:
            docx_file = io.BytesIO(content)
            doc = docx.Document(docx_file)
            return "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            raise ValueError(f"Failed to extract text from DOCX: {str(e)}")
    
    else:
        raise ValueError(f"Unsupported file type: {filename}. Supported types: .txt, .pdf, .docx")
