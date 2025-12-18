import logging 
from fastapi import WebSocket, APIRouter
import asyncio
import json
import os
import struct
from typing import Optional
import aiohttp
from dotenv import load_dotenv
from vonage import Auth, Vonage
from websockets.exceptions import ConnectionClosed 

load_dotenv() 

logger = logging.getLogger(__name__)

router = APIRouter()


def create_wav_header(audio_data: bytes, sample_rate: int = 16000, bits_per_sample: int = 16, channels: int = 1) -> bytes: 
    data_size = len(audio_data)
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    
    wav_header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + data_size,
        b'WAVE',
        b'fmt ',
        16,
        1,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b'data',
        data_size
    )
    
    return wav_header + audio_data

async def tts_consumer(websocket: WebSocket, queue: asyncio.Queue):
    try:
        while True:
            item = await queue.get()
            
            if item["type"] == "audio":
                await websocket.send_bytes(item["data"])
            elif item["type"] == "end":
                await websocket.send_text(json.dumps({"type": "tts_end"}))
            
            queue.task_done()
            
    except asyncio.CancelledError:
        print("TTS consumer task cancelled")
    except Exception as e:
        print(f"TTS consumer error: {e}")

async def speech_to_text(audio_data: bytes, api_key: str) -> Optional[str]:
    
    headers = {
        "xi-api-key": api_key,
    }

    form_data = aiohttp.FormData()
    form_data.add_field('model_id', os.getenv("ELEVENLABS_MODEL_ID"))
    form_data.add_field('file', 
                       audio_data, 
                       filename='audio.wav', 
                       content_type='audio/wav')
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.elevenlabs.io/v1/speech-to-text",
                headers=headers,
                data=form_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    return result.get("text", "")
                else:
                    error_text = await response.text()
                    print(f"STT Error: {response.status} - {error_text}")
                    return None
                    
    except Exception as e:
        print(f"STT error: {e}")
        return None


@router.websocket("/vonage/audio-stream")
async def audio_stream_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Vonage connected") 
    
    ELEVENLABS_API_KEY = os.getenv("ELEVEN_API_KEY")
    BUFFER_SIZE = 64000 
    VONAGE_SAMPLE_RATE = 16000  
    audio_buffer = bytearray()
    tts_queue = asyncio.Queue()

    try:
        tts_task = asyncio.create_task(tts_consumer(websocket, tts_queue))

        while True:
            message = await websocket.receive()
 

            if "text" in message and message["text"] is not None:
                text_data = message["text"]
                print("Text message:", text_data) 


            elif "bytes" in message and message["bytes"] is not None:
                audio_data = message["bytes"]
                audio_buffer.extend(audio_data)
                if len(audio_buffer) >= BUFFER_SIZE:
                    wav_audio = create_wav_header(bytes(audio_buffer), sample_rate=VONAGE_SAMPLE_RATE)
                    
                    transcript = await speech_to_text(
                        wav_audio, 
                        ELEVENLABS_API_KEY
                    )
                    
                    if transcript and not '(' in transcript:
                        print(f"STT Result: {transcript}")
                        await websocket.send_text(json.dumps({
                            "type": "transcription",
                            "text": transcript
                        }))
                    
                    audio_buffer.clear()

    except Exception as e:
        print("WebSocket disconnected")
    finally:
        if 'tts_task' in locals():
            tts_task.cancel()
            try:
                await tts_task
            except asyncio.CancelledError:
                pass