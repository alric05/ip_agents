"""
Quick test script to verify Azure OpenAI GPT-5.2 vision support across image formats.

Tests both URL-based and local file (base64-encoded) image inputs.

Usage:
    python test_vision_formats.py
"""

import base64
import io
import os
import tempfile
import time
from pathlib import Path

import litellm
from dotenv import load_dotenv
from PIL import Image, ImageDraw

# Load .env from project root
load_dotenv(Path(__file__).parent / ".env")

litellm.drop_params = True

MODEL = f"azure/{os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-5.2')}"

# Public sample images in different formats
TEST_IMAGES = {
    "JPEG": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png",
    "PNG": "https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png",
    "GIF": "https://upload.wikimedia.org/wikipedia/commons/2/2c/Rotating_earth_%28large%29.gif",
    "WEBP": "https://www.gstatic.com/webp/gallery/1.webp",
}

PROMPT = "Describe this image in one sentence."

MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}

PIL_FORMATS = {
    "JPEG": "JPEG",
    "PNG": "PNG",
    "GIF": "GIF",
    "WEBP": "WEBP",
}


def generate_local_images(tmp_dir: str) -> dict[str, str]:
    """Generate simple test images in each format and return {format: filepath}."""
    paths = {}
    for fmt, pil_fmt in PIL_FORMATS.items():
        img = Image.new("RGB", (200, 200), color="white")
        draw = ImageDraw.Draw(img)
        # Draw distinct shapes so the model can describe each differently
        if fmt == "JPEG":
            draw.rectangle([30, 30, 170, 170], fill="red", outline="black")
            draw.text((60, 90), "JPEG", fill="white")
        elif fmt == "PNG":
            draw.ellipse([30, 30, 170, 170], fill="blue", outline="black")
            draw.text((70, 90), "PNG", fill="white")
        elif fmt == "GIF":
            draw.polygon([(100, 30), (30, 170), (170, 170)], fill="green", outline="black")
            draw.text((70, 110), "GIF", fill="white")
        elif fmt == "WEBP":
            draw.rounded_rectangle([30, 30, 170, 170], radius=30, fill="orange", outline="black")
            draw.text((65, 90), "WEBP", fill="white")

        ext = fmt.lower()
        path = os.path.join(tmp_dir, f"test.{ext}")
        img.save(path, pil_fmt)
        paths[fmt] = path
    return paths


def _call_model(messages: list[dict]) -> dict:
    """Send messages to the model and return result dict."""
    start = time.time()
    try:
        resp = litellm.completion(
            model=MODEL,
            messages=messages,
            api_base=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            max_tokens=150,
        )
        elapsed = time.time() - start
        content = resp.choices[0].message.content.strip()
        return {"status": "PASS", "response": content, "time": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        return {"status": "FAIL", "response": str(e)[:200], "time": elapsed}


def test_image_url(fmt: str, url: str) -> dict:
    """Test an image via URL."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": url}},
            ],
        }
    ]
    result = _call_model(messages)
    result["format"] = fmt
    result["source"] = "URL"
    return result


def test_image_local(fmt: str, filepath: str) -> dict:
    """Test a local image file via base64 encoding."""
    with open(filepath, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    data_uri = f"data:{MIME_TYPES[fmt]};base64,{b64}"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        }
    ]
    result = _call_model(messages)
    result["format"] = fmt
    result["source"] = "LOCAL"
    return result


def print_results(title: str, results: list[dict]):
    """Print a summary table for a set of results."""
    print(f"\n{'=' * 70}")
    print(title)
    print("-" * 70)
    for r in results:
        icon = "+" if r["status"] == "PASS" else "X"
        print(f"  [{icon}] {r['format']:<6} {r['status']}  ({r['time']:.1f}s)")
    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"  {passed}/{len(results)} passed")


def main():
    print(f"Model: {MODEL}")
    print(f"Endpoint: {os.environ.get('AZURE_OPENAI_ENDPOINT', 'NOT SET')}")
    print(f"API Version: {os.environ.get('AZURE_OPENAI_API_VERSION', '2024-12-01-preview')}")

    # --- URL-based tests ---
    print("\n" + "=" * 70)
    print("TEST 1: URL-based images")
    print("=" * 70)
    url_results = []
    for fmt, url in TEST_IMAGES.items():
        print(f"\n  Testing {fmt} (URL)...")
        result = test_image_url(fmt, url)
        url_results.append(result)
        print(f"    [{result['status']}] ({result['time']:.1f}s) {result['response'][:100]}")

    # --- Local file tests ---
    print("\n" + "=" * 70)
    print("TEST 2: Local file images (base64)")
    print("=" * 70)
    local_results = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        local_images = generate_local_images(tmp_dir)
        for fmt, filepath in local_images.items():
            size_kb = os.path.getsize(filepath) / 1024
            print(f"\n  Testing {fmt} (local, {size_kb:.1f} KB)...")
            result = test_image_local(fmt, filepath)
            local_results.append(result)
            print(f"    [{result['status']}] ({result['time']:.1f}s) {result['response'][:100]}")

    # --- Combined summary ---
    print_results("SUMMARY: URL-based", url_results)
    print_results("SUMMARY: Local file (base64)", local_results)

    all_results = url_results + local_results
    total_passed = sum(1 for r in all_results if r["status"] == "PASS")
    print(f"\nOVERALL: {total_passed}/{len(all_results)} tests passed")


if __name__ == "__main__":
    main()
