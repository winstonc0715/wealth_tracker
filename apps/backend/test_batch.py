import asyncio
from app.price.manager import PriceManager

async def main():
    manager = PriceManager()
    items = [("ETH", "crypto"), ("USDT", "crypto"), ("BTC", "crypto"), ("NVDA", "us_stock")]
    
    # 測試含快取
    print("=== 快取或即時 ===")
    res1 = await manager.get_prices_batch(items, force_refresh=False)
    for sym, pd in res1.items():
        print(f"{sym}: {pd.price} (source: {pd.source})")

    await manager.close()

if __name__ == "__main__":
    asyncio.run(main())
