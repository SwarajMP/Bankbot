import logging
import re
import time
import json
import asyncio
import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

from livekit import rtc, api
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
    get_job_context,
)
from livekit.plugins import cartesia, deepgram, google, noise_cancellation, silero

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("emily-agent")

# ===== ENV =====
load_dotenv(".env")

REQUIRED_ENV_VARS = [
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "LIVEKIT_URL",
    "SIP_OUTBOUND_TRUNK_ID",
]

def validate_environment():
    missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    logger.info("✅ All required environment variables validated successfully")

validate_environment()
OUTBOUND_TRUNK_ID = os.getenv("SIP_OUTBOUND_TRUNK_ID")

# ===== HELPERS =====
def normalize_phone_number(phone: str) -> Optional[str]:
    """Normalize and validate phone number."""
    if not phone:
        return None

    phone = re.sub(r"[^\d+]", "", phone)

    # Add +91 if it's a 10-digit Indian number
    if re.fullmatch(r"\d{10}", phone):
        phone = "+91" + phone
    elif not phone.startswith("+"):
        phone = "+" + phone

    return phone if re.match(r"^\+[1-9]\d{6,14}$", phone) else None


def sanitize_log_data(data: str) -> str:
    if not data:
        return ""
    patterns = [
        (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "****-****-****-****"),
        (r"\b\d{3}-\d{2}-\d{4}\b", "***-**-****"),
    ]
    for pattern, repl in patterns:
        data = re.sub(pattern, repl, data)
    return data


async def hangup_call_with_retry(max_retries: int = 3):
    for i in range(max_retries):
        try:
            job_ctx = get_job_context()
            await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))
            logger.info("✅ Call hung up successfully")
            return
        except Exception as e:
            logger.error(f"Error hanging up (attempt {i+1}): {e}")
            if i < max_retries - 1:
                await asyncio.sleep(2 ** i)
    logger.error("❌ Failed to hang up after all retries")

# ===== CALL STATE =====
@dataclass
class CallState:
    customer_name: Optional[str] = None
    phone_number: Optional[str] = None
    is_interested: bool = False
    payment_amount: Optional[str] = None
    interaction_count: int = 0
    call_start_time: float = field(default_factory=time.time)
    payment_confirmed: bool = False

# ===== AGENT LOGIC =====
class GreetingAgent(Agent):
    """Emily introduces herself and handles the conversation."""

    def __init__(self):
        super().__init__(
            instructions=(
                "You are Emily, an AI voice assistant from SecureCard Financial Services. "
                "You should sound warm, professional, and human-like. "
                "Greet the user, confirm their identity, mention their pending payment, "
                "and politely offer to help them make the payment. Keep replies short and friendly."
            )
        )

    async def on_start(self, session: AgentSession[CallState]):
        logger.info("🧠 Emily (GreetingAgent) started call session.")

        await session.wait_for_connection()
        logger.info("🔊 Audio connection ready — starting TTS playback")

        await session.say(
            "Hello! This is Emily from SecureCard Financial Services. "
            "I'm calling to remind you about your upcoming payment. "
            "Can I confirm that I'm speaking to the account holder?"
        )
        session.userdata.interaction_count += 1

        user_response = await session.listen(timeout=10)
        if user_response and user_response.text:
            reply = user_response.text.lower()
            logger.info(f"👂 Customer said: {reply}")

            if "yes" in reply:
                await session.say("Great! Your balance due is $250. Would you like to make the payment now?")
            elif "no" in reply:
                await session.say("No problem. I’ll make a note that the account holder isn’t available right now.")
            else:
                await session.say("I didn't quite catch that. Could you please repeat?")
        else:
            await session.say("I didn’t hear a response. Let’s try again another time.")

        await asyncio.sleep(2)
        await hangup_call_with_retry()

# ===== SIP DIAL LOGIC =====
async def create_sip_participant_with_retry(ctx: JobContext, phone: str, max_retries: int = 3):
    for i in range(max_retries):
        try:
            logger.info(f"📞 Dialing {phone} (attempt {i+1})")
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=OUTBOUND_TRUNK_ID,
                    sip_call_to=phone,
                    participant_identity=phone,
                    wait_until_answered=True,
                )
            )
            logger.info("✅ SIP participant connected successfully")
            return
        except api.TwirpError as e:
            logger.error(f"❌ SIP dial failed (attempt {i+1}): {e.message}")
            if i < max_retries - 1:
                await asyncio.sleep(2 ** i)
    raise RuntimeError("Failed to connect SIP participant after retries.")

# ===== ENTRYPOINT =====
async def entrypoint(ctx: JobContext):
    try:
        metadata_raw = ctx.job.metadata
        logger.info(f"📦 Raw metadata: {metadata_raw!r}")

        # Parse metadata JSON
        dial_info = {}
        if isinstance(metadata_raw, str) and metadata_raw.strip():
            try:
                dial_info = json.loads(metadata_raw)
            except json.JSONDecodeError:
                logger.warning("⚠️ Invalid JSON metadata.")
        elif isinstance(metadata_raw, dict):
            dial_info = metadata_raw

        # Flexible phone key handling
        phone_number = (
            dial_info.get("phone_number")
            or dial_info.get("phoneNumber")
            or dial_info.get("phone")
            or dial_info.get("number")
        )

        phone_number = normalize_phone_number(phone_number)

        if not phone_number:
            logger.error(f"❌ Invalid phone number: {phone_number}")
            return

        logger.info(f"📞 Starting call for: {sanitize_log_data(phone_number)} in room: {ctx.room.name}")

        await ctx.connect()

        # Load audio components
        vad = silero.VAD.load()
        logger.info("✅ VAD model loaded")

        try:
            tts = cartesia.TTS(model="sonic-english", voice="6f84f4b8-58a2-430c-8c79-688dad597532")
        except Exception as e:
            logger.warning(f"Cartesia voice load failed: {e}, using fallback voice.")
            tts = cartesia.TTS(model="sonic-english")

        session = AgentSession[CallState](
            llm=google.LLM(model="gemini-2.5-flash"),
            stt=deepgram.STT(model="nova-3", language="en-US"),
            tts=tts,
            vad=vad,
            userdata=CallState(phone_number=phone_number),
        )

        session_task = asyncio.create_task(
            session.start(
                agent=GreetingAgent(),
                room=ctx.room,
                room_input_options=RoomInputOptions(
                    noise_cancellation=noise_cancellation.BVCTelephony()
                ),
            )
        )

        # Dial the number
        await create_sip_participant_with_retry(ctx, phone_number)

        # Wait for participant join
        participant = await ctx.wait_for_participant(identity=phone_number)
        logger.info(f"👤 Participant joined: {participant.identity}")

        await session_task

        duration = time.time() - session.userdata.call_start_time
        logger.info(
            f"📊 Call completed | Duration: {duration:.1f}s | Interactions: {session.userdata.interaction_count}"
        )

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        ctx.shutdown()

# ===== RUN APP =====
if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="john-payment-specialist",
            num_idle_processes=1,
            load_threshold=float("inf"),
        )
    )
