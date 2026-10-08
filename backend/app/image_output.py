"""Image-output adapters. Provider credentials remain in the supplied backend client.

Ollama's experimental v0.15 API emits image/completed/total via /api/generate.
Newer builds may reject it; surface that error rather than fabricate an image.
"""
import asyncio
import base64
import binascii
import io
import json
import uuid
import warnings
try:
    from PIL import Image, UnidentifiedImageError
    DecompressionBombWarning = Image.DecompressionBombWarning
    DecompressionBombError = Image.DecompressionBombError
except ImportError:
    Image = None
    class UnidentifiedImageError(Exception):
        pass
    class DecompressionBombWarning(Warning):
        pass
    class DecompressionBombError(Exception):
        pass

from .config import settings
from .database import connect

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_RESPONSE_BYTES = 32 * 1024 * 1024


def decode_image(encoded):
    if Image is None:
        raise ValueError('Image processing library (Pillow) is not available on this server.')
    if not isinstance(encoded, str) or len(encoded) > MAX_RESPONSE_BYTES:
        raise ValueError('The generated image exceeds the supported size.')
    try:
        data = base64.b64decode(encoded, validate=True)
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError('The generated image is too large.')
        with warnings.catch_warnings():
            warnings.simplefilter('error', DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as picture:
                if picture.format not in ('PNG', 'JPEG', 'WEBP'):
                    raise ValueError('The provider returned an unsupported image format. Choose a raster image model.')
                if picture.width * picture.height > 32_000_000:
                    raise ValueError('The generated image dimensions are too large.')
                fmt = picture.format
                picture.verify()
        return data, {'PNG': ('image/png', 'png'), 'JPEG': ('image/jpeg', 'jpg'), 'WEBP': ('image/webp', 'webp')}[fmt]
    except (binascii.Error, UnidentifiedImageError, OSError, DecompressionBombWarning, DecompressionBombError) as exc:
        raise ValueError('The provider returned invalid image data. Please retry.') from exc


async def ndjson(response):
    buffer = b''
    async for chunk in response.aiter_bytes():
        buffer += chunk
        if len(buffer) > MAX_RESPONSE_BYTES:
            raise ValueError('The image response is too large.')
        while b'\n' in buffer:
            line, buffer = buffer.split(b'\n', 1)
            if line.strip():
                yield json.loads(line)
    if buffer.strip():
        yield json.loads(buffer)


async def generate_image(client, provider, model, prompt, notify):
    if Image is None:
        raise ValueError('Image processing library (Pillow) is not available on this server.')
    async with asyncio.timeout(settings.GENERATION_TIMEOUT):
        if provider == 'ollama':
            encoded, complete = None, False
            async with client.stream('POST', '/api/generate', json={
                'model': model, 'prompt': prompt, 'stream': True, 'width': 1024, 'height': 1024,
            }) as response:
                if response.status_code == 400:
                    raise ValueError('This Ollama server rejected image generation. Check its experimental image support and selected model.')
                response.raise_for_status()
                async for item in ndjson(response):
                    if item.get('error'):
                        raise ValueError('Ollama could not generate this image. Check that its server version and platform support experimental image generation.')
                    if item.get('image'):
                        encoded = item['image']
                    if item.get('total') and isinstance(item.get('completed'), (float, int)):
                        percent = max(0, min(100, int(item['completed'] / item['total'] * 100)))
                        await notify(f'Creating image · {percent}%')
                    if item.get('done'):
                        complete = True
                        break
            if not complete or not encoded:
                raise ValueError('Ollama did not return a completed image. Your server may not support image generation.')
        else:
            raise ValueError('This provider does not have an image-output adapter.')
    return decode_image(encoded)


def save_image(cid, mid, result, stamp):
    data, (mime, extension) = result
    aid = str(uuid.uuid4())
    folder = settings.ATTACHMENTS_DIR / cid
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{aid}.{extension}'
    path.write_bytes(data)
    try:
        with connect() as db:
            db.execute('''INSERT INTO attachments
                (id, conversation_id, message_id, filename, content_type, size_bytes, file_path, created_at, is_image, generated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1)''',
                (aid, cid, mid, f'forma-{aid[:8]}.{extension}', mime, len(data), str(path), stamp))
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return {'id': aid, 'conversation_id': cid, 'message_id': mid, 'filename': f'forma-{aid[:8]}.{extension}',
            'content_type': mime, 'size_bytes': len(data), 'created_at': stamp, 'is_image': True, 'generated': True}
