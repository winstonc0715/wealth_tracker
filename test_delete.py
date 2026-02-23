import httpx
import asyncio

async def main():
    base_url = "https://wealthtracker-production-f2c3.up.railway.app/api"
    
    async with httpx.AsyncClient() as client:
        # Register user
        reg_resp = await client.post(f"{base_url}/auth/register", json={
            "email": "testdeletetry3@example.com",
            "password": "Password123!",
            "username": "Test Delete User"
        })
        print("Register:", reg_resp.status_code, reg_resp.text)
        
        # Login
        login_resp = await client.post(f"{base_url}/auth/login", json={
            "email": "testdeletetry3@example.com",
            "password": "Password123!"
        })
        print("Login:", login_resp.status_code, login_resp.text)
        
        if login_resp.status_code != 200:
            return
            
        token = login_resp.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Origin": "https://wealth-tracker-web-brown.vercel.app"}
        
        # Create portfolio
        port_resp = await client.post(f"{base_url}/portfolio/", headers=headers, json={
            "name": "Test Delete Portfolio",
            "base_currency": "USD"
        })
        print("Create Portfolio:", port_resp.status_code, port_resp.text)
        if port_resp.status_code != 200:
            return
        portfolio_id = port_resp.json()["data"]["id"]
        
        cat_id = 1

        # Create transaction
        tx_resp = await client.post(f"{base_url}/transactions/", headers=headers, json={
            "portfolio_id": portfolio_id,
            "category_id": cat_id,
            "symbol": "AAPL",
            "asset_name": "Apple",
            "tx_type": "buy",
            "quantity": 10,
            "unit_price": 150.0,
            "fee": 1.0,
            "currency": "USD",
            "executed_at": "2023-01-01T00:00:00Z"
        })
        print("Create Transaction:", tx_resp.status_code, tx_resp.text)
        
        if tx_resp.status_code == 200:
            tx_id = tx_resp.json()["data"]["id"]
            
            # Delete transaction
            del_resp = await client.delete(f"{base_url}/transactions/{tx_id}", headers=headers)
            print("Delete Transaction:", del_resp.status_code, del_resp.text)

if __name__ == "__main__":
    asyncio.run(main())
