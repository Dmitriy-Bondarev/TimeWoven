import asyncio
import json
import os

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

from app.bot.max_messenger import MaxMessengerBot


async def main() -> None:
    if load_dotenv is not None:
        load_dotenv()

    bot = MaxMessengerBot()
    user_id = "4471252"
    text = "Тест TimeWoven: проверка отправки сообщения из test_bot.py"

    result = await bot.send_message(user_id=user_id, text=text)
    print("BOT_SEND_RESULT")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not bot.api_token:
        print("WARNING: MAX_BOT_TOKEN is empty")


if __name__ == "__main__":
    asyncio.run(main())
