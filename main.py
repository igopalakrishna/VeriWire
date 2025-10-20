import asyncio # to run the event loop
import websockets # to connect to the WebSocket server
# asyncio & websockets build an asynchronous websocket server
import base64 # to encode and decode base64 strings from Aura to pass data to Twilio
import json # to parse JSON data for Twilio
import sys # to provides access to some variables and functions used or maintained by the Python interpreter (used for debugging)
import ssl # to handle SSL/TLS encryption for secure communication

import os # to access environment variables (used for API keys)
from dotenv import load_dotenv # to load environment variables from a .env file (used for API keys)

from veriwire.bank_tools import FUNCTION_MAP
from veriwire.session import SESSIONS
from veriwire.graph import make_phrase
from veriwire.storage import init_db, log_event

load_dotenv()

def sts_connect(): # function to connect to the WebSocket server to communicate with the Deepgram API
  api_key = os.getenv("DEEPGRAM_API_KEY") # get the API key from the environment variables
  if not api_key:
      raise Exception("DEEPGRAM_API_KEY environment variable is not set") # raise an error if the API key is not set

  sts_ws = websockets.connect( # connect to the WebSocket server
      "wss://agent.deepgram.com/v1/agent/converse", # the WebSocket server URL (multi part communication protocol for sending and receiving data)
      subprotocols=["token", api_key] # use the API key as the subprotocol
  )
  return sts_ws # return the WebSocket connection

def load_config(): # function to load the config data from the config.json file
    with open("config.json", "r") as f: # open the config.json file
        return json.load(f) # return the config data as a dictionary

async def handle_barge_in(decoded, twilio_ws, streamsid): # function to handle the barge in message from Deepgram to Twilio to handle interruptions from the user
    if decoded["type"] == "UserStartedSpeaking":
        clear_message = {
            "event": "clear",
            "streamSid": streamsid
        }
        await twilio_ws.send(json.dumps(clear_message))


def execute_function_call(func_name, arguments):
    if func_name in FUNCTION_MAP:
        result = FUNCTION_MAP[func_name](**arguments)
        print(f"Function call result: {result}")
        return result
    else:
        result = {"error": f"Unknown function: {func_name}"}
        print(result)
        return result


def create_function_call_response(func_id, func_name, result):
    return {
        "type": "FunctionCallResponse",
        "id": func_id,
        "name": func_name,
        "content": json.dumps(result)
    }


async def handle_function_call_request(decoded, sts_ws): # function to handle the function call request from Deepgram to Twilio to execute the function call
    try:
        for function_call in decoded["functions"]:
            func_name = function_call["name"]
            func_id = function_call["id"]
            arguments = json.loads(function_call["arguments"])

            print(f"Function call: {func_name} (ID: {func_id}), arguments: {arguments}")
            # log function call
            try:
                # best-effort streamsid if present alongside messages (not always available here)
                streamsid = arguments.get("streamsid") if isinstance(arguments, dict) else None
                log_event(streamsid or "unknown", "function_call", json.dumps({"name": func_name, "args": arguments}))
            except Exception:
                pass

            result = execute_function_call(func_name, arguments)

            function_result = create_function_call_response(func_id, func_name, result)
            await sts_ws.send(json.dumps(function_result))
            print(f"Sent function result: {function_result}")

    except Exception as e:
        print(f"Error calling function: {e}")
        error_result = create_function_call_response(
            func_id if "func_id" in locals() else "unknown",
            func_name if "func_name" in locals() else "unknown",
            {"error": f"Function call failed with: {str(e)}"}
        )
        await sts_ws.send(json.dumps(error_result))

async def handle_text_message(decoded, twilio_ws, sts_ws, streamsid): # function to handle the text message from Deepgram to Twilio to transcribe the audio
    await handle_barge_in(decoded, twilio_ws, streamsid)

    # function calling 
    if decoded["type"] == "FunctionCallRequest":
        await handle_function_call_request(decoded, sts_ws)

async def sts_sender(sts_ws, audio_queue, usertext_queue): 
    print("sending audio to Deepgram (sts_sender)") 
    while True:
        # send any pending user text (e.g., DTMF fallback) first
        # Removed ad-hoc UserMessage injection to avoid UNPARSABLE_CLIENT_MESSAGE
        await asyncio.sleep(0)

        # then send audio if available
        chunk = await audio_queue.get()
        await sts_ws.send(chunk)

