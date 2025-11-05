# BankBot - Automated Payment Collection System

A sophisticated AI-powered voice assistant system for automated payment collection calls using LiveKit's voice capabilities and AI services.

## Overview

BankBot is an automated calling system that uses an AI agent named **John** to make outbound calls for payment collection. The system leverages **LiveKit** for real-time voice communication, **Google Gemini AI** for natural language processing, and a combination of speech technologies for transcription and text-to-speech conversion.

## Features

- 🤖 AI-powered voice assistant (**John**) for natural, human-like conversations  
- 📞 Automated outbound calling using SIP trunking  
- 🗣️ NLP powered by **Google Gemini AI**  
- 🎙️ Speech recognition through **Deepgram**  
- 🔊 Text-to-speech using **Cartesia**  
- 🎭 Voice activity detection using **Silero**  
- 🔇 Noise cancellation for improved clarity  
- 📊 Detailed call logging and metrics  
- ⚡ Automatic retry and error recovery  

## Prerequisites

- Python 3.7+  
- LiveKit account with API keys  
- SIP trunk configured  
- Google Gemini API key  
- Required environment variables set via system or deployment environment  

## Installation

Clone the repository and install dependencies:

```bash
pip install -r requirements.txt
Environment Configuration

Before running the system, ensure these environment variables are configured in your system, Docker environment, or deployment platform:

-LIVEKIT_API_KEY
-LIVEKIT_API_SECRET
-LIVEKIT_URL
-SIP_OUTBOUND_TRUNK_ID
-GOOGLE_API_KEY

No .env file is required — values can be set via OS environment variables or secure configuration managers.

Project Structure
bankbot/
│
├── agent.py                # AI agent (John) and conversation logic
├── call.py                 # Call management and LiveKit interaction
├── list_models.py          # Lists available Google Gemini models
├── requirements.txt        # Dependency list
├── outbound-trunk.json     # Example SIP trunk configuration
└── participant.json        # Sample participant configuration

Usage
-Verify all environment variables are set
-Update the phone number in call.py
-Run the system:
  python call.py

Key Components
## Key Components

### John Agent (GreetingAgent)

John is responsible for:

- Introducing herself as a representative from **SecureCard Financial Services**
- Verifying customer identity
- Discussing outstanding payments
- Handling natural back-and-forth conversation
- Managing call flow intelligently

---

### Call Management

The calling system includes:

- Phone number normalization and validation
- Connection retries and failure handling
- Call state tracking
- Secure SIP trunk communication
- Comprehensive logging for diagnostics

---

### Security Features

- Sanitization of sensitive input data
- Masking confidential information in logs
- Environment variable validation
- Secure call routing via LiveKit and SIP

---

### Logging

Logs include:

- Timestamps
- Call events and statuses
- Errors and exceptions
- Call duration and metrics

---

### Error Handling

- Automatic retries for failed operations
- Graceful recovery from exceptions
- Detailed logging for debugging


Requirements
Refer to `requirements.txt` for the full list of dependencies:
- livekit-agents  
- livekit-api  
- livekit-plugins-google  
- livekit-plugins-deepgram  
- livekit-plugins-cartesia  
- livekit-plugins-silero  
- livekit-plugins-noise-cancellation  
- google-auth  
- deepgram-sdk  
- python-dotenv  
- requests  
- aiohttp  
- asyncio  
- rich  
- loguru  
- pydantic

