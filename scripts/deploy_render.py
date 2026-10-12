"""Automated Live Deployment Script for AgentPay-x402 on Render Cloud.

Supports:
1. Render REST API (Headless programmatic deployment via RENDER_API_KEY)
2. Playwright Browser Automation with Chrome Profile Persistence
3. Live Build Log Monitoring & Public URL Health Verification
"""

import argparse
import asyncio
import os
from pathlib import Path
import re
import sys
import time

import httpx

REPO_URL = "https://github.com/fokrulanthro16-eng/agentpay-x402"
REPO_NAME = "fokrulanthro16-eng/agentpay-x402"
SERVICE_NAME = "agentpay-x402"
BRANCH = "main"
BUILD_CMD = "pip install -r requirements.txt"
START_CMD = "uvicorn server.main:app --host 0.0.0.0 --port $PORT"
PLAN = "free"
PUBLIC_URL_CANDIDATE = f"https://{SERVICE_NAME}.onrender.com"


def check_live_endpoint(url: str, timeout: float = 6.0) -> bool:
    """Probe the health endpoint of the deployed service."""
    try:
        r = httpx.get(f"{url.rstrip('/')}/health", timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "healthy":
                return True
    except Exception:
        pass
    return False


async def deploy_via_render_api(api_key: str):
    """Deploy via Render REST API (v1)."""
    print("\n" + "=" * 75)
    print("           Deploying AgentPay-x402 via Render REST API              ")
    print("=" * 75)
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

        # 4. Monitor Deployment Status & Build Logs
        print(f">> [4/4] Monitoring deployment progress...")
        deploy_url = service_url or PUBLIC_URL_CANDIDATE
        print(f"Public URL: {deploy_url}")

        for attempt in range(1, 25):
            res_deploys = await client.get(f"https://api.render.com/v1/services/{service_id}/deploys?limit=1", headers=headers)
            if res_deploys.status_code == 200 and res_deploys.json():
                latest = res_deploys.json()[0].get("deploy", res_deploys.json()[0])
                status = latest.get("status")
                commit_info = latest.get("commit", {}).get("message", "Latest commit")
                print(f"   [Polling {attempt}/25] Deploy Status: {status} (Commit: {commit_info[:40]}...)")
                if status == "live":
                    print("\n" + "=" * 75)
                    print(f"SUCCESS: AgentPay-x402 is LIVE on Render Cloud!")
                    print(f"Public URL:       {deploy_url}")
                    print(f"Health Endpoint:  {deploy_url}/health")
                    print("=" * 75 + "\n")
                    return True
                elif status in ("build_failed", "deactivated", "canceled"):
                    print(f"\nDeployment ended with status: {status}")
                    return False
            await asyncio.sleep(10)

        print(f"\nDeployment initiated. Public endpoint will be live at: {deploy_url}")
        return True


def deploy_via_playwright(headful: bool = True):
    """Deploy via Playwright Browser Automation with Chrome Profile Persistence."""
    from playwright.sync_api import sync_playwright

    blueprint_url = f"https://render.com/deploy?repo={REPO_URL}"
    dashboard_url = "https://dashboard.render.com/select-repo?type=web"
    session_dir = Path.home() / ".render_browser_session"
    session_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 75)
    print("      Deploying AgentPay-x402 via Playwright Browser Automation     ")
    print("=" * 75)
    print(f"Repository:           {REPO_URL}")
    print(f"Target Service Name:  {SERVICE_NAME}")
    print(f"Build Command:        {BUILD_CMD}")
    print(f"Start Command:        {START_CMD}")
    print(f"Plan Tier:            {PLAN.upper()}")
    print(f"Browser Mode:         {'Visible Headful Browser' if headful else 'Headless'}")
    print(f"Session Profile Dir:  {session_dir}")
    print("=" * 75)

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(session_dir),
                channel="chrome",
                headless=not headful,
                args=["--start-maximized"]
            )
        except Exception:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(session_dir),
                headless=not headful,
                args=["--start-maximized"]
            )

        page = context.new_page()

        print(f"\n>> Step 1: Navigating to Render Blueprint Portal...")
        page.goto(blueprint_url, wait_until="networkidle")
        page.wait_for_timeout(3000)

        current_url = page.url
        print(f"Current URL: {current_url}")

        # Check if user needs to authenticate
        if "login" in current_url:
            print("\n------------------------------------------------------------")
            print("[ACTION REQUIRED] Render Login Page Detected.")
            print("Please click 'GitHub' or log in to Render in the open browser window.")
            print("Once authenticated, the script will automatically continue!")
            print("------------------------------------------------------------\n")

            # Click GitHub login button automatically if visible
            github_btn = page.locator("button:has-text('GitHub'), a:has-text('GitHub')")
            if github_btn.count() > 0:
                print("Found 'GitHub' sign-in button. Clicking automatically...")
                try:
                    github_btn.first.click()
                except Exception:
                    pass

            # Wait for user to log in and redirect to dashboard or blueprint
            try:
                page.wait_for_url(lambda u: "login" not in u, timeout=120000)
                print(f"PASS: Authentication successful! Redirected to: {page.url}")
                page.wait_for_timeout(3000)
            except Exception:
                print("Timed out waiting for login. You can use the 1-Click URL below:")
                print(f"  {blueprint_url}")
                context.close()
                return

        # Handle Blueprint creation page
        print(f">> Step 2: Processing Blueprint / Web Service settings for '{SERVICE_NAME}'...")
        page.wait_for_timeout(4000)

        # If on Blueprint page: look for Apply button
        apply_btn = page.locator("button:has-text('Apply'), button:has-text('Create Web Service'), button:has-text('Connect')")
        if apply_btn.count() > 0:
            btn_label = apply_btn.first.text_content().strip()
            print(f"Found deployment trigger: '{btn_label}'. Clicking...")
            apply_btn.first.click()
            page.wait_for_timeout(5000)

        # Check if on service details page
        print(f">> Step 3: Monitoring deployment page: {page.url}")
        page.wait_for_timeout(5000)

        # Look for live link on page (e.g. *.onrender.com)
        links = page.locator("a[href*='onrender.com']").all()
        detected_url = PUBLIC_URL_CANDIDATE
        if links:
            detected_url = links[0].get_attribute("href")
            print(f"Detected Public URL: {detected_url}")

        print("\n" + "=" * 75)
        print(">> Deployment workflow initiated on Render Cloud!")
        print(f">> Public Endpoint: {detected_url}")
        print(f">> Health Check:    {detected_url}/health")
        print("=" * 75 + "\n")

        page.wait_for_timeout(5000)
        context.close()


