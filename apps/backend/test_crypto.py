import asyncio
from app.price.manager import PriceManager

async def main():
    manager = PriceManager()
    print("ETH:")
    try:
        eth = await manager.get_price("ETH", "crypto", force_refresh=True)
        print(eth.price)
    except Exception as e:
        print(f"Error: {e}")
        
    print("USDT:")
    try:
        usdt = await manager.get_price("USDT", "crypto", force_refresh=True)
        print(usdt.price)
    except Exception as e:
        print(f"Error: {e}")
        
    await manager.close()

if __name__ == "__main__":
    asyncio.run(main())
