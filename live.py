import os
import asyncio
import logging
import sys
from telethon import TelegramClient, events
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger('telethon').setLevel(logging.WARNING)

# Configuration
API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
SESSION_NAME = 'live_bot_session'

if not API_ID or not API_HASH:
    print("Error: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in a .env file.")
    exit(1)

async def main():
    async with TelegramClient(SESSION_NAME, int(API_ID), API_HASH) as client:
        print(f"LiveBot Connected! (Powered by prompt_toolkit)")
        print("Listening for command: !live")

        @client.on(events.NewMessage(outgoing=True, pattern=r'^!live\s*$'))
        async def live_handler(event):
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', getattr(chat, 'first_name', str(chat.id)))
            print(f"\nLive mode activated for {chat_title}.")
            print("Type away! Supports readline shortcuts (Ctrl+A, Ctrl+E, etc.)")
            print("Press Enter to send, Ctrl+C to cancel.")

            # Shared state
            state = {
                'text': '',
                'cursor_pos': 0,
                'running': True,
                'last_sent': ''
            }

            # Key bindings
            kb = KeyBindings()

            @kb.add(Keys.Enter)
            def _(event):
                event.app.exit(result=event.app.current_buffer.text)

            @kb.add(Keys.ControlC)
            def _(event):
                event.app.exit(exception=KeyboardInterrupt)

            # Create session
            session = PromptSession(key_bindings=kb)

            # Hook into buffer changes
            def on_text_changed(_):
                state['text'] = session.default_buffer.text
                state['cursor_pos'] = session.default_buffer.cursor_position
            
            session.default_buffer.on_text_changed += on_text_changed
            
            # Background sync task
            async def sync_loop():
                try:
                    while state['running']:
                        txt = state['text']
                        pos = state['cursor_pos']
                        
                        # Insert cursor visual
                        # Handle case where cursor is at the end
                        if pos >= len(txt):
                            display_text = txt + " █"
                        else:
                            display_text = txt[:pos] + " █" + txt[pos:]
                        
                        if display_text != state['last_sent']:
                            try:
                                await event.edit(display_text)
                                state['last_sent'] = display_text
                            except Exception:
                                # Ignore rate limits or unchanged content errors
                                pass
                        
                        await asyncio.sleep(0.1) # Throttle updates
                except asyncio.CancelledError:
                    pass

            sync_task = asyncio.create_task(sync_loop())

            try:
                # Run the prompt
                # patch_stdout ensure that if we print something else, it doesn't break the prompt line
                with patch_stdout():
                    result = await session.prompt_async(message="> ")
                
                # Success - stop sync and update final
                state['running'] = False
                await sync_task
                
                if result:
                    await event.edit(result)
                else:
                    await event.delete()
                    
            except KeyboardInterrupt:
                state['running'] = False
                sync_task.cancel()
                print("\nCancelled.")
                await event.delete()
            except Exception as e:
                state['running'] = False
                sync_task.cancel()
                print(f"\nError: {e}")
            finally:
                if not sync_task.done():
                    sync_task.cancel()
                print("Live mode finished.")

        await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())