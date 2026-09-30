import csv
import io
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from pypdf import PdfReader

# Allowed extensions mapped to standard types
TEXT_EXTENSIONS = {
    '.txt', '.md', '.markdown', '.rtf', '.log',
    # Code & configuration
    '.py', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.scss',
    '.json', '.yaml', '.yml', '.toml', '.xml', '.env', '.sh', '.bash',
    '.c', '.cpp', '.h', '.hpp', '.rs', '.go', '.java', '.kt',
    '.rb', '.php', '.sql', '.r', '.swift', '.scala', '.dockerfile',
}

DOCUMENT_EXTENSIONS = {'.pdf', '.docx', '.csv'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
ALLOWED_EXTENSIONS = TEXT_EXTENSIONS | DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS

# Dangerous executable file patterns strictly forbidden
FORBIDDEN_EXTENSIONS = {
    '.exe', '.dll', '.so', '.dylib', '.bat', '.cmd', '.com', '.msi',
    '.scr', '.vbs', '.wsf', '.cpl', '.jar', '.bin'
}

# Known Ollama vision model signatures
KNOWN_OLLAMA_VISION_MODELS = {
    'llava', 'llama3.2-vision', 'bakllava', 'minicpm-v', 'moondream',
    'qwen2-vl', 'granite3-vision', 'vision'
}

# Known Cloud vision models
CLOUD_VISION_MODELS = {
    'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'claude-3-5-sonnet',
    'claude-3-haiku', 'claude-3-opus', 'gemini-2.0-flash', 'gemini-1.5-pro',
    'gemini-1.5-flash', 'llama-3.2-11b-vision-preview', 'llama-3.2-90b-vision-preview'
}


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and special character injection."""
    name = Path(filename).name
    # Keep alphanumeric, underscores, dots, hyphens
    clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
    return clean[:120] if clean else 'uploaded_file'


def validate_file_type(filename: str) -> str:
    """Validate that the file type is permitted. Returns the lowercase extension."""
    ext = Path(filename).suffix.lower()
    if not ext:
        raise ValueError('Files without a valid extension are not supported.')
    if ext in FORBIDDEN_EXTENSIONS or ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Allowed types: PDF, DOCX, CSV, TXT, Markdown, images, and source code files."
        )
    return ext


def is_image_extension(ext: str) -> bool:
    return ext.lower() in IMAGE_EXTENSIONS


def extract_docx_text(file_path: Path) -> str:
    """Extract formatted text from docx via document.xml without requiring python-docx."""
    try:
        with zipfile.ZipFile(file_path) as z:
            xml_content = z.read('word/document.xml')
        tree = ET.fromstring(xml_content)
        # XML namespace for wordprocessingML
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        paragraphs = []
        for p in tree.iterfind('.//w:p', namespaces):
            texts = [node.text for node in p.iterfind('.//w:t', namespaces) if node.text]
            if texts:
                paragraphs.append(''.join(texts))
        return '\n\n'.join(paragraphs)
    except Exception as e:
        raise ValueError(f'Unable to parse DOCX file: {e}')


def extract_pdf_text(file_path: Path, filename: str) -> tuple[str, int]:
    """Extract page-by-page text from a PDF with page citations."""
    try:
        reader = PdfReader(str(file_path))
        page_count = len(reader.pages)
        sections = []
        for i, page in enumerate(reader.pages):
            txt = page.extract_text() or ''
            clean_txt = txt.strip()
            if clean_txt:
                sections.append(f'--- [File: {filename}, Page {i + 1}] ---\n{clean_txt}')
            else:
                sections.append(f'--- [File: {filename}, Page {i + 1}] ---\n[Empty or image-only page]')
        return '\n\n'.join(sections), page_count
    except Exception as e:
        raise ValueError(f'Unable to parse PDF document: {e}')


def extract_csv_text(file_path: Path, filename: str) -> tuple[str, int]:
    """Extract formatted tabular text from a CSV file."""
    try:
        with open(file_path, mode='r', encoding='utf-8', errors='replace') as f:
            reader = list(csv.reader(f))
        
        row_count = len(reader)
        if not reader:
            return f'--- [File: {filename}] ---\n(Empty CSV file)', 1

        # Format up to 100 rows cleanly
        formatted_rows = []
        headers = reader[0]
        formatted_rows.append(' | '.join(headers))
        formatted_rows.append(' | '.join(['---'] * len(headers)))

        for row in reader[1:101]:
            formatted_rows.append(' | '.join(row))

        if row_count > 101:
            formatted_rows.append(f'... [{row_count - 101} more rows omitted for space]')

        text = f'--- [File: {filename}, Rows 1-{min(row_count, 101)} of {row_count}] ---\n' + '\n'.join(formatted_rows)
        return text, 1
    except Exception as e:
        raise ValueError(f'Unable to parse CSV file: {e}')


def extract_code_or_text(file_path: Path, filename: str, ext: str) -> tuple[str, int]:
    """Extract source code or plain text file with line numbers for precise citation."""
    try:
        with open(file_path, mode='r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        lang = ext.lstrip('.')
        if lang in ('txt', 'md', 'markdown', 'log'):
            content = ''.join(lines)
            return f'--- [File: {filename}] ---\n{content}', 1
        
        # Source code with line numbers
        numbered = [f'{i + 1:4d} | {line}' for i, line in enumerate(lines)]
        code_block = (
            f'--- [File: {filename}, Lines 1-{total_lines}] ---\n'
            f'```{lang}\n'
            f"{''.join(numbered)}"
            f'```'
        )
        return code_block, 1
    except Exception as e:
        raise ValueError(f'Unable to read text or source file: {e}')


def extract_file_content(file_path: Path, filename: str) -> tuple[str, int, bool]:
    """
    Extract content from an uploaded file.
    Returns: (extracted_text, page_count, is_image)
    """
    ext = validate_file_type(filename)
    if is_image_extension(ext):
        return '', 1, True

    if ext == '.pdf':
        text, pages = extract_pdf_text(file_path, filename)
        return text, pages, False
    elif ext == '.docx':
        text = extract_docx_text(file_path)
        return f'--- [File: {filename}] ---\n{text}', 1, False
    elif ext == '.csv':
        text, pages = extract_csv_text(file_path, filename)
        return text, pages, False
    else:
        text, pages = extract_code_or_text(file_path, filename, ext)
        return text, pages, False


def check_vision_support(provider: str, model: str) -> tuple[bool, str]:
    """
    Check if the provider & model support image input.
    Returns (is_supported, explanation_if_not).
    """
    p = provider.lower()
    m = model.lower()

    if p == 'ollama':
        is_supported = any(sig in m for sig in KNOWN_OLLAMA_VISION_MODELS)
        if not is_supported:
            return (
                False,
                f"The selected Ollama model '{model}' does not support vision or image analysis. "
                f"Please switch to a vision-capable model (such as llama3.2-vision or llava) or attach a document/text file instead."
            )
        return True, ""

    # Cloud providers
    is_cloud_vision = any(sig in m for sig in CLOUD_VISION_MODELS)
    if not is_cloud_vision:
        return (
            False,
            f"The selected model '{model}' on {provider.title()} does not support image analysis. "
            f"Please switch to a vision model (like GPT-4o, Gemini 2.0 Flash, or Claude 3.5 Sonnet) or attach a document/text file."
        )
    return True, ""
