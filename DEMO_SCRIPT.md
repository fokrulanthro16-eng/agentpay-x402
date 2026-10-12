# AgentPay-x402: Hackathon Demo Video Script & Voiceover Guide

[![Solana Devnet](https://img.shields.io/badge/Solana-Devnet-14F195.svg?logo=solana&logoColor=black)](https://solana.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Nebius Token Factory](https://img.shields.io/badge/Nebius_Token_Factory-NVIDIA_Nemotron-76B900.svg?logo=nvidia&logoColor=white)](https://tokenfactory.nebius.com)
[![Alpaca Paper Markets](https://img.shields.io/badge/Alpaca-Paper_Trading-FCD535.svg?logo=alpaca&logoColor=black)](https://alpaca.markets)

---

## 1. Production Specifications

| Parameter | Value |
| :--- | :--- |
| **Target Runtime** | **2 Minutes 30 Seconds (150 Seconds)** |
| **Pacing** | 135 – 150 words per minute (crisp, confident, Silicon Valley engineer style) |
| **Audio Tone** | High energy, technically rigorous, clear articulation, zero fluff |
| **Target Visuals** | Split-screen or alternating view: **Tailwind Dashboard (`http://127.0.0.1:8000`)** on left, **Terminal Output (`uvicorn` & agent telemetry)** on right |
| **Resolution** | 1080p 60fps / 4K UHD |
| **Music Track** | Subtle, driving synthwave / cyberpunk lo-fi (ducked -18dB during voiceover) |

---

## 2. Second-by-Second Storyboard & Voiceover Script

### [0:00 – 0:35] Scene 1: The Problem (The Hook)
- **Visuals**: Split-screen animation or terminal showing an autonomous AI agent attempting to query a paid data endpoint. A giant red `401 Unauthorized` or API key expiration error flashes. Transition to slides showing Stripe credit card modals and subscription billing tables.
- **On-Screen Graphic**: `THE AGENT PAYMENTS DILEMMA: AI Minds Trapped Behind Human Credit Cards`

> **Voiceover (0:00 – 0:35)**:
> *"Every autonomous AI agent being built today faces a fatal bottleneck: it has no native bank account.*
>
> *When an agent needs real-time market alpha or specialized LLM compute, traditional financial rails fall completely apart. Credit cards require human KYC. Monthly SaaS subscriptions bleed capital even when idle. And traditional payment gateways choke on sub-cent transactions because interchange fees exceed the value of the micro-request.*
>
> *Autonomous software needs autonomous money. And that requires reviving the original, forgotten standard of the Internet: HTTP 402 Payment Required."*

---

### [0:35 – 1:10] Scene 2: The Solution & Protocol Mechanics
- **Visuals**: Cut to the clean, dark-mode **AgentPay-x402 Dashboard** (`http://127.0.0.1:8000`). Highlight the live Merchant Wallet and Solana Devnet badge. Click the **"Unauthenticated Browser Test"** button. A sleek modal pops up displaying the raw `HTTP 402 Payment Required` JSON payload and HTTP response headers (`X-402-Recipient`, `X-402-Amount: 20000`, `X-402-Network: solana-devnet`).
- **On-Screen Graphic**: `RFC/x402 PROTOCOL IN ACTION: ZERO-CUSTODY MICRO-NEGOTIATION`

> **Voiceover (0:35 – 1:10)**:
> *"Meet **AgentPay-x402**—a production-grade, autonomous machine-to-machine payment gateway running on Solana Devnet.*
>
> *Watch what happens when a client queries our protected market feed without payment credentials. The gateway instantly issues an RFC-compliant HTTP 402 challenge.*
>
> *In the response headers, the server dictates the merchant receiving public key, the exact price in lamports—here, 20,000 lamports, or just two-thousandths of a cent—and the target network.*
>
> *No API keys. No pre-funding balances. No credit card custody. Pure protocol negotiation."*

---

### [0:10 – 1:55] Scene 3: The Autonomous Live Run (The Climax)
- **Visuals**: Click **"Simulate AI Agent Run"**. The Live Activity Feed springs to life with cards transitioning from `402 CHALLENGE` to `200 SETTLED`. On the right, terminal logs show the agent constructing the Ed25519 Solana instruction, broadcasting to Devnet RPC, and obtaining transaction confirmation in **240 milliseconds**. Then, cut to the dashboard console rendering the unlocked payload: live Alpaca Paper Trading portfolio metrics and deep reasoning traces from **Nebius Token Factory powered by NVIDIA Nemotron-70B**.
- **On-Screen Graphic**: `SUB-SECOND ON-CHAIN SETTLEMENT -> LIVE ALPACA + NEBIUS NEMOTRON UNLOCKED`

> **Voiceover (1:10 – 1:55)**:
> *"Now let's watch an autonomous agent fulfill this challenge in real-time.*
>
> *The agent detects the 402 status code, parses the price registry, queries recent blockhash, and cryptographically signs a native SOL transfer transaction on Solana Devnet.*
>
> *Within 245 milliseconds, the transaction settles on-chain. The agent retries the request presenting the signature in the `X-402-Signature` header.*
>
> *Our gateway's Solana verifier inspects the transaction on Devnet, validates the lamport balance differential, verifies the merchant recipient, and unlocks the payload.*
>
> *And look at what's returned: authentic, live market context from Alpaca Paper Trading, fed directly into Nebius Token Factory's NVIDIA Nemotron model, streaming genuine quantitative trading reasoning traces back to the agent."*

---

### [1:55 – 2:15] Scene 4: Security & Replay Attack Defense
- **Visuals**: Show terminal running the automated security audit (`test_replay_attack_rejection`). An attacker replays an old signature; the gateway instantly rejects it with `402 Payment Verification Failed: Transaction signature already processed`. Highlight the Pytest terminal showing `13 passed in 7.66s`.
- **On-Screen Graphic**: `ENTERPRISE SECURITY: NONCE & SIGNATURE REPLAY SHIELD (13/13 TESTS PASSING)`

> **Voiceover (1:55 – 2:15)**:
> *"In machine-to-machine commerce, security is non-negotiable.*
>
> *AgentPay-x402 features an in-memory, thread-safe Replay Protection Shield with automated TTL eviction. If any actor attempts to reuse a transaction signature, the gateway rejects it immediately with zero compute leakage.*
>
> *Backed by 13 comprehensive unit and integration tests, our verifier validates confirmation commitments, balance deltas, and edge-case exceptions."*

---

### [2:15 – 2:30] Scene 5: Outro & The Autonomous Future
- **Visuals**: Camera zooms out showing the full project architecture banner, live Solana Explorer links, and GitHub repository URL (`github.com/fokrulanthro16-eng/agentpay-x402`).
- **On-Screen Graphic**: `AgentPay-x402: The Economic Layer for the Autonomous AI Era`

> **Voiceover (2:15 – 2:30)**:
> *"The future of software is autonomous agents paying autonomous agents—in sub-second micro-settlements on Solana.*
>
> *AgentPay-x402 is open-source, fully tested, and ready for production deployment.*
>
> *Clone the repo, run the gateway, and join the machine-to-machine economy today."*

---

## 3. Teleprompter & Recording Checklist

- [ ] **FastAPI Gateway Running**: `python -m uvicorn server.main:app --host 127.0.0.1 --port 8000`
- [ ] **Browser Window Clean**: Open `http://127.0.0.1:8000` in full screen (Chrome / Brave, zoom 100%, dark mode enabled).
- [ ] **Terminal Prepared**: Split terminal with clean dark background, 16pt font size (Fira Code / JetBrains Mono).
- [ ] **Microphone Levels**: Voice peaking between -6dB and -3dB, no background room echo.
- [ ] **Screen Recording Settings**: OBS Studio / Loom recording at 1080p60 or 4K60, 6000+ kbps bitrate.

---

## 4. Automated AI Voiceover Generator

To automatically render this script into a clean voiceover audio track (`demo_voiceover.mp3`), run the bundled script:

```bash
python scripts/generate_voiceover.py
```

This uses modern neural speech synthesis to export broadcast-quality audio matching the 2-minute 30-second pacing guide.
