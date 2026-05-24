# File Input Methods for Azure OpenAI GPT Models

This document covers all supported ways to provide file input (images and documents) to vision-enabled Azure OpenAI models (GPT-5 series, GPT-4o series, GPT-4.1 series, GPT-4.5, o-series).

---

## Quick Reference: What's Supported?

| Format | Native API Input | Text Extraction Workaround | Tested on Azure GPT-5.2 |
|--------|:---:|:---:|:---:|
| **JPEG** | Yes (image_url) | N/A | PASS |
| **PNG** | Yes (image_url) | N/A | PASS |
| **GIF** | Yes (first frame) | N/A | PASS |
| **WEBP** | Yes (image_url) | N/A | PASS |
| **PDF** | Yes (OpenAI) / No (Azure Chat Completions) | Yes (PyPDF2, pymupdf) | PASS (text extraction) |
| **PPTX** | No | Yes (python-pptx) | PASS (text extraction) |
| **DOCX** | No | Yes (python-docx) | PASS (text extraction) |
| **XLSX** | No | Yes (openpyxl) | PASS (text extraction) |
| **CSV** | No | Yes (stdlib csv) | PASS (text extraction) |
| **Markdown** | No | Yes (read as text) | PASS (text extraction) |

---

# Part 1: Image Input

## Supported Image Formats

| Format | Notes |
|--------|-------|
| JPEG | Fully supported |
| PNG | Fully supported (transparency preserved) |
| GIF | First frame only |
| WEBP | Fully supported |

**Constraints:**
- Max image size: **50 MB**
- Max images per request: **10**

## Method 1: URL-Based Image

Pass a publicly accessible HTTP/HTTPS URL directly in the `image_url` field.

```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "Describe this image."},
            {
                "type": "image_url",
                "image_url": {
                    "url": "https://example.com/photo.jpg"
                }
            }
        ]
    }
]
```

**When to use:** The image is already hosted publicly (e.g., blob storage, CDN, Wikipedia).

**Important:** The URL must be reachable from Azure's servers. Private/authenticated URLs will fail.

## Method 2: Base64-Encoded Local File

Encode a local file as a base64 data URI and pass it in the same `image_url` field.

```python
import base64
from mimetypes import guess_type

def local_image_to_data_url(image_path: str) -> str:
    mime_type, _ = guess_type(image_path)
    if mime_type is None:
        mime_type = "application/octet-stream"
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"

data_url = local_image_to_data_url("diagram.png")

messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "Describe this image."},
            {
                "type": "image_url",
                "image_url": {
                    "url": data_url
                }
            }
        ]
    }
]
```

**When to use:** Local files, dynamically generated images, or when you can't host the image publicly.

## Method 3: Multiple Images in a Single Request

You can include up to **10 images** in one message by adding multiple `image_url` entries. URL and base64 can be mixed.

```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "Compare these two images."},
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/image1.jpg"}
            },
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,iVBOR..."}
            }
        ]
    }
]
```

## Detail Parameter

Controls image resolution processing. Set it on each `image_url` entry.

| Value | Behavior | Token Cost |
|-------|----------|------------|
| `auto` | Model decides based on image size (default) | Varies |
| `low` | Processes a 512x512 thumbnail only | Lower |
| `high` | Full resolution, split into 512x512 tiles | Higher |

```python
{
    "type": "image_url",
    "image_url": {
        "url": "https://example.com/photo.jpg",
        "detail": "high"
    }
}
```

**Guidance:**
- Use `low` for quick classification, captioning, or when fine detail doesn't matter.
- Use `high` for OCR, reading small text, analyzing charts, or detailed object recognition.
- `auto` is a sensible default for most use cases.

---

# Part 2: Document Input

## Azure vs OpenAI: Key Difference

OpenAI's Chat Completions API supports **native PDF input** via a `file` content type. However, **Azure OpenAI's Chat Completions endpoint does not support this** — it rejects the `file` content type with an "Invalid Value" error.

On Azure, the options for document input are:
1. **Text extraction** — extract text from the document and send as plain text (recommended, works for all formats)
2. **Render to images** — convert document pages to images and send via `image_url` (useful when layout matters)
3. **Azure Responses API (preview)** — supports native PDF input on some models, but uses a different API surface

## Method 1: Text Extraction (Recommended)

Extract text from the document using a Python library, then send as a plain text message. This is the most reliable approach and works on Azure.

### PDF

```python
# Using PyPDF2
from PyPDF2 import PdfReader

reader = PdfReader("document.pdf")
text = "\n".join(page.extract_text() for page in reader.pages)
```

### PPTX (PowerPoint)

```python
from pptx import Presentation

prs = Presentation("slides.pptx")
text = ""
for slide in prs.slides:
    for shape in slide.shapes:
        if shape.has_text_frame:
            text += shape.text_frame.text + "\n"
```

### DOCX (Word)

```python
from docx import Document

doc = Document("report.docx")
text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
```

### XLSX (Excel)