def print_1click_guide():
    """Print the 1-click cloud deployment guide."""
    blueprint_url = f"https://render.com/deploy?repo={REPO_URL}"
    print("\n" + "=" * 75)
    print("      AGENTPAY-X402: 1-CLICK CLOUD DEPLOYMENT PORTAL                 ")
    print("=" * 75)
    print("Your repository is fully configured with 'render.yaml'.")
    print("To trigger automatic deployment on Render with 1 click:")
    print(f"\n  👉 Direct Blueprint URL: {blueprint_url}\n")
    print("Specifications automatically provisioned:")
    print(f"  • Name:            {SERVICE_NAME}")
    print(f"  • Repository:      {REPO_URL}")
    print(f"  • Branch:          {BRANCH}")
    print(f"  • Build Command:   {BUILD_CMD}")
    print(f"  • Start Command:   {START_CMD}")
    print(f"  • Plan Tier:       {PLAN.upper()}")
    print(f"  • Expected URL:    {PUBLIC_URL_CANDIDATE}")
    print("=" * 75 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Automate AgentPay-x402 Live Deployment to Render")
    parser.add_argument("--api-key", help="Render API Token (or set RENDER_API_KEY environment variable)")
    parser.add_argument("--headful", action="store_true", default=True, help="Launch visible Chrome browser for OAuth")
    parser.add_argument("--check-only", action="store_true", help="Probe if public endpoint is reachable")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("RENDER_API_KEY")

    if args.check_only:
        print(f">> Checking live endpoint status at: {PUBLIC_URL_CANDIDATE}/health...")
        if check_live_endpoint(PUBLIC_URL_CANDIDATE):
            print(f"PASS: Service is LIVE and HEALTHY at: {PUBLIC_URL_CANDIDATE}")
        else:
            print(f"NOTICE: Service is still building or not yet deployed at: {PUBLIC_URL_CANDIDATE}")
        return

    print_1click_guide()

    if api_key:
        print("RENDER_API_KEY detected. Initiating automated REST API deployment...")
        asyncio.run(deploy_via_render_api(api_key))
    else:
        print("No RENDER_API_KEY environment variable detected.")
        print("Launching Playwright Chrome automation to connect repository...")
        try:
            deploy_via_playwright(headful=args.headful)
        except Exception as e:
            print(f"Browser automation note: {e}")
            print(f"You can also click the 1-Click Blueprint URL above directly in your browser.")


if __name__ == "__main__":
    main()
