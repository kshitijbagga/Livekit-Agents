import os
import sys
import asyncio
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dataclasses import dataclass
from typing import Annotated, Literal

from database import (
    COMMON_INSTRUCTIONS,
    FakeDB,
    MenuItem,
    find_items_by_id,
    menu_instructions,
)
from dotenv import load_dotenv
from order import OrderedCombo, OrderedHappy, OrderedRegular, OrderState
from pydantic import Field

from livekit.agents import (
    Agent,
    AgentSession,
    AudioConfig,
    BackgroundAudioPlayer,
    FunctionTool,
    JobContext,
    RunContext,
    ToolError,
    WorkerOptions,
    cli,
    function_tool,
    RoomInputOptions,
)

import livekit.plugins.silero as silero
import livekit.plugins.noise_cancellation as noise_cancellation

# import livekit.plugins 
# import noise_cancellation, cartesia, deepgram, openai # silero
# from livekit.plugins.turn_detector import multilingual as ml

# === NEW IMPORT ===
from interrupt_handler import InterruptHandler

load_dotenv()
logging.basicConfig(level=logging.INFO)


# --------------------------------------------------------------------------------
# USERDATA CLASS
# --------------------------------------------------------------------------------
@dataclass
class Userdata:
    order: OrderState
    drink_items: list[MenuItem]
    combo_items: list[MenuItem]
    happy_items: list[MenuItem]
    regular_items: list[MenuItem]
    sauce_items: list[MenuItem]


# --------------------------------------------------------------------------------
# DRIVE-THRU AGENT CLASS
# --------------------------------------------------------------------------------
class DriveThruAgent(Agent):
    def __init__(self, *, userdata: Userdata, interrupt_handler: InterruptHandler) -> None:
        """
        Extended DriveThruAgent with filler-word interruption handling.
        """
        self.interrupt_handler = interrupt_handler

        instructions = (
            COMMON_INSTRUCTIONS
            + "\n\n"
            + menu_instructions("drink", items=userdata.drink_items)
            + "\n\n"
            + menu_instructions("combo_meal", items=userdata.combo_items)
            + "\n\n"
            + menu_instructions("happy_meal", items=userdata.happy_items)
            + "\n\n"
            + menu_instructions("regular", items=userdata.regular_items)
            + "\n\n"
            + menu_instructions("sauce", items=userdata.sauce_items)
        )

        super().__init__(
            instructions=instructions,
            tools=[
                self.build_regular_order_tool(
                    userdata.regular_items, userdata.drink_items, userdata.sauce_items
                ),
                self.build_combo_order_tool(
                    userdata.combo_items, userdata.drink_items, userdata.sauce_items
                ),
                self.build_happy_order_tool(
                    userdata.happy_items, userdata.drink_items, userdata.sauce_items
                ),
                # self.remove_order_item,
                # self.list_order_items_1,
            ],
        )

    # --------------------------------------------------------------------------
    # FILLER INTERRUPTION HOOK
    # --------------------------------------------------------------------------
    async def on_transcription_event(self, transcript: str, confidence: float, session: AgentSession):
        """
        Hook called whenever ASR produces a transcription.
        Determines if it’s a filler interruption or genuine user speech.
        """
        agent_speaking = session.is_tts_active()

        valid_interrupt = await self.interrupt_handler.handle_transcription(
            transcript, agent_speaking, confidence
        )

        if valid_interrupt and agent_speaking:
            # Stop speaking if genuine interruption detected
            logging.info(f"Valid interruption detected: '{transcript}' — stopping TTS.")
            await session.stop_tts()
        elif not valid_interrupt:
            # Ignore filler; continue speaking
            logging.debug(f"Ignored filler: '{transcript}'")

    # --------------------------------------------------------------------------
    # TOOL DEFINITIONS (unchanged from original)
    # --------------------------------------------------------------------------
    def build_combo_order_tool(
        self, combo_items: list[MenuItem], drink_items: list[MenuItem], sauce_items: list[MenuItem]
    ) -> FunctionTool:
        available_combo_ids = {item.id for item in combo_items}
        available_drink_ids = {item.id for item in drink_items}
        available_sauce_ids = {item.id for item in sauce_items}

        @function_tool
        async def order_combo_meal(
            ctx: RunContext[Userdata],
            meal_id: Annotated[str, Field(description="Combo meal ID", json_schema_extra={"enum": list(available_combo_ids)})],
            drink_id: Annotated[str, Field(description="Drink ID", json_schema_extra={"enum": list(available_drink_ids)})],
            drink_size: Literal["M", "L", "null"] | None,
            fries_size: Literal["M", "L"],
            sauce_id: Annotated[str, Field(description="Sauce ID", json_schema_extra={"enum": [*available_sauce_ids, "null"]})] | None,
        ):
            if not find_items_by_id(combo_items, meal_id):
                raise ToolError(f"error: meal {meal_id} not found")

            drink_sizes = find_items_by_id(drink_items, drink_id)
            if not drink_sizes:
                raise ToolError(f"error: drink {drink_id} not found")

            if drink_size == "null":
                drink_size = None
            if sauce_id == "null":
                sauce_id = None

            available_sizes = list({item.size for item in drink_sizes if item.size})
            if drink_size is None and len(available_sizes) > 1:
                raise ToolError(f"error: {drink_id} has multiple sizes: {', '.join(available_sizes)}.")

            item = OrderedCombo(
                meal_id=meal_id,
                drink_id=drink_id,
                drink_size=drink_size,
                sauce_id=sauce_id,
                fries_size=fries_size,
            )
            await ctx.userdata.order.add(item)
            return f"Added combo: {item.model_dump_json()}"

        return order_combo_meal

    def build_happy_order_tool(
        self, happy_items: list[MenuItem], drink_items: list[MenuItem], sauce_items: list[MenuItem]
    ) -> FunctionTool:
        available_happy_ids = {item.id for item in happy_items}
        available_drink_ids = {item.id for item in drink_items}
        available_sauce_ids = {item.id for item in sauce_items}

        @function_tool
        async def order_happy_meal(
            ctx: RunContext[Userdata],
            meal_id: Annotated[str, Field(description="Happy meal ID", json_schema_extra={"enum": list(available_happy_ids)})],
            drink_id: Annotated[str, Field(description="Drink ID", json_schema_extra={"enum": list(available_drink_ids)})],
            drink_size: Literal["S", "M", "L", "null"] | None,
            sauce_id: Annotated[str, Field(description="Sauce ID", json_schema_extra={"enum": [*available_sauce_ids, "null"]})] | None,
        ):
            if not find_items_by_id(happy_items, meal_id):
                raise ToolError(f"error: meal {meal_id} not found")

            drink_sizes = find_items_by_id(drink_items, drink_id)
            if not drink_sizes:
                raise ToolError(f"error: drink {drink_id} not found")

            if drink_size == "null":
                drink_size = None
            if sauce_id == "null":
                sauce_id = None

            item = OrderedHappy(
                meal_id=meal_id, drink_id=drink_id, drink_size=drink_size, sauce_id=sauce_id
            )
            await ctx.userdata.order.add(item)
            return f"Added happy meal: {item.model_dump_json()}"

        return order_happy_meal

    def build_regular_order_tool(
        self, regular_items: list[MenuItem], drink_items: list[MenuItem], sauce_items: list[MenuItem]
    ) -> FunctionTool:
        all_items = regular_items + drink_items + sauce_items
        available_ids = {item.id for item in all_items}

        @function_tool
        async def order_regular_item(
            ctx: RunContext[Userdata],
            item_id: Annotated[str, Field(description="Item ID", json_schema_extra={"enum": list(available_ids)})],
            size: Annotated[Literal["S", "M", "L", "null"] | None, Field(description="Item size, if any")] = "null",
        ):
            item_sizes = find_items_by_id(all_items, item_id)
            if not item_sizes:
                raise ToolError(f"error: {item_id} not found.")

            if size == "null":
                size = None

            item = OrderedRegular(item_id=item_id, size=size)
            await ctx.userdata.order.add(item)
            return f"Added regular item: {item.model_dump_json()}"

        return order_regular_item

    @function_tool
    async def remove_order_item(self, ctx: RunContext[Userdata], order_id: list[str]) -> str:
        not_found = [oid for oid in order_id if oid not in ctx.userdata.order.items]
        if not_found:
            raise ToolError(f"error: no items found with id(s): {', '.join(not_found)}")
        removed = [await ctx.userdata.order.remove(oid) for oid in order_id]
        return "Removed:\n" + "\n".join(item.model_dump_json() for item in removed)

    @function_tool
    async def list_order_items_1(self, ctx: RunContext[Userdata]) -> str:
        items = ctx.userdata.order.items.values()
        if not items:
            return "The order is empty"
        return "\n".join(item.model_dump_json() for item in items)