```python
from openpyxl import load_workbook

wb = load_workbook("data.xlsx")
text = ""
for ws in wb.worksheets:
    for row in ws.iter_rows(values_only=True):
        text += " | ".join(str(c) for c in row if c is not None) + "\n"
```

### CSV

```python
import csv

with open("data.csv") as f:
    reader = csv.reader(f)
    text = "\n".join(" | ".join(row) for row in reader)
```

### Markdown

```python
with open("document.md") as f:
    text = f.read()
```

### Sending Extracted Text to the Model

```python
messages = [
    {
        "role": "user",
        "content": f"The following is the content of a document:\n\n{text}\n\nSummarize the key points.",
    }
]
```

## Method 2: Render Document Pages as Images

When document layout, tables, or visual formatting matters, convert pages to images first.

```python
# PDF to images (requires pdf2image + poppler)
from pdf2image import convert_from_path

images = convert_from_path("document.pdf", dpi=150)
# Then base64-encode each image and send via image_url
```

**When to use:** Charts, tables with complex formatting, scanned documents, or when OCR-like understanding of layout is needed.

**Trade-off:** Higher token cost (image tokens) vs text extraction (text tokens).

## Method 3: Native PDF Input (OpenAI API only)

This works on OpenAI's API directly but **NOT on Azure Chat Completions**.

```python
# OpenAI native PDF (does NOT work on Azure Chat Completions)
import base64

with open("document.pdf", "rb") as f:
    b64 = base64.b64encode(f.read()).decode("utf-8")

messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "Summarize this document."},
            {
                "type": "file",
                "file": {
                    "filename": "document.pdf",
                    "file_data": f"data:application/pdf;base64,{b64}",
                },
            },
        ],
    }
]
```

**Azure error:** `Invalid Value: 'file'` — the Azure Chat Completions endpoint does not accept this content type.

## Required Libraries

| Format | Library | Install |
|--------|---------|---------|
| PDF | PyPDF2 or pymupdf | `pip install PyPDF2` |
| PPTX | python-pptx | `pip install python-pptx` |
| DOCX | python-docx | `pip install python-docx` |
| XLSX | openpyxl | `pip install openpyxl` |
| CSV | csv (stdlib) | Built-in |
| Markdown | — | Built-in (read as text) |
| PDF→Images | pdf2image | `pip install pdf2image` (requires poppler) |

---

# Part 3: SDK Examples

### OpenAI Python SDK (direct Azure)

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    base_url="https://YOUR-RESOURCE.openai.azure.com/openai/v1/",
)

response = client.chat.completions.create(
    model="gpt-5.2",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {"type": "image_url", "image_url": {"url": "<url_or_data_uri>"}},
            ],
        },
    ],
    max_tokens=300,
)
```

### LiteLLM (used in this project)

```python
import litellm

response = litellm.completion(
    model="azure/gpt-5.2",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image."},
                {"type": "image_url", "image_url": {"url": "<url_or_data_uri>"}},
            ],
        }
    ],
    api_base=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version="2024-12-01-preview",
    max_tokens=300,
)
```

### REST API (cURL)

```bash
curl -X POST "https://YOUR-RESOURCE.openai.azure.com/openai/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "api-key: $AZURE_OPENAI_API_KEY" \
  -d '{
    "model": "gpt-5.2",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "Describe this image."},
          {"type": "image_url", "image_url": {"url": "<url_or_data_uri>"}}
        ]
      }
    ],
    "max_tokens": 300
  }'
```

---

## Token Cost Considerations

- **Images** are converted to tokens for billing. The count depends on the `detail` level and image dimensions.
  - `low` detail: fixed token cost regardless of image size.
  - `high` detail: the image is first viewed at low res, then split into 512x512 tiles. Each tile costs additional tokens.
- **Text extraction** uses standard text tokens — generally cheaper than sending document pages as images.
- Always set `max_tokens` or `max_completion_tokens` — otherwise the response may be silently truncated.

---

## Limitations

- No video input (GIF = first frame only).
- No image generation — these are input-only capabilities. Use DALL-E for image generation.
- Images in URLs must be publicly accessible (no auth headers supported).
- **Azure Chat Completions does not support native PDF `file` content type** — use text extraction or image rendering instead.
- PPTX, DOCX, XLSX, CSV are never natively supported — always use text extraction.
- Content filtering applies to both image inputs and text outputs.
- Accuracy may vary with low-resolution images, rotated text, or highly specialized domains.

---

## References

- [Azure OpenAI — How to use vision-enabled models](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/gpt-with-vision)
- [Azure OpenAI — Vision-enabled model concepts](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/gpt-with-vision)
- [OpenAI — File inputs guide](https://developers.openai.com/api/docs/guides/pdf-files)
- [Introducing GPT-5.2 — OpenAI](https://openai.com/index/introducing-gpt-5-2/)
- [Azure OpenAI file type support — Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/5533767/i-wanted-to-know-list-of-files-types-supported-by)
