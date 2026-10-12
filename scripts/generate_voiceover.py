"""Automated AI Voiceover Generation Script for AgentPay-x402 Hackathon Demo Video.

Renders broadcast-quality neural speech narration matching DEMO_SCRIPT.md
using edge-tts (default) or gTTS (fallback).
"""

import asyncio
from pathlib import Path
import sys

VOICEOVER_TEXT = """
Every autonomous AI agent being built today faces a fatal bottleneck: it has no native bank account.

When an agent needs real-time market alpha or specialized LLM compute, traditional financial rails fall completely apart. Credit cards require human KYC. Monthly SaaS subscriptions bleed capital even when idle. And traditional payment gateways choke on sub-cent transactions because interchange fees exceed the value of the micro-request.

Autonomous software needs autonomous money. And that requires reviving the original, forgotten standard of the Internet: HTTP 402 Payment Required.

Meet AgentPay-x402: a production-grade, autonomous machine-to-machine payment gateway running on Solana Devnet.

Watch what happens when a client queries our protected market feed without payment credentials. The gateway instantly issues an RFC-compliant HTTP 402 challenge.

In the response headers, the server dictates the merchant receiving public key, the exact price in lamports: here, 20,000 lamports, or just two-thousandths of a cent: and the target network.

No API keys. No pre-funding balances. No credit card custody. Pure protocol negotiation.

Now let's watch an autonomous agent fulfill this challenge in real-time.

The agent detects the 402 status code, parses the price registry, queries recent blockhash, and cryptographically signs a native SOL transfer transaction on Solana Devnet.

Within 245 milliseconds, the transaction settles on-chain. The agent retries the request presenting the signature in the X-402-Signature header.

Our gateway's Solana verifier inspects the transaction on Devnet, validates the lamport balance differential, verifies the merchant recipient, and unlocks the payload.

And look at what's returned: authentic, live market context from Alpaca Paper Trading, fed directly into Nebius Token Factory's NVIDIA Nemotron model, streaming genuine quantitative trading reasoning traces back to the agent.

In machine-to-machine commerce, security is non-negotiable.

AgentPay-x402 features an in-memory, thread-safe Replay Protection Shield with automated TTL eviction. If any actor attempts to reuse a transaction signature, the gateway rejects it immediately with zero compute leakage.

Backed by 13 comprehensive unit and integration tests, our verifier validates confirmation commitments, balance deltas, and edge-case exceptions.

The future of software is autonomous agents paying autonomous agents: in sub-second micro-settlements on Solana.

AgentPay-x402 is open-source, fully tested, and ready for production deployment.

Clone the repo, run the gateway, and join the machine-to-machine economy today.
""".strip()


async def generate_with_edge_tts(text: str, output_path: Path):
    import edge_tts

    # Professional, confident Silicon Valley engineer voice
    voice = "en-US-ChristopherNeural"
    print(f">> Synthesizing voiceover with edge-tts (Voice: {voice})...")
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+5%", pitch="+0Hz")
    await communicate.save(str(output_path))
    print(f">> [SUCCESS] Generated audio at: {output_path} ({output_path.stat().st_size:,} bytes)")


def generate_with_gtts(text: str, output_path: Path):
    from gtts import gTTS

    print(">> Synthesizing voiceover with gTTS fallback...")
    tts = gTTS(text=text, lang="en", tld="com")
    tts.save(str(output_path))
    print(f">> [SUCCESS] Generated audio at: {output_path} ({output_path.stat().st_size:,} bytes)")


async def main():
    output_dir = Path(__file__).resolve().parent.parent / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "demo_voiceover.mp3"

    print("=" * 70)
    print("      AgentPay-x402: Automated Hackathon Demo Voiceover Generator      ")
    print("=" * 70)
    print(f"Target Output: {output_file}")
    print(f"Word Count:    {len(VOICEOVER_TEXT.split())} words (~2m 20s runtime)")
    print("-" * 70)

    try:
        await generate_with_edge_tts(VOICEOVER_TEXT, output_file)
    except Exception as e:
        print(f"edge-tts failed ({e}), attempting gTTS fallback...")
        try:
            generate_with_gtts(VOICEOVER_TEXT, output_file)
        except Exception as e2:
            print(f"Error during voice synthesis: {e2}")
            sys.exit(1)

    print("=" * 70)
    print("Voiceover rendering complete! Ready to mix into video editor.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
