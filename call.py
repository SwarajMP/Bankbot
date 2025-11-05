import asyncio
import os
import json
import time
import re
from dotenv import load_dotenv
from livekit import api

# === Agent and Target Info ===
AGENT_NAME = "john-payment-specialist"
PHONE_NUMBER_TO_CALL = "+91 "  # Replace with your verified number

# === Required Environment Variables ===
REQUIRED_ENV_VARS = [
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "LIVEKIT_URL",
    "SIP_OUTBOUND_TRUNK_ID"
]


def validate_phone_number(phone: str) -> bool:
    pattern = r'^\+[1-9]\d{1,14}$'
    return bool(re.match(pattern, phone))


def validate_environment() -> dict:
    load_dotenv(".env")
    env_vars = {}
    missing_vars = []

    for var in REQUIRED_ENV_VARS:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            env_vars[var] = value

    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    return env_vars


async def test_api_connection(env_vars: dict) -> api.LiveKitAPI:
    ws_url = env_vars["LIVEKIT_URL"]
    api_key = env_vars["LIVEKIT_API_KEY"]
    api_secret = env_vars["LIVEKIT_API_SECRET"]

    http_url = ws_url.replace("wss://", "https://").replace("ws://", "http://")
    lkapi = api.LiveKitAPI(url=http_url, api_key=api_key, api_secret=api_secret)

    print(f"\n🔌 Testing LiveKit API connection...")
    try:
        rooms = await lkapi.room.list_rooms(api.ListRoomsRequest())
        print(f"✅ Connected to LiveKit successfully! ({len(rooms.rooms)} active rooms)")
        return lkapi
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        await lkapi.aclose()
        raise


async def test_sip_configuration(env_vars: dict):
    trunk_id = env_vars["SIP_OUTBOUND_TRUNK_ID"]
    print(f"\n📡 Validating SIP Configuration...")
    print(f"   Trunk ID: {trunk_id}")
    print(f"   Target: {PHONE_NUMBER_TO_CALL}")

    if not validate_phone_number(PHONE_NUMBER_TO_CALL):
        raise ValueError(f"Invalid phone number format: {PHONE_NUMBER_TO_CALL}")

    print("✅ SIP and phone number are valid.")


async def create_payment_call(lkapi: api.LiveKitAPI, trunk_id: str):
    timestamp = int(time.time())
    room_name = f"payment-outbound-call-{timestamp}"

    print(f"\n🏦 Starting Outbound Payment Call...")
    print(f"   Agent: {AGENT_NAME}")
    print(f"   To: {PHONE_NUMBER_TO_CALL}")

    # ✅ Use camelCase metadata keys (as required by john-agent)
    metadata_dict = {
        "phoneNumber": PHONE_NUMBER_TO_CALL,
        "callType": "credit_card_payment",
        "company": "SecureCard Financial Services",
        "agentName": "John",
        "createdAt": timestamp,
        "purpose": "payment_collection"
    }

    metadata = json.dumps(metadata_dict)
    print("📋 Metadata:")
    print(json.dumps(metadata_dict, indent=2))

    try:
        print("🚀 Initiating SIP call through LiveKit...")
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,
                room=room_name,
                metadata=metadata
            )
        )

        print("✅ Dispatch created successfully!")
        print(f"   Dispatch ID: {dispatch.id}")
        print(f"   Room: {dispatch.room}")

        return {
            "dispatch_id": dispatch.id,
            "room": dispatch.room,
            "agent_name": AGENT_NAME,
            "phone_number": PHONE_NUMBER_TO_CALL,
            "created_at": timestamp
        }

    except api.TwirpError as e:
        print(f"❌ LiveKit API Error: {e.code} - {e.message}")
        if "object cannot be found" in e.message.lower():
            print("🔧 Check SIP trunk configuration in LiveKit dashboard.")
        elif "agent" in e.message.lower():
            print("🔧 Verify agent name and deployment status in Telephony → Agents.")
        elif "unauthorized" in e.message.lower():
            print("🔧 Check your LiveKit API key and secret.")
        raise


async def cleanup_old_rooms(lkapi: api.LiveKitAPI, max_age_minutes: int = 30):
    try:
        rooms = await lkapi.room.list_rooms(api.ListRoomsRequest())
        now = time.time()
        old_rooms = [
            r.name for r in rooms.rooms
            if r.name.startswith("payment-outbound-call-") and
            (now - int(r.name.split("-")[-1])) / 60 > max_age_minutes
        ]

        if old_rooms:
            print(f"\n🧹 Cleaning {len(old_rooms)} old rooms...")
            for r in old_rooms:
                await lkapi.room.delete_room(api.DeleteRoomRequest(room=r))
                print(f"   ✅ Deleted: {r}")
        else:
            print("✨ No old rooms to clean.")
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")


async def main():
    print("🎯 SecureCard Financial Services - Automated Payment Call")
    print("=" * 60)

    try:
        print("1️⃣ Validating environment...")
        env_vars = validate_environment()

        print("\n2️⃣ Connecting to LiveKit API...")
        lkapi = await test_api_connection(env_vars)

        print("\n3️⃣ Validating SIP settings...")
        await test_sip_configuration(env_vars)

        print("\n4️⃣ Cleaning up old rooms...")
        await cleanup_old_rooms(lkapi)

        print("\n5️⃣ Creating payment call...")
        await create_payment_call(lkapi, env_vars["SIP_OUTBOUND_TRUNK_ID"])

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        if "lkapi" in locals():
            await lkapi.aclose()
            print("🔒 API connection closed.")


if __name__ == "__main__":
    asyncio.run(main())