# --------------------------------------------------------------------------------
# USERDATA INIT
# --------------------------------------------------------------------------------
async def new_userdata() -> Userdata:
    fake_db = FakeDB()
    drink_items = await fake_db.list_drinks()
    combo_items = await fake_db.list_combo_meals()
    happy_items = await fake_db.list_happy_meals()
    regular_items = await fake_db.list_regulars()
    sauce_items = await fake_db.list_sauces()

    order_state = OrderState(items={})
    return Userdata(
        order=order_state,
        drink_items=drink_items,
        combo_items=combo_items,
        happy_items=happy_items,
        regular_items=regular_items,
        sauce_items=sauce_items,
    )


# --------------------------------------------------------------------------------
# ENTRYPOINT WITH INTERRUPTION LOGIC
# --------------------------------------------------------------------------------
async def entrypoint(ctx: JobContext):
    await ctx.connect()
    userdata = await new_userdata()

    interrupt_handler = InterruptHandler(ignored_words=["uh", "umm", "hmm", "haan"])

    session = AgentSession(
        userdata=userdata,
        stt="assemblyai/universal-streaming:en",
        llm="google/gemini-2.0-flash",
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        # turn_detection=ml.MultilingualModel(),
        vad=silero.VAD.load(),
    )

    background_audio = BackgroundAudioPlayer(
        ambient_sound=AudioConfig(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "bg_noise.mp3"),
            volume=1.0,
        ),
    )

    agent = DriveThruAgent(userdata=userdata, interrupt_handler=interrupt_handler)

    # ✅ Proper async handler for transcription events
    async def handle_transcriptions():
        async for event in session.stream("transcription"):
            asyncio.create_task(
                agent.on_transcription_event(
                    transcript=event.text,
                    confidence=getattr(event, "confidence", 1.0),
                    session=session,
                )
            )

    # Run the listener in background
    asyncio.create_task(handle_transcriptions())

    # Start the session and background audio
    await session.start(
    agent=agent,
    room=ctx.room,
    room_input_options=RoomInputOptions(
        noise_cancellation=noise_cancellation.BVC()
    ),
)
    await background_audio.start(room=ctx.room, agent_session=session)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
