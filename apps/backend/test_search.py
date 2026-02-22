import asyncio
from app.price.manager import PriceManager

async def main():
    manager = PriceManager()
    
    print("=== Crypto Search ===")
    res1 = await manager.search_symbol("eth", "crypto")
    for r in res1:
        print(f"{r.symbol} - {r.name} ({r.type_box})")
        
    print("\n=== US Stock Search ===")
    res2 = await manager.search_symbol("apple", "us_stock")
    for r in res2[:5]:
        print(f"{r.symbol} - {r.name} ({r.type_box})")

    print("\n=== TW Stock Search ===")
    res3 = await manager.search_symbol("台積", "tw_stock")
    for r in res3[:5]:
        print(f"{r.symbol} - {r.name} ({r.type_box})")

    await manager.close()

if __name__ == "__main__":
    asyncio.run(main())
