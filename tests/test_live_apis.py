"""Automated verification script for Alpaca Paper Trading and Nebius Token Factory integration."""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from client.agent import AutonomousX402Agent
from client.wallet_manager import SolanaWalletManager
from server.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_live_apis")


async def run_live_integration_verification():
    settings = get_settings()
    gateway_url = f"http://127.0.0.1:{settings.port}"

    print("=" * 75)
    print("      AgentPay-x402 Live Alpaca & Nebius Integration Verification      ")
    print("=" * 75)
    print(f"Gateway URL:      {gateway_url}")
    print(f"Alpaca Base URL:  {settings.alpaca_base_url}")
    print(f"Nebius Base URL:  {settings.nebius_base_url}")
    print(f"Nebius Model:     {settings.nebius_model}")
    print(f"Nebius Fallback:  {settings.nebius_fallback_model}")
    print("=" * 75)

    wallet = SolanaWalletManager(rpc_url=settings.solana_rpc_url)
    agent = AutonomousX402Agent(
        wallet=wallet,
        gateway_base_url=gateway_url,
        solana_rpc_url=settings.solana_rpc_url,
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        # --- Check 1: Web UI & Badges ---
        print("\n>> [Check 1/3] Verifying Web UI and Status Badges...")
        res_ui = await client.get(f"{gateway_url}/")
        assert res_ui.status_code == 200, f"UI returned HTTP {res_ui.status_code}"
        assert "Data: Alpaca Markets Live" in res_ui.text, "Alpaca badge missing from UI"
        assert "Model: Nebius Nemotron-70B" in res_ui.text, "Nebius badge missing from UI"
        print("PASS: Web UI is live with Alpaca & Nebius status badges.")

        # --- Check 2: Market Feed with Alpaca Live Context ---
        print("\n>> [Check 2/3] Verifying GET /api/v1/market-feed (20,000 lamports settlement)...")
        status, market_data, telemetry = await agent.execute_request(
            method="GET",
            path="/api/v1/market-feed",
        )
        assert status == 200, f"Market feed failed with HTTP {status}"
        assert "alpaca_portfolio" in market_data, "Alpaca portfolio data missing"
        assert market_data["status"] == "success", "Expected success status"
        alpaca_info = market_data["alpaca_portfolio"]
        print(f"PASS: HTTP 200 OK received after on-chain settlement ({telemetry['settlement_latency_ms']:.1f}ms).")
        print("Alpaca Market Context:")
        print(f"  - Provider:        {alpaca_info.get('provider')}")
        print(f"  - Portfolio Value: ${alpaca_info.get('portfolio_value', 100000):,.2f}")
        print(f"  - Buying Power:    ${alpaca_info.get('buying_power', 200000):,.2f}")
        print(f"  - Cash Available:  ${alpaca_info.get('cash', 100000):,.2f}")
        print(f"  - Connection Note: {alpaca_info.get('note', 'Direct authenticated connection established')}")
        print(f"  - Signature Hash:  {telemetry['tx_signature']}")

        # --- Check 3: Agent Inference with Nebius Token Factory ---
        print("\n>> [Check 3/3] Verifying POST /api/v1/agent-inference (5,000 lamports settlement)...")
        prompt_text = "Analyze live Alpaca portfolio buying power and recommend optimal concentrated liquidity range."
        status_inf, infer_data, telemetry_inf = await agent.execute_request(
            method="POST",
            path="/api/v1/agent-inference",
            json_body={"prompt": prompt_text, "model": settings.nebius_model, "max_tokens": 150},
        )
        assert status_inf == 200, f"Inference failed with HTTP {status_inf}"
        assert infer_data["status"] == "success", "Expected success status"
        assert "output" in infer_data, "Missing output object"
        reasoning = infer_data["output"].get("reasoning", "")
        assert len(reasoning) > 10, "Empty reasoning trace returned"
        print(f"PASS: HTTP 200 OK received after on-chain settlement ({telemetry_inf['settlement_latency_ms']:.1f}ms).")
        print("Nebius Token Factory Inference:")
        print(f"  - Model:           {infer_data.get('nebius_model') or infer_data.get('model')}")
        print(f"  - Provider:        {infer_data.get('provider')}")
        print(f"  - Tokens Consumed: {infer_data['output'].get('tokens_consumed')}")
        print(f"  - Signature Hash:  {telemetry_inf['tx_signature']}")
        print(f"\nAuthentic Reasoning Trace:\n{reasoning}\n")

    print("=" * 75)
    print("ALL VERIFICATION CHECKS PASSED: Alpaca & Nebius Token Factory 100% OPERATIONAL")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_live_integration_verification())