async def sts_receiver(sts_ws, twilio_ws, streamsid_queue): 
    print("receiving audio from Deepgram (sts_receiver)")
    streamsid = await streamsid_queue.get() # get the streamsid from the streamsid queue

    async for message in sts_ws:
        if type(message) is str:
            print(message)
            decoded = json.loads(message)
            await handle_text_message(decoded, twilio_ws, sts_ws, streamsid)
            continue

        raw_mulaw = message

        media_message = {
            "event": "media",
            "streamSid": streamsid,
            "media": {
                "payload": base64.b64encode(raw_mulaw).decode("ascii")
            }
        }

        await twilio_ws.send(json.dumps(media_message))


async def twilio_receiver(twilio_ws, audio_queue, usertext_queue, streamsid_queue): 
    BUFFER_SIZE = 20 * 160 # 20 seconds * 160 samples per second = 3200 samples = 1MB buffer size
    inbuffer = bytearray(b"") # initialize the input buffer as an empty bytearray - byte datatype in python represents raw binary data

    async for message in twilio_ws:
        try:
            data = json.loads(message)
            event = data["event"]

            if event == "start": # get the streamsid from Twilio to stream the audio to VeriWire
                print("get streamsid")
                start = data["start"]
                streamsid = start["streamSid"]
                streamsid_queue.put_nowait(streamsid)
                # init per-call session
                SESSIONS.set(streamsid, {"phrase": make_phrase()})
                try:
                    log_event(streamsid, "start", json.dumps(start))
                except Exception:
                    pass
            elif event == "connected": # continue the loop if the connection is established
                continue
            elif event == "media": # receive the audio data from Twilio to stream the audio to VeriWire
                media = data["media"]
                chunk = base64.b64decode(media["payload"])
                if media["track"] == "inbound":
                    inbuffer.extend(chunk)
            # DTMF fallback removed for now to avoid client parse errors on Agent API
            elif event == "stop": # stop the audio stream from Twilio to Aura
                try:
                    log_event(streamsid, "stop", "{}")
                except Exception:
                    pass
                break

            while len(inbuffer) >= BUFFER_SIZE: # while the input buffer is greater than the buffer size, send the audio data to the audio queue
                chunk = inbuffer[:BUFFER_SIZE] # send the audio data to the audio queue
                audio_queue.put_nowait(chunk) # put the audio data into the audio queue
                inbuffer = inbuffer[BUFFER_SIZE:] # remove the audio data from the input buffer
        except:
            break 

async def twilio_handler(twilio_ws): # VeriWire: handle the Twilio connection and Deepgram Agent
    audio_queue = asyncio.Queue() # create a queue to store the audio data streamed from Aura to Twilio - stores audio data for transcription 
    usertext_queue = asyncio.Queue() # queue for textual user inputs (e.g., DTMF)
    streamsid_queue = asyncio.Queue() # create a queue to store the streamsid data streamed from Twilio to Aura - represents current active connection to the WebSocket server

    async with sts_connect() as sts_ws: # connect to the WebSocket server to communicate with the Deepgram API
        config_message = load_config() # load the config data from the config.json file
        # inject dynamic liveness greeting per session if available
        try:
            # wait briefly for streamsid to be available
            streamsid = await asyncio.wait_for(streamsid_queue.get(), timeout=1.0)
            streamsid_queue.put_nowait(streamsid)
            st = SESSIONS.get(streamsid)
            phrase = st.get("phrase") or make_phrase()
            SESSIONS.set(streamsid, {"phrase": phrase})
            if isinstance(config_message, dict) and "agent" in config_message:
                config_message["agent"]["greeting"] = (
                    f"Hello, this is VeriWire. For verification, please say exactly: '{phrase}'. "
                    "For example: 'blue cedar 37' or 'silver harbor 42'."
                )
        except Exception:
            pass

        await sts_ws.send(json.dumps(config_message)) # configure the Deepgram Agent

        await asyncio.wait(
            [
                asyncio.ensure_future(sts_sender(sts_ws, audio_queue, usertext_queue)), # send audio and user text to the Deepgram Agent
                asyncio.ensure_future(sts_receiver(sts_ws, twilio_ws, streamsid_queue)), # receive the streamsid data from the WebSocket server to stream the audio to Twilio
                asyncio.ensure_future(twilio_receiver(twilio_ws, audio_queue, usertext_queue, streamsid_queue)), # receive the audio data from Twilio to stream the audio to VeriWire
            ]
        )

        await twilio_ws.close()

async def main():
    init_db()
    await websockets.serve(twilio_handler, "localhost", 5000)
    print("Server is running on http://localhost:5000")
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())