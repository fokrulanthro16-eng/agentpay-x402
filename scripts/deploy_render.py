"""Automated Live Deployment Script for AgentPay-x402 on Render.

Supports both:
1. Render REST API (Automated headless deployment via RENDER_API_KEY)
2. Playwright Browser Automation (1-Click Blueprint or Dashboard Web Service Flow)
3. Live URL Health Verification & Build Log Monitor
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time

import httpx

REPO_URL = "https://github.com/fokrulanthro16-eng/agentpay-x402"
SERVICE_NAME = "agentpay-x402"
BRANCH = "main"
BUILD_CMD = "pip install -r requirements.txt"
START_CMD = "uvicorn server.main:app --host 0.0.0.0 --port $PORT"
PLAN = "free"
PUBLIC_URL_CANDIDATE = f"https://{SERVICE_NAME}.onrender.com"


def check_live_endpoint(url: str, timeout: float = 5.0) -> bool:
    """Probe the health endpoint of the deployed service."""
    try:
        r = httpx.get(f"{url.rstrip('/')}/health", timeout=timeout)
        if r.status_code == 200 and r.json().get("status") == "healthy":
            return True
    except Exception:
        pass
    return False


async def deploy_via_render_api(api_key: str):
    """Deploy via Render REST API (v1)."""
    print("\n" + "=" * 70)
    print("           Deploying AgentPay-x402 via Render REST API              ")
    print("=" * 70)
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Fetch Owner ID
        print(">> [1/4] Retrieving Render Account Owner ID...")
        res_owners = await client.get("https://api.render.com/v1/owners", headers=headers)
        if res_owners.status_code != 200:
            print(f"Error fetching owners: HTTP {res_owners.status_code} - {res_owners.text}")
            return False
        
        owners = res_owners.json()
        if not owners:
            print("No owner account found for this API token.")
            return False
        
        owner_id = owners[0].get("owner", {}).get("id") or owners[0].get("id")
        owner_name = owners[0].get("owner", {}).get("name") or owners[0].get("name", "User")
        print(f"PASS: Connected as {owner_name} (Owner ID: {owner_id})")

        # 2. Check if service already exists
        print(f">> [2/4] Checking existing services for '{SERVICE_NAME}'...")
        res_services = await client.get("https://api.render.com/v1/services", headers=headers)
        service_id = None
        service_url = None

        if res_services.status_code == 200:
            for s in res_services.json():
                srv = s.get("service", s)
                if srv.get("name") == SERVICE_NAME:
                    service_id = srv.get("id")
                    service_url = srv.get("serviceDetails", {}).get("url")
                    print(f"Found existing service: {SERVICE_NAME} (ID: {service_id})")
                    break

        # 3. Create or Trigger Deployment
        if not service_id:
            print(f">> [3/4] Creating new Web Service '{SERVICE_NAME}'...")
            payload = {
                "type": "web_service",
                "name": SERVICE_NAME,
                "ownerId": owner_id,
                "repo": REPO_URL,
                "branch": BRANCH,
                "autoDeploy": "yes",
                "serviceDetails": {
                    "env": "python",
                    "plan": PLAN,
                    "buildCommand": BUILD_CMD,
                    "startCommand": START_CMD,
                    "envVars": [
                        {"key": "PYTHON_VERSION", "value": "3.11.9"},
                        {"key": "SOLANA_RPC_URL", "value": "https://api.devnet.solana.com"},
                        {"key": "SOLANA_NETWORK", "value": "solana-devnet"},
                        {"key": "MOCK_SETTLEMENT", "value": "true"},
                        {"key": "ALPACA_API_KEY", "value": "PKV6FTKSBFEBUW45T4ME6AVBBE"},
                        {"key": "ALPACA_SECRET_KEY", "value": "AxTbThigrfmXChC7H1ywTEgQehvvwR7fy1z3LfP4VhWgv"},
                        {"key": "ALPACA_BASE_URL", "value": "https://paper-api.alpaca.markets"},
                        {"key": "NEBIUS_BASE_URL", "value": "https://api.tokenfactory.nebius.com/v1"},
                        {"key": "NEBIUS_MODEL", "value": "nvidia/Nemotron-3_5-Lightning"},
                        {"key": "NEBIUS_FALLBACK_MODEL", "value": "nvidia/Nemotron-3_5-Lightning"},
                    ]
                }
            }
            res_create = await client.post("https://api.render.com/v1/services", headers=headers, json=payload)
            if res_create.status_code in (200, 201):
                created = res_create.json()
                service_id = created.get("id") or created.get("service", {}).get("id")
                service_url = created.get("serviceDetails", {}).get("url") or created.get("service", {}).get("serviceDetails", {}).get("url")
                print(f"PASS: Web Service created successfully (ID: {service_id})")
            else:
                print(f"Service creation returned HTTP {res_create.status_code}: {res_create.text}")
                return False
        else:
            print(f">> [3/4] Triggering latest deployment for service {service_id}...")
            res_deploy = await client.post(f"https://api.render.com/v1/services/{service_id}/deploys", headers=headers, json={"clearCache": "do_not_clear"})
            print(f"Deployment trigger response: HTTP {res_deploy.status_code}")

        # 4. Monitor Deployment Status
        print(f">> [4/4] Monitoring deployment progress...")
        deploy_url = service_url or PUBLIC_URL_CANDIDATE
        print(f"Expected Public URL: {deploy_url}")

        for attempt in range(1, 20):
            res_deploys = await client.get(f"https://api.render.com/v1/services/{service_id}/deploys?limit=1", headers=headers)
            if res_deploys.status_code == 200 and res_deploys.json():
                latest = res_deploys.json()[0].get("deploy", res_deploys.json()[0])
                status = latest.get("status")
                print(f"   [Polling {attempt}/20] Current Status: {status}")
                if status == "live":
                    print(f"\n>> SUCCESS: Deployment is LIVE at: {deploy_url}")
                    return True
                elif status in ("build_failed", "deactivated", "canceled"):
                    print(f"\n>> Deployment ended with status: {status}")
                    return False
            await asyncio.sleep(10)

        print(f"\nDeployment initiated. Public endpoint will be active shortly at: {deploy_url}")
        return True


def deploy_via_playwright(headful: bool = True):
    """Deploy via Playwright Browser Automation."""
    from playwright.sync_api import sync_playwright

    blueprint_url = f"https://render.com/deploy?repo={REPO_URL}"
    dashboard_url = "https://dashboard.render.com/select-repo?type=web"

    print("\n" + "=" * 70)
    print("      Deploying AgentPay-x402 via Playwright Browser Automation     ")
    print("=" * 70)
    print(f"1-Click Blueprint URL: {blueprint_url}")
    print(f"Target Repository:     {REPO_URL}")
    print(f"Browser Mode:          {'Headful (Visible GUI)' if headful else 'Headless'}")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful, args=["--start-maximized"])
        context = browser.new_context(viewport=None)
        page = context.new_page()

        print(f"\n>> Navigating to Render Blueprint deployment portal...")
        page.goto(blueprint_url)
        page.wait_for_timeout(3000)

        current_url = page.url
        print(f"Current URL: {current_url}")

        if "login" in current_url:
            print("\n------------------------------------------------------------")
            print("[AUTHENTICATION REQUIRED] Render login page detected.")
            print("Please log into Render (via GitHub or Email) in the browser window.")
            print("Once authenticated, Render will automatically load the blueprint.")
            print("------------------------------------------------------------\n")

            # Wait for user to log in and redirect away from login page
            try:
                page.wait_for_url(lambda u: "login" not in u, timeout=120000)
                print(f"PASS: Logged in successfully! Redirected to: {page.url}")
                page.wait_for_timeout(3000)
            except Exception:
                print("Timed out waiting for login. Please use the 1-Click URL below:")
                print(f"  {blueprint_url}")
                browser.close()
                return

        # At Blueprint / New Service Page
        print(f">> Inspecting Blueprint configuration for '{SERVICE_NAME}'...")
        page.wait_for_timeout(3000)

        # Look for "Apply" button on Blueprint or "Create Web Service"
        apply_btn = page.locator("button:has-text('Apply'), button:has-text('Create Web Service'), button:has-text('Connect')")
        if apply_btn.count() > 0:
            print(f"Found deployment trigger button: '{apply_btn.first.text_content().strip()}'. Clicking...")
            apply_btn.first.click()
            page.wait_for_timeout(5000)
            print(f"Current status page: {page.url}")

        print("\n" + "=" * 70)
        print(">> Deployment workflow initiated on Render!")
        print(f">> Live Web Service URL: {PUBLIC_URL_CANDIDATE}")
        print("=" * 70)

        page.wait_for_timeout(5000)
        browser.close()


def print_manual_1click_guide():
    """Print the instant 1-click deployment guide."""
    blueprint_url = f"https://render.com/deploy?repo={REPO_URL}"
    print("\n" + "=" * 75)
    print("      AGENTPAY-X402: INSTANT 1-CLICK CLOUD DEPLOYMENT GUIDE           ")
    print("=" * 75)
    print("Render automatically parses 'render.yaml' committed to your GitHub repository.")
    print("To trigger instant cloud deployment with 1 click:")
    print(f"\n  👉 Direct Blueprint URL: {blueprint_url}\n")
    print("Pre-configured Service Specs (from render.yaml):")
    print(f"  • Name:            {SERVICE_NAME}")
    print(f"  • Repository:      {REPO_URL}")
    print(f"  • Branch:          {BRANCH}")
    print(f"  • Build Command:   {BUILD_CMD}")
    print(f"  • Start Command:   {START_CMD}")
    print(f"  • Plan:            {PLAN.upper()}")
    print(f"  • Public Endpoint: {PUBLIC_URL_CANDIDATE}")
    print("=" * 75 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Deploy AgentPay-x402 to Render Cloud")
    parser.add_argument("--api-key", help="Render API Key (or set RENDER_API_KEY env var)")
    parser.add_argument("--headful", action="store_true", default=True, help="Run browser in headful mode for login")
    parser.add_argument("--check-only", action="store_true", help="Only check if live endpoint is reachable")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("RENDER_API_KEY")

    if args.check_only:
        print(f">> Checking live endpoint status at: {PUBLIC_URL_CANDIDATE}/health...")
        if check_live_endpoint(PUBLIC_URL_CANDIDATE):
            print(f"PASS: Service is LIVE and HEALTHY at: {PUBLIC_URL_CANDIDATE}")
        else:
            print(f"NOTICE: Service is still building or not yet deployed at: {PUBLIC_URL_CANDIDATE}")
        return

    print_manual_1click_guide()

    if api_key:
        asyncio.run(deploy_via_render_api(api_key))
    else:
        print("No RENDER_API_KEY detected. Launching browser automation flow...")
        try:
            deploy_via_playwright(headful=args.headful)
        except Exception as e:
            print(f"Browser automation note: {e}")
            print("You can also deploy instantly with the 1-click URL above.")


if __name__ == "__main__":
    main()
